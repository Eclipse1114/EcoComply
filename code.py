import json
import os
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
            font-size: 1.55rem;
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
            Evidence-based environmental compliance research for small
            businesses. EcoComply retrieves official regulatory sources,
            identifies relevant requirements, and shows why each result
            was flagged.
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
                "generator",
            ],
        },
        {
            "name": "eCFR — 40 CFR Part 262",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-262",
            "source_type": "eCFR",
            "keywords": [
                "hazardous waste",
                "generator",
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
# TEXT HELPERS
# ============================================================

def clean_text(text: str) -> str:
    """Remove HTML and normalize whitespace."""

    if not text:
        return ""

    text = re.sub(
        r"<script.*?</script>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<style.*?</style>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

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

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def score_relevance(
    text: str,
    business_description: str,
    keywords: List[str],
) -> int:
    """
    Deterministic relevance score.

    This happens locally, before the AI sees the evidence.
    """

    haystack = (
        f"{business_description} {text}"
    ).lower()

    score = 0

    for keyword in keywords:
        if keyword.lower() in haystack:
            score += 4

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
            score += 1

    return score


def extract_relevant_passages(
    text: str,
    business_description: str,
    keywords: List[str],
) -> str:
    """
    Extract only small, relevant portions of a retrieved page.

    This is the key token-saving step.

    Instead of sending thousands of characters from every page to
    the model, we select a handful of sentences surrounding terms
    relevant to the business/topic.
    """

    if not text:
        return ""

    # Split into sentence-ish chunks.
    chunks = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    if len(chunks) <= 1:
        chunks = [
            text[i:i + 500]
            for i in range(
                0,
                len(text),
                500,
            )
        ]

    keyword_set = [
        keyword.lower()
        for keyword in keywords
    ]

    important_terms = [
        "shall",
        "must",
        "required",
        "applicable",
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
        "methylene chloride",
        "MeCl",
        "minimization",
    ]

    scored_chunks = []

    for index, chunk in enumerate(chunks):

        lowered = chunk.lower()

        score = 0

        for keyword in keyword_set:
            if keyword in lowered:
                score += 5

        for term in important_terms:
            if term.lower() in lowered:
                score += 2

        # Business-specific terms get extra weight.
        business_words = re.findall(
            r"[a-zA-Z]{4,}",
            business_description.lower(),
        )

        for word in business_words[:50]:
            if word in lowered:
                score += 1

        if score > 0:
            scored_chunks.append(
                (
                    score,
                    index,
                    chunk,
                )
            )

    scored_chunks.sort(
        reverse=True
    )

    selected = []

    # Maximum 7 small passages per source.
    for _, index, chunk in scored_chunks[:7]:

        # Keep individual passages compact.
        chunk = chunk.strip()

        if len(chunk) > 450:
            chunk = chunk[:450].rsplit(
                " ",
                1,
            )[0] + "..."

        selected.append(
            (
                index,
                chunk,
            )
        )

    # Restore original order.
    selected.sort(
        key=lambda item: item[0]
    )

    result = " ".join(
        chunk
        for _, chunk in selected
    )

    # Absolute per-source cap.
    return result[:1800]


# ============================================================
# PLAYWRIGHT
# ============================================================

def ensure_playwright_browser() -> None:
    """
    Ensure the Chromium executable exists.

    The Playwright Python package and browser binaries are separate.
    """

    try:

        with sync_playwright() as p:

            executable = p.chromium.executable_path

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
    """Retrieve an official regulatory page with Playwright."""

    ensure_playwright_browser()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 "
                "(compatible; EcoComply/1.0)"
            )
        )

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=45000,
            )

            page.wait_for_timeout(1000)

            text = page.locator(
                "body"
            ).inner_text(
                timeout=15000
            )

            text = clean_text(text)

        finally:
            browser.close()

    blocked_phrases = [
        "access denied",
        "request access",
        "403 forbidden",
        "404 not found",
        "captcha",
        "checking your browser",
        "enable javascript",
    ]

    lowered = text.lower()

    if any(
        phrase in lowered
        for phrase in blocked_phrases
    ):
        return ""

    if len(text) < 500:
        return ""

    return text


# ============================================================
# TOPIC DETECTION
# ============================================================

def detect_topics(
    business_description: str,
) -> List[str]:

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

        if any(
            keyword in text
            for keyword in keywords
        ):
            matched.append(topic)

    if not matched:
        matched = [
            "General environmental requirements"
        ]

    return matched


# ============================================================
# SOURCE CATALOG
# ============================================================

def build_source_catalog(
    topics: List[str],
) -> List[Dict[str, Any]]:

    sources = []
    seen_urls = set()

    for topic in topics:

        for source in REGULATORY_TOPICS.get(
            topic,
            [],
        ):

            if source["url"] in seen_urls:
                continue

            copied = dict(source)
            copied["topic"] = topic

            sources.append(copied)
            seen_urls.add(
                source["url"]
            )

    return sources


# ============================================================
# EVIDENCE RETRIEVAL
# ============================================================

def retrieve_evidence(
    business_description: str,
    topics: List[str],
) -> List[Dict[str, Any]]:

    catalog = build_source_catalog(
        topics
    )

    retrieved = []

    progress = st.progress(0)
    status = st.empty()

    total = len(catalog)

    for index, source in enumerate(
        catalog
    ):

        status.info(
            f"Searching official sources... "
            f"{index + 1}/{total}: "
            f"{source['name']}"
        )

        try:

            full_text = scrape_page(
                source["url"]
            )

            if full_text:

                score = score_relevance(
                    full_text,
                    business_description,
                    source["keywords"],
                )

                relevant_passages = (
                    extract_relevant_passages(
                        full_text,
                        business_description,
                        source["keywords"],
                    )
                )

                if relevant_passages:

                    retrieved.append(
                        {
                            "name": source["name"],
                            "url": source["url"],
                            "source_type": source[
                                "source_type"
                            ],
                            "topic": source["topic"],
                            "relevance_score": score,
                            "evidence": relevant_passages,
                            "full_text": full_text,
                        }
                    )

        except Exception as exc:

            retrieved.append(
                {
                    "name": source["name"],
                    "url": source["url"],
                    "source_type": source[
                        "source_type"
                    ],
                    "topic": source["topic"],
                    "relevance_score": 0,
                    "evidence": "",
                    "full_text": "",
                    "error": str(exc),
                }
            )

        progress.progress(
            (index + 1) / max(total, 1)
        )

    status.empty()
    progress.empty()

    # Strongest sources first.
    retrieved.sort(
        key=lambda item: item.get(
            "relevance_score",
            0,
        ),
        reverse=True,
    )

    # Keep at most 5 sources in the AI evidence packet.
    usable = [
        source
        for source in retrieved
        if source.get("evidence")
    ][:5]

    return usable


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(
    text: str,
) -> Dict[str, Any]:

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
            return json.loads(
                match.group(0)
            )

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "The AI returned invalid JSON."
    )


# ============================================================
# AI ANALYSIS
# ============================================================

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
            "GROQ_API_KEY is missing from "
            "Streamlit secrets."
        )

    client = Groq(
        api_key=api_key
    )

    # --------------------------------------------------------
    # Build a deliberately SMALL evidence packet.
    #
    # This is intentionally kept far below the 8K TPM limit.
    # --------------------------------------------------------

    evidence_packet = []

    for source in evidence:

        evidence_packet.append(
            {
                "source": source["name"],
                "topic": source["topic"],
                "citation_source_url": source["url"],
                "evidence": source["evidence"][:1400],
            }
        )

    packet_text = json.dumps(
        evidence_packet,
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
    )

    business_description = (
        business_description[:2500]
    )

    system_prompt = """
You are EcoComply's environmental compliance analysis engine.

Use ONLY the evidence supplied by the application.

Rules:
- Never invent regulations, citations, deadlines, penalties,
  exemptions, thresholds, or requirements.
- Every requirement must cite a supplied source.
- Do not declare legal compliance.
- If information is missing, use "Needs Review".
- Use "Action Required" only when the supplied evidence shows
  the business is missing or failing a requirement.
- Use "Compliant" only when the business information appears
  to satisfy that specific requirement.
- Use "Not Applicable" only when the evidence clearly establishes
  that the requirement does not apply.
- Be concise.
- Return ONLY valid JSON.

For each requirement explain:
1. what the regulation requires,
2. what the business evidence says,
3. why the result was assigned,
4. what should happen next.
"""

    user_prompt = f"""
BUSINESS:
{business_description}

OFFICIAL REGULATORY EVIDENCE:
{packet_text}

Return exactly:

{{
  "overall_status": "Compliant | Needs Review | Action Required",
  "summary": "short summary",
  "requirements": [
    {{
      "title": "short title",
      "status": "Compliant | Needs Review | Action Required | Not Applicable",
      "requirement": "specific requirement",
      "citation": "specific citation",
      "regulatory_evidence": "short evidence passage",
      "business_evidence": "what the business information establishes",
      "why_flagged": "why this status was assigned",
      "recommended_action": "specific next step",
      "source_url": "URL from supplied evidence"
    }}
  ],
  "next_steps": [
    "specific next step"
  ]
}}

Keep the number of requirements focused on the most important
requirements supported by the supplied evidence.
"""

    # --------------------------------------------------------
    # Final request-size guard.
    #
    # This does NOT replace the evidence limits above. It is
    # simply an additional safety net.
    # --------------------------------------------------------

    estimated_input_tokens = (
        len(system_prompt)
        + len(user_prompt)
    ) // 4

    if estimated_input_tokens > 4500:
        raise RuntimeError(
            "The regulatory evidence packet is still too large. "
            "EcoComply stopped before sending an oversized AI request."
        )

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

        # Deliberately much smaller than before.
        # This keeps the total request comfortably below
        # the free/on-demand TPM budget.
        max_tokens=2200,

        # Reduce reasoning overhead for this structured task.
        reasoning_effort="low",
    )

    content = response.choices[0].message.content

    return extract_json(
        content
    )


# ============================================================
# DISPLAY HELPERS
# ============================================================

def normalize_status(
    status: str,
) -> str:

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


def status_icon(
    status: str,
) -> str:

    return {
        "Compliant": "✅",
        "Needs Review": "⚠️",
        "Action Required": "🔴",
        "Not Applicable": "➖",
    }.get(
        status,
        "⚠️",
    )


def clean_requirement(
    requirement: Dict[str, Any],
) -> Dict[str, Any]:

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

    st.header(
        "Business profile"
    )

    st.caption(
        "Describe what the business does. "
        "EcoComply uses this information to select "
        "relevant official regulatory sources."
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
            "We repair damaged vehicles, perform sanding "
            "and painting, use spray application equipment, "
            "and store paints, solvents, and other automotive "
            "chemicals. We generate used solvent containers "
            "and other waste materials."
        ),

        "Automotive repair shop": (
            "We operate an automotive repair shop. "
            "We perform mechanical repairs, use automotive "
            "fluids and cleaning solvents, store chemicals "
            "and parts, and generate used fluids and other waste."
        ),

        "Small manufacturing shop": (
            "We operate a small manufacturing facility. "
            "We use paints, coatings, solvents, and other "
            "chemicals during production and store these "
            "materials on site. We generate industrial waste "
            "and may have air emissions."
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
            "Example: We operate an auto body shop "
            "and paint damaged vehicles..."
        ),
    )

    st.divider()

    st.markdown(
        """
        **How EcoComply works**

        1. Understand the business
        2. Identify regulatory topics
        3. Retrieve official sources
        4. Extract relevant evidence
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
# SESSION STATE
# ============================================================

if "assessment" not in st.session_state:
    st.session_state.assessment = None

if "sources" not in st.session_state:
    st.session_state.sources = []

if "topics" not in st.session_state:
    st.session_state.topics = []


# ============================================================
# RUN
# ============================================================

if run_analysis:

    if not business_description.strip():

        st.error(
            "Please enter a business description first."
        )

        st.stop()

    try:

        # ----------------------------------------------------
        # TOPICS
        # ----------------------------------------------------

        topics = detect_topics(
            business_description
        )

        st.session_state.topics = topics

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

        # ----------------------------------------------------
        # RETRIEVAL
        # ----------------------------------------------------

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
                "EcoComply could not retrieve usable "
                "regulatory evidence from the official sources."
            )

            st.stop()

        st.markdown(
            f"""
            <div class="research-success">
                <strong>✓ Research complete</strong><br>
                Retrieved {len(sources)} usable official
                {"source" if len(sources) == 1 else "sources"}.
                Relevant passages were extracted locally before
                the AI analysis.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # ANALYSIS
        # ----------------------------------------------------

        st.markdown(
            '<div class="section-label">Analysis</div>',
            unsafe_allow_html=True,
        )

        st.subheader(
            "📋 Compliance assessment"
        )

        with st.spinner(
            "Comparing business information against "
            "retrieved requirements..."
        ):

            assessment = analyze_compliance(
                business_description,
                sources,
            )

        st.session_state.assessment = assessment

    except Exception as exc:

        st.error(
            "EcoComply encountered an error while running "
            "the assessment."
        )

        with st.expander(
            "Technical details"
        ):

            st.code(
                str(exc)
            )

        st.stop()


# ============================================================
# DISPLAY
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

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

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
                <div class="value">
                    {len(requirements)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:

        st.markdown(
            f"""
            <div class="status-card">
                <div class="label">Action Required</div>
                <div class="value">
                    {action_count}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:

        st.markdown(
            f"""
            <div class="status-card">
                <div class="label">Needs Review</div>
                <div class="value">
                    {review_count}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "### Summary"
    )

    st.write(
        assessment.get(
            "summary",
            "No summary was returned.",
        )
    )

    # --------------------------------------------------------
    # EVIDENCE CHAIN
    # --------------------------------------------------------

    st.markdown(
        "### 🧠 How EcoComply reached these results"
    )

    st.caption(
        "EcoComply does not simply ask an AI model whether "
        "the business is compliant. Each finding follows "
        "an evidence chain."
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

            Whether the available information
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

    # --------------------------------------------------------
    # REQUIREMENTS
    # --------------------------------------------------------

    st.markdown(
        "### 📑 Regulatory requirements"
    )

    if not requirements:

        st.warning(
            "No specific requirements were produced "
            "from the retrieved evidence."
        )

    for req in requirements:

        status = req["status"]

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
                f"[🔗 Open official source]({req['source_url']})"
            )

        st.divider()

    # --------------------------------------------------------
    # NEXT STEPS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # SOURCES
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-label">Evidence</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        "🔗 Retrieved official sources"
    )

    st.caption(
        "These are the sources EcoComply actually retrieved. "
        "Only relevant passages from them were sent to the "
        "analysis engine."
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
            "View evidence used by EcoComply"
        ):

            st.write(
                source["evidence"]
            )

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

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
        "retrieved_sources": [
            {
                "name": source["name"],
                "url": source["url"],
                "source_type": source["source_type"],
                "topic": source["topic"],
                "relevance_score": source[
                    "relevance_score"
                ],
                "evidence": source[
                    "evidence"
                ],
            }
            for source in sources
        ],
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
    )

    with st.expander(
        "View raw JSON"
    ):

        st.code(
            json_data,
            language="json",
        )

    # --------------------------------------------------------
    # LIMITATIONS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-label">Transparency</div>',
        unsafe_allow_html=True,
    )

    st.subheader(
        "⚠️ Limitations"
    )

    st.markdown(
        """
        - EcoComply evaluates requirements supported by the
          regulatory evidence it successfully retrieves.
        - Applicability can depend on details such as facility
          size, materials used, quantities, emissions, waste
          generation, permits, and operating practices.
        - A "Compliant" result means the provided information
          appears to satisfy the specific requirement based on
          the retrieved evidence. It is not a legal determination.
        - "Needs Review" means EcoComply does not have enough
          evidence to establish the requirement.
        - EcoComply does not replace professional legal or
          environmental compliance advice.
        """
    )

else:

    # ========================================================
    # LANDING PAGE
    # ========================================================

    st.markdown(
        "### Start a compliance assessment"
    )

    st.write(
        "Describe a business in the sidebar, then run "
        "EcoComply's regulatory research."
    )

    st.info(
        "EcoComply retrieves regulatory information from "
        "curated official sources such as the eCFR, EPA, "
        "and Michigan EGLE."
    )

    st.markdown(
        """
        **What makes EcoComply different**

        **🔎 Evidence retrieval**  
        Official regulatory pages are retrieved instead of
        relying solely on the model's existing knowledge.

        **📜 Traceable requirements**  
        Findings are tied to specific regulatory citations
        and source pages.

        **🧠 Evidence-based analysis**  
        The AI receives selected regulatory evidence and
        compares it against the business description.

        **⚠️ Uncertainty handling**  
        When the information is insufficient, EcoComply
        says **Needs Review** instead of pretending to know.

        **➡️ Actionable results**  
        Each finding includes a recommended next step.
        """
    )

    st.markdown(
        """
        <div class="disclaimer">
            <strong>Important:</strong>
            EcoComply provides a preliminary educational
            assessment. It does not replace professional
            legal or environmental compliance advice.
        </div>
        """,
        unsafe_allow_html=True,
    )
