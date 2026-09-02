import json
import re
import subprocess
import sys
from typing import Any, Dict, List

import streamlit as st
from groq import Groq
from playwright.sync_api import sync_playwright


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="EcoComply",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1250px;
        }

        .eco-header {
            padding: 1.5rem 1.75rem;
            border-radius: 18px;
            border: 1px solid #dfe7e1;
            background: linear-gradient(135deg, #f4faf5, #ffffff);
            margin-bottom: 1.5rem;
        }

        .eco-header h1 {
            margin: 0;
            font-size: 2.4rem;
        }

        .eco-header p {
            margin-top: 0.5rem;
            margin-bottom: 0;
            color: #52605a;
            font-size: 1.05rem;
        }

        .section-label {
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #68766e;
            margin-bottom: 0.25rem;
        }

        .status-card {
            border: 1px solid #dfe7e1;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            background: #ffffff;
            min-height: 105px;
        }

        .status-card .label {
            color: #68766e;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .status-card .value {
            font-size: 1.7rem;
            font-weight: 750;
            margin-top: 0.3rem;
        }

        .requirement-card {
            border: 1px solid #dfe7e1;
            border-radius: 16px;
            padding: 1.25rem;
            margin-bottom: 1rem;
            background: #ffffff;
        }

        .requirement-title {
            font-size: 1.2rem;
            font-weight: 750;
            margin-bottom: 0.65rem;
        }

        .evidence-box {
            border-left: 4px solid #8aa996;
            background: #f7faf8;
            padding: 0.85rem 1rem;
            border-radius: 0 10px 10px 0;
            margin-top: 0.5rem;
        }

        .next-step {
            border: 1px solid #dfe7e1;
            border-radius: 12px;
            padding: 0.85rem 1rem;
            margin: 0.5rem 0;
            background: #fafcfb;
        }

        .source-card {
            border: 1px solid #e0e6e2;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            background: #ffffff;
        }

        .source-type {
            font-size: 0.78rem;
            font-weight: 750;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #68766e;
        }

        .source-title {
            font-weight: 700;
            margin-top: 0.2rem;
        }

        .source-score {
            color: #6b766f;
            font-size: 0.85rem;
        }

        .disclaimer {
            border: 1px solid #e5e5e5;
            background: #fafafa;
            border-radius: 12px;
            padding: 1rem;
            color: #606060;
            font-size: 0.88rem;
            margin-top: 2rem;
        }

        .research-success {
            border: 1px solid #cfe3d4;
            background: #f4faf5;
            border-radius: 12px;
            padding: 1rem;
            margin: 1rem 0;
        }

        .small-muted {
            color: #68766e;
            font-size: 0.88rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="eco-header">
        <h1>🌱 EcoComply</h1>
        <p>
            Evidence-based environmental compliance research for small businesses.
            EcoComply retrieves official regulatory sources, analyzes applicability,
            and shows exactly why a requirement was flagged.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# REGULATORY SOURCE CATALOG
# ============================================================

REGULATORY_TOPICS = {
    "Hazardous waste": [
        {
            "name": "eCFR — 40 CFR Part 261",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-261",
            "source_type": "eCFR",
            "keywords": [
                "hazardous waste",
                "waste",
                "spent solvent",
                "solvent",
                "waste oil",
                "hazardous material",
                "discarded",
            ],
        },
        {
            "name": "eCFR — 40 CFR Part 262",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-262",
            "source_type": "eCFR",
            "keywords": [
                "generator",
                "hazardous waste",
                "waste generator",
                "accumulation",
                "manifest",
                "recordkeeping",
            ],
        },
        {
            "name": "Michigan EGLE — Hazardous Waste",
            "url": "https://www.michigan.gov/egle/about/organization/materials-management/hazardous-waste",
            "source_type": "Michigan EGLE",
            "keywords": [
                "hazardous waste",
                "waste",
                "generator",
                "Michigan",
            ],
        },
        {
            "name": "Michigan EGLE — Hazardous Waste Disposal Guidance",
            "url": "https://www.michigan.gov/egle/about/organization/materials-management/hazardous-waste/liquid-industrial-byproducts/hw-disposal-guidance",
            "source_type": "Michigan EGLE",
            "keywords": [
                "hazardous waste",
                "disposal",
                "solvent",
                "waste",
                "container",
            ],
        },
    ],

    "Materials storage and releases": [
        {
            "name": "eCFR — 40 CFR Part 264",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-264",
            "source_type": "eCFR",
            "keywords": [
                "storage",
                "container",
                "release",
                "hazardous material",
                "hazardous waste",
            ],
        },
        {
            "name": "Michigan EGLE — Automotive Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "source_type": "Michigan EGLE",
            "keywords": [
                "automotive",
                "repair",
                "storage",
                "spill",
                "release",
                "waste",
            ],
        },
    ],

    "Air emissions and VOCs": [
        {
            "name": "eCFR — 40 CFR § 63.11169",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11169",
            "source_type": "eCFR",
            "keywords": [
                "air",
                "emission",
                "paint",
                "coating",
                "hazardous air pollutant",
                "HAP",
            ],
        },
        {
            "name": "eCFR — 40 CFR § 63.11170",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11170",
            "source_type": "eCFR",
            "keywords": [
                "applicability",
                "motor vehicle",
                "spray",
                "coating",
                "paint",
            ],
        },
        {
            "name": "eCFR — 40 CFR § 63.11173",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11173",
            "source_type": "eCFR",
            "keywords": [
                "paint",
                "methylene chloride",
                "MeCl",
                "training",
                "recordkeeping",
                "minimization",
            ],
        },
        {
            "name": "eCFR — 40 CFR § 63.11175",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11175",
            "source_type": "eCFR",
            "keywords": [
                "notification",
                "air",
                "paint",
                "surface coating",
            ],
        },
        {
            "name": "EPA — About EPA's Auto Body Rule",
            "url": "https://www.epa.gov/collision-repair-campaign/about-epas-auto-body-rule",
            "source_type": "EPA",
            "keywords": [
                "auto body",
                "collision repair",
                "paint",
                "surface coating",
                "air",
                "emission",
            ],
        },
    ],

    "Paint and surface coating": [
        {
            "name": "eCFR — Subpart HHHHHH",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH",
            "source_type": "eCFR",
            "keywords": [
                "paint",
                "coating",
                "surface coating",
                "paint stripping",
                "motor vehicle",
                "spray",
            ],
        },
        {
            "name": "eCFR — 40 CFR § 63.11170",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11170",
            "source_type": "eCFR",
            "keywords": [
                "applicability",
                "motor vehicle",
                "spray",
                "coating",
            ],
        },
        {
            "name": "EPA — About EPA's Auto Body Rule",
            "url": "https://www.epa.gov/collision-repair-campaign/about-epas-auto-body-rule",
            "source_type": "EPA",
            "keywords": [
                "auto body",
                "collision repair",
                "paint",
                "surface coating",
            ],
        },
    ],

    "General environmental requirements": [
        {
            "name": "Michigan EGLE — Automotive Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "source_type": "Michigan EGLE",
            "keywords": [
                "automotive",
                "repair",
                "environmental",
                "air",
                "water",
                "waste",
            ],
        },
        {
            "name": "Michigan EGLE — Environmental Rules",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/regulations",
            "source_type": "Michigan EGLE",
            "keywords": [
                "environmental",
                "regulation",
                "rules",
                "Michigan",
            ],
        },
    ],

    "Stormwater and water discharges": [
        {
            "name": "eCFR — 40 CFR Part 122",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-122",
            "source_type": "eCFR",
            "keywords": [
                "stormwater",
                "water discharge",
                "discharge",
                "water",
                "runoff",
                "permit",
            ],
        },
        {
            "name": "Michigan EGLE — Automotive Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "source_type": "Michigan EGLE",
            "keywords": [
                "water",
                "stormwater",
                "automotive",
                "repair",
                "discharge",
            ],
        },
    ],
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(text: str) -> str:
    """Remove HTML and normalize whitespace."""
    if not text:
        return ""

    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)

    replacements = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def score_relevance(text: str, business_description: str) -> int:
    """Simple deterministic relevance score."""
    haystack = (
        f"{business_description} {text}"
    ).lower()

    score = 0

    important_terms = [
        "shall",
        "must",
        "required",
        "applicable",
        "applicability",
        "notification",
        "recordkeeping",
        "training",
        "storage",
        "disposal",
        "emission",
        "hazardous",
        "paint",
        "coating",
        "waste",
        "permit",
    ]

    for term in important_terms:
        if term in haystack:
            score += 2

    return score


def detect_topics(business_description: str) -> List[str]:
    """Determine which regulatory topic groups are relevant."""
    text = business_description.lower()

    topic_keywords = {
        "Hazardous waste": [
            "hazardous waste",
            "waste",
            "spent solvent",
            "solvent",
            "waste oil",
            "chemical waste",
        ],
        "Materials storage and releases": [
            "storage",
            "container",
            "spill",
            "release",
            "chemical",
            "fuel",
        ],
        "Air emissions and VOCs": [
            "air",
            "emission",
            "voc",
            "paint",
            "spray",
            "coating",
            "solvent",
        ],
        "Paint and surface coating": [
            "paint",
            "painting",
            "spray",
            "surface coating",
            "auto body",
            "collision repair",
            "body shop",
        ],
        "General environmental requirements": [
            "automotive",
            "repair",
            "environmental",
            "business",
        ],
        "Stormwater and water discharges": [
            "stormwater",
            "runoff",
            "water discharge",
            "discharge",
            "drain",
            "wastewater",
        ],
    }

    matched = []

    for topic, keywords in topic_keywords.items():
        if any(keyword in text for keyword in keywords):
            matched.append(topic)

    if not matched:
        matched = ["General environmental requirements"]

    return matched


def ensure_playwright_browser() -> None:
    """
    Make sure the Playwright Chromium browser is actually installed.

    The Python package and browser executable are separate dependencies.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            executable = p.chromium.executable_path

        import os

        if os.path.exists(executable):
            return

    except Exception:
        pass

    subprocess.run(
        [
            sys.executable,
            "-m",
            "playwright",
            "install",
            "chromium",
        ],
        check=True,
    )


def scrape_page(url: str) -> str:
    """
    Retrieve a page using Playwright.

    Only URLs from the curated source catalog are used.
    """
    ensure_playwright_browser()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (compatible; EcoComply/1.0; "
                "+https://ecocomply.streamlit.app)"
            )
        )

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=45000,
            )

            page.wait_for_timeout(1000)

            text = page.locator("body").inner_text(
                timeout=15000
            )

            text = clean_text(text)

        finally:
            browser.close()

    # Reject obvious access/error pages.
    blocked_phrases = [
        "access denied",
        "request access",
        "403 forbidden",
        "404 not found",
        "captcha",
        "enable javascript",
        "checking your browser",
    ]

    lowered = text.lower()

    if any(phrase in lowered for phrase in blocked_phrases):
        return ""

    # Very small pages usually aren't useful regulatory evidence.
    if len(text) < 500:
        return ""

    return text


def build_source_catalog(topics: List[str]) -> List[Dict[str, Any]]:
    """Create a deduplicated source list."""
    sources = []
    seen_urls = set()

    for topic in topics:
        for source in REGULATORY_TOPICS.get(topic, []):
            if source["url"] not in seen_urls:
                copied = dict(source)
                copied["topic"] = topic
                sources.append(copied)
                seen_urls.add(source["url"])

    return sources


def retrieve_evidence(
    business_description: str,
    topics: List[str],
) -> List[Dict[str, Any]]:
    """
    Retrieve a bounded set of official sources.

    Limits are intentionally conservative so the LLM request stays
    within token limits.
    """
    catalog = build_source_catalog(topics)

    retrieved = []

    progress = st.progress(0)
    status = st.empty()

    total = len(catalog)

    for index, source in enumerate(catalog):
        status.info(
            f"Searching official sources... "
            f"{index + 1}/{total}: {source['name']}"
        )

        try:
            text = scrape_page(source["url"])

            if text:
                score = score_relevance(
                    text,
                    business_description,
                )

                # Keep a bounded excerpt.
                excerpt = text[:3500]

                retrieved.append(
                    {
                        "name": source["name"],
                        "url": source["url"],
                        "source_type": source["source_type"],
                        "topic": source["topic"],
                        "relevance_score": score,
                        "evidence": excerpt,
                    }
                )

        except Exception as exc:
            # A single failed source should not kill the entire research run.
            retrieved.append(
                {
                    "name": source["name"],
                    "url": source["url"],
                    "source_type": source["source_type"],
                    "topic": source["topic"],
                    "relevance_score": 0,
                    "evidence": "",
                    "error": str(exc),
                }
            )

        progress.progress(
            (index + 1) / max(total, 1)
        )

    status.empty()
    progress.empty()

    # Sort strongest evidence first.
    retrieved.sort(
        key=lambda item: item.get(
            "relevance_score",
            0
        ),
        reverse=True,
    )

    # Maximum six evidence sources.
    usable = [
        source
        for source in retrieved
        if source.get("evidence")
    ][:6]

    # Hard total evidence limit.
    max_total_chars = 17000
    final_sources = []
    total_chars = 0

    for source in usable:
        evidence = source["evidence"]

        remaining = max_total_chars - total_chars

        if remaining <= 0:
            break

        evidence = evidence[:remaining]

        copied = dict(source)
        copied["evidence"] = evidence

        final_sources.append(copied)

        total_chars += len(evidence)

    return final_sources


def extract_json(text: str) -> Dict[str, Any]:
    """Safely extract JSON from an LLM response."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL,
    )

    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(
        "The AI returned invalid structured data."
    )


def analyze_compliance(
    business_description: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:

    api_key = st.secrets.get(
        "GROQ_API_KEY",
        "",
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing from Streamlit secrets."
        )

    client = Groq(api_key=api_key)

    evidence_packet = []

    for source in evidence:
        evidence_packet.append(
            {
                "source": source["name"],
                "source_type": source["source_type"],
                "topic": source["topic"],
                "url": source["url"],
                "evidence": source["evidence"],
            }
        )

    packet_text = json.dumps(
        evidence_packet,
        ensure_ascii=False,
    )

    business_description = business_description[:4000]

    system_prompt = """
You are the analysis engine for EcoComply.

EcoComply performs preliminary environmental compliance research.

IMPORTANT RULES:

1. Use ONLY the regulatory evidence provided in the evidence packet.
2. Never invent a regulation, citation, deadline, penalty, exemption,
   threshold, requirement, agency, or URL.
3. Every requirement must cite one of the provided sources.
4. If the evidence does not establish something, say that it cannot
   be determined from the available evidence.
5. Do not claim that a business is legally compliant.
6. "Compliant" means the provided business evidence appears to satisfy
   the specific requirement based on the retrieved evidence.
7. Missing information should normally produce "Needs Review", not
   "Action Required".
8. "Action Required" should be used only when the evidence establishes
   that the business is missing or failing a requirement.
9. "Not Applicable" should only be used when the provided evidence
   clearly establishes that the requirement does not apply.
10. Keep requirements specific and traceable.
11. Do not make broad legal conclusions.

For every requirement provide:
- title
- status
- requirement
- citation
- regulatory_evidence
- business_evidence
- why_flagged
- recommended_action
- source_url

Return ONLY valid JSON.
"""

    user_prompt = f"""
BUSINESS DESCRIPTION:
{business_description}

REGULATORY EVIDENCE:
{packet_text}

Return JSON using exactly this structure:

{{
  "overall_status": "Compliant | Needs Review | Action Required",
  "summary": "short explanation",
  "requirements": [
    {{
      "title": "string",
      "status": "Compliant | Needs Review | Action Required | Not Applicable",
      "requirement": "string",
      "citation": "string",
      "regulatory_evidence": "string",
      "business_evidence": "string",
      "why_flagged": "string",
      "recommended_action": "string",
      "source_url": "string"
    }}
  ],
  "next_steps": [
    "string"
  ]
}}

Prioritize concrete, verifiable requirements over generic advice.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.1,
        max_tokens=4500,
    )

    content = response.choices[0].message.content

    result = extract_json(content)

    return result


def normalize_status(status: str) -> str:
    """Normalize status text for display."""
    if not status:
        return "Needs Review"

    normalized = status.strip().lower()

    mapping = {
        "compliant": "Compliant",
        "needs review": "Needs Review",
        "action required": "Action Required",
        "not applicable": "Not Applicable",
    }

    return mapping.get(
        normalized,
        "Needs Review",
    )


def status_icon(status: str) -> str:
    return {
        "Compliant": "✅",
        "Needs Review": "⚠️",
        "Action Required": "🔴",
        "Not Applicable": "➖",
    }.get(status, "⚠️")


def clean_requirement(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure every expected field exists."""
    return {
        "title": str(
            requirement.get(
                "title",
                "Untitled requirement",
            )
        ),
        "status": normalize_status(
            str(
                requirement.get(
                    "status",
                    "Needs Review",
                )
            )
        ),
        "requirement": str(
            requirement.get(
                "requirement",
                "Requirement could not be determined.",
            )
        ),
        "citation": str(
            requirement.get(
                "citation",
                "Not specified",
            )
        ),
        "regulatory_evidence": str(
            requirement.get(
                "regulatory_evidence",
                "No regulatory evidence provided.",
            )
        ),
        "business_evidence": str(
            requirement.get(
                "business_evidence",
                "No business evidence provided.",
            )
        ),
        "why_flagged": str(
            requirement.get(
                "why_flagged",
                "Additional evidence is needed.",
            )
        ),
        "recommended_action": str(
            requirement.get(
                "recommended_action",
                "Review the applicable requirement.",
            )
        ),
        "source_url": str(
            requirement.get(
                "source_url",
                "",
            )
        ),
    }


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Business profile")

    st.caption(
        "Describe what the business does. "
        "EcoComply uses this information to select relevant "
        "official regulatory sources."
    )

    preset = st.selectbox(
        "Example business",
        [
            "Custom",
            "Auto body shop",
            "Automotive repair shop",
            "Small manufacturing shop",
        ],
    )

    presets = {
        "Auto body shop": (
            "We operate an auto body repair shop. "
            "We repair damaged vehicles, perform sanding and painting, "
            "use spray application equipment, and store paints, solvents, "
            "and other automotive chemicals. "
            "We generate used solvent containers and other waste materials."
        ),
        "Automotive repair shop": (
            "We operate an automotive repair shop. "
            "We perform mechanical repairs, use automotive fluids and "
            "cleaning solvents, store chemicals and parts, and generate "
            "used fluids and other waste."
        ),
        "Small manufacturing shop": (
            "We operate a small manufacturing facility. "
            "We use paints, coatings, solvents, and other chemicals "
            "during production and store these materials on site. "
            "We generate industrial waste and may have air emissions."
        ),
    }

    default_description = presets.get(
        preset,
        "",
    )

    business_description = st.text_area(
        "Business description",
        value=default_description,
        height=230,
        placeholder=(
            "Example: We operate an auto body shop and paint "
            "damaged vehicles..."
        ),
    )

    st.divider()

    st.markdown(
        """
        **How EcoComply works**

        1. Understand the business
        2. Identify regulatory topics
        3. Retrieve official sources
        4. Extract regulatory evidence
        5. Analyze requirements
        6. Show the evidence chain
        """
    )

    run_analysis = st.button(
        "🔎 Run compliance research",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# INITIAL STATE
# ============================================================

if "assessment" not in st.session_state:
    st.session_state.assessment = None

if "sources" not in st.session_state:
    st.session_state.sources = []

if "topics" not in st.session_state:
    st.session_state.topics = []


# ============================================================
# RUN ANALYSIS
# ============================================================

if run_analysis:

    if not business_description.strip():
        st.error(
            "Please enter a business description first."
        )
        st.stop()

    try:
        # --------------------------------------------
        # 1. Identify topics
        # --------------------------------------------

        topics = detect_topics(
            business_description
        )

        st.session_state.topics = topics

        # --------------------------------------------
        # 2. Regulatory research
        # --------------------------------------------

        st.markdown(
            '<div class="section-label">Research</div>',
            unsafe_allow_html=True,
        )

        st.subheader(
            "🔎 Regulatory research"
        )

        st.write(
            "Targeted topics: "
            + ", ".join(topics)
        )

        with st.spinner(
            "Searching official regulatory sources..."
        ):
            sources = retrieve_evidence(
                business_description,
                topics,
            )

        st.session_state.sources = sources

        if not sources:
            st.error(
                "EcoComply could not retrieve usable regulatory "
                "evidence from the official sources."
            )
            st.stop()

        st.markdown(
            f"""
            <div class="research-success">
                <strong>✓ Research complete</strong><br>
                Retrieved {len(sources)} usable official source
                {"page" if len(sources) == 1 else "pages"}.
                The compliance analysis below is limited to this evidence.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # --------------------------------------------
        # 3. AI analysis
        # --------------------------------------------

        st.markdown(
            '<div class="section-label">Analysis</div>',
            unsafe_allow_html=True,
        )

        st.subheader(
            "📋 Compliance assessment"
        )

        with st.spinner(
            "Comparing business information against retrieved requirements..."
        ):
            assessment = analyze_compliance(
                business_description,
                sources,
            )

        st.session_state.assessment = assessment

    except Exception as exc:
        st.error(
            "EcoComply encountered an error while running the assessment."
        )

        with st.expander("Technical details"):
            st.code(str(exc))

        st.stop()


# ============================================================
# DISPLAY ASSESSMENT
# ============================================================

assessment = st.session_state.assessment
sources = st.session_state.sources
topics = st.session_state.topics


if assessment:

    overall_status = normalize_status(
        assessment.get(
            "overall_status",
            "Needs Review",
        )
    )

    requirements = [
        clean_requirement(req)
        for req in assessment.get(
            "requirements",
            [],
        )
    ]

    next_steps = assessment.get(
        "next_steps",
        [],
    )

    # --------------------------------------------
    # Summary
    # --------------------------------------------

    st.markdown(
        '<div class="section-label">Assessment</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        "📋 Compliance assessment"
    )

    col1, col2, col3, col4 = st.columns(4)

    compliant_count = sum(
        r["status"] == "Compliant"
        for r in requirements
    )

    review_count = sum(
        r["status"] == "Needs Review"
        for r in requirements
    )

    action_count = sum(
        r["status"] == "Action Required"
        for r in requirements
    )

    with col1:
        st.markdown(
            f"""
            <div class="status-card">
                <div class="label">Overall</div>
                <div class="value">
                    {status_icon(overall_status)}
                    {overall_status}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="status-card">
                <div class="label">Requirements</div>
                <div class="value">{len(requirements)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="status-card">
                <div class="label">Action Required</div>
                <div class="value">{action_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="status-card">
                <div class="label">Needs Review</div>
                <div class="value">{review_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Summary")

    st.write(
        assessment.get(
            "summary",
            "No summary was returned.",
        )
    )

    # --------------------------------------------
    # Evidence chain explanation
    # --------------------------------------------

    st.markdown("### 🧠 How EcoComply reached these results")

    st.caption(
        "EcoComply does not simply ask an AI model whether the business "
        "is compliant. Each finding follows an evidence chain."
    )

    chain1, chain2, chain3, chain4 = st.columns(4)

    with chain1:
        st.markdown(
            """
            **1. Business evidence**

            What the business says it does.
            """
        )

    with chain2:
        st.markdown(
            """
            **2. Regulatory evidence**

            What an official source requires.
            """
        )

    with chain3:
        st.markdown(
            """
            **3. Gap analysis**

            Whether the available business information
            establishes that requirement.
            """
        )

    with chain4:
        st.markdown(
            """
            **4. Next step**

            What information or action is needed.
            """
        )

    # --------------------------------------------
    # Requirements
    # --------------------------------------------

    st.markdown("### 📑 Regulatory requirements")

    if not requirements:
        st.warning(
            "No specific requirements were produced from the retrieved evidence."
        )

    for index, req in enumerate(requirements, start=1):

        status = req["status"]

        with st.container():

            st.markdown(
                f"""
                <div class="requirement-card">
                    <div class="requirement-title">
                        {status_icon(status)}
                        {req["title"]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"**Status:** {status}"
            )

            st.markdown(
                f"**Requirement**  \n{req['requirement']}"
            )

            st.markdown(
                f"**Citation**  \n`{req['citation']}`"
            )

            evidence_col, business_col = st.columns(2)

            with evidence_col:
                st.markdown(
                    "#### 📜 Regulatory evidence"
                )

                st.markdown(
                    f"""
                    <div class="evidence-box">
                        {req["regulatory_evidence"]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with business_col:
                st.markdown(
                    "#### 🏢 Business evidence"
                )

                st.markdown(
                    f"""
                    <div class="evidence-box">
                        {req["business_evidence"]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown(
                "#### 🔍 Why EcoComply flagged this"
            )

            st.write(
                req["why_flagged"]
            )

            st.markdown(
                "#### ➡️ Recommended action"
            )

            st.write(
                req["recommended_action"]
            )

            if req["source_url"]:
                st.markdown(
                    f"🔗 [Open official source]({req['source_url']})"
                )

            st.divider()

    # --------------------------------------------
    # Next steps
    # --------------------------------------------

    st.markdown(
        '<div class="section-label">Action plan</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        "➡️ Recommended next steps"
    )

    if next_steps:

        for step in next_steps:
            st.markdown(
                f"""
                <div class="next-step">
                    {step}
                </div>
                """,
                unsafe_allow_html=True,
            )

    else:
        st.info(
            "No additional next steps were generated."
        )

    # --------------------------------------------
    # Sources
    # --------------------------------------------

    st.markdown(
        '<div class="section-label">Evidence</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        "🔗 Retrieved official sources"
    )

    st.caption(
        "These are the sources EcoComply actually retrieved and supplied "
        "to the analysis engine."
    )

    for source in sources:

        score = source.get(
            "relevance_score",
            0,
        )

        st.markdown(
            f"""
            <div class="source-card">
                <div class="source-type">
                    {source["source_type"]}
                </div>
                <div class="source-title">
                    {source["name"]}
                </div>
                <div class="source-score">
                    Topic: {source["topic"]} ·
                    Relevance score: {score}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"[Open official source]({source['url']})"
        )

        with st.expander(
            "View retrieved evidence"
        ):
            st.write(
                source["evidence"]
            )

    # --------------------------------------------
    # Structured JSON
    # --------------------------------------------

    st.markdown(
        '<div class="section-label">Export</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        "🧾 Structured assessment data"
    )

    export_data = {
        "business_description": business_description,
        "targeted_topics": topics,
        "retrieved_sources": sources,
        "assessment": assessment,
    }

    json_data = json.dumps(
        export_data,
        indent=2,
        ensure_ascii=False,
    )

    st.download_button(
        label="⬇️ Download assessment JSON",
        data=json_data,
        file_name="ecocomply_assessment.json",
        mime="application/json",
        use_container_width=False,
    )

    with st.expander(
        "View raw JSON"
    ):
        st.code(
            json_data,
            language="json",
        )

    # --------------------------------------------
    # Limitations
    # --------------------------------------------

    st.markdown(
        '<div class="section-label">Transparency</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        "⚠️ Limitations"
    )

    st.markdown(
        """
        - EcoComply only evaluates requirements supported by the
          regulatory evidence it successfully retrieved.
        - Applicability can depend on details such as facility size,
          materials used, quantities, emissions, waste generation,
          permits, and operating practices.
        - A "Compliant" result means the provided information appears
          to satisfy the specific requirement based on the retrieved
          evidence; it is not a legal determination.
        - "Needs Review" means EcoComply does not have enough evidence
          to establish the requirement from the information provided.
        - EcoComply does not replace professional legal or environmental
          compliance advice.
        """
    )

else:

    # ========================================================
    # LANDING STATE
    # ========================================================

    st.markdown(
        "### Start a compliance assessment"
    )

    st.write(
        "Describe a business in the sidebar, then run EcoComply's "
        "regulatory research."
    )

    st.info(
        "EcoComply retrieves regulatory information from curated "
        "official sources such as the eCFR, EPA, and Michigan EGLE."
    )

    st.markdown(
        """
        **What makes EcoComply different**

        **🔎 Evidence retrieval**  
        Official regulatory pages are retrieved instead of relying
        solely on the model's existing knowledge.

        **📜 Traceable requirements**  
        Findings are tied to specific regulatory citations and
        source pages.

        **🧠 Evidence-based analysis**  
        The AI receives the retrieved evidence and compares it
        against the business description.

        **⚠️ Uncertainty handling**  
        When the available information is insufficient, EcoComply
        says **Needs Review** instead of pretending to know.

        **➡️ Actionable results**  
        Each finding includes a recommended next step.
        """
    )

    st.markdown(
        """
        <div class="disclaimer">
            <strong>Important:</strong>
            EcoComply provides a preliminary educational assessment.
            It does not replace professional legal or environmental
            compliance advice.
        </div>
        """,
        unsafe_allow_html=True,
    )
