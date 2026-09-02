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
)


# ============================================================
# HEADER
# ============================================================

st.title("🌱 EcoComply")
st.write(
    "Evidence-based environmental compliance research for small businesses. "
    "EcoComply retrieves official regulatory sources, identifies relevant "
    "requirements, and shows why each result was flagged."
)


# ============================================================
# REGULATORY SOURCE CATALOG
# ============================================================
#
# Authority levels:
# 3 = direct regulation / eCFR
# 2 = official EPA/EGLE guidance
# 1 = general overview
#
# Direct regulations are deliberately ranked above general
# informational pages.
# ============================================================

REGULATORY_TOPICS = {
    "Hazardous waste": [
        {
            "title": "40 CFR Part 262 — Standards Applicable to Generators of Hazardous Waste",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-262",
            "authority": 3,
            "keywords": [
                "hazardous waste",
                "generator",
                "manifest",
                "container",
                "storage",
                "label",
                "accumulation",
            ],
        },
        {
            "title": "40 CFR Part 261 — Identification and Listing of Hazardous Waste",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-261",
            "authority": 3,
            "keywords": [
                "hazardous waste",
                "listed waste",
                "characteristic",
                "ignitable",
                "corrosive",
                "reactive",
                "toxic",
            ],
        },
        {
            "title": "Michigan EGLE — Hazardous Waste",
            "url": "https://www.michigan.gov/egle/about/organization/materials-management/hazardous-waste",
            "authority": 2,
            "keywords": [
                "hazardous waste",
                "generator",
                "storage",
                "disposal",
                "manifest",
            ],
        },
        {
            "title": "Michigan EGLE — Hazardous Waste Disposal Guidance",
            "url": "https://www.michigan.gov/egle/about/organization/materials-management/hazardous-waste/liquid-industrial-byproducts/hw-disposal-guidance",
            "authority": 2,
            "keywords": [
                "hazardous waste",
                "disposal",
                "waste",
                "manifest",
                "container",
            ],
        },
    ],

    "Materials storage and releases": [
        {
            "title": "40 CFR Part 262 — Hazardous Waste Generator Requirements",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-262",
            "authority": 3,
            "keywords": [
                "storage",
                "container",
                "hazardous waste",
                "release",
                "generator",
                "accumulation",
            ],
        },
        {
            "title": "Michigan EGLE — Automotive Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "authority": 2,
            "keywords": [
                "automotive",
                "repair",
                "environmental",
                "storage",
                "waste",
                "release",
            ],
        },
        {
            "title": "Michigan EGLE — Environmental Rules",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/regulations",
            "authority": 2,
            "keywords": [
                "environmental",
                "rules",
                "regulations",
                "air",
                "water",
                "waste",
            ],
        },
    ],

    "Air emissions and VOCs": [
        {
            "title": "40 CFR § 63.11170 — Applicability of Subpart HHHHHH",
            "url": "https://www.ecfr.gov/current/title-40/section-63.11170",
            "authority": 3,
            "keywords": [
                "applicability",
                "motor vehicle",
                "spray application",
                "coating",
                "paint",
                "target HAP",
            ],
        },
        {
            "title": "40 CFR § 63.11173 — General Requirements for Subpart HHHHHH",
            "url": "https://www.ecfr.gov/current/title-40/section-63.11173",
            "authority": 3,
            "keywords": [
                "general requirements",
                "management practices",
                "paint stripping",
                "spray",
                "training",
                "methylene chloride",
            ],
        },
        {
            "title": "40 CFR § 63.11175 — Notifications",
            "url": "https://www.ecfr.gov/current/title-40/section-63.11175",
            "authority": 3,
            "keywords": [
                "notification",
                "initial notification",
                "compliance notification",
            ],
        },
        {
            "title": "40 CFR § 63.11177 — Records",
            "url": "https://www.ecfr.gov/current/title-40/section-63.11177",
            "authority": 3,
            "keywords": [
                "records",
                "recordkeeping",
                "records required",
            ],
        },
        {
            "title": "EPA — About EPA's Auto Body Rule",
            "url": "https://www.epa.gov/collision-repair-campaign/about-epas-auto-body-rule",
            "authority": 2,
            "keywords": [
                "auto body",
                "paint stripping",
                "surface coating",
                "air emissions",
                "notification",
                "training",
            ],
        },
        {
            "title": "EPA — Paint Stripping and Miscellaneous Surface Coating Operations",
            "url": "https://www.epa.gov/stationary-sources-air-pollution/paint-stripping-and-miscellaneous-surface-coating-operations",
            "authority": 2,
            "keywords": [
                "surface coating",
                "paint stripping",
                "hazardous air pollutants",
                "VOC",
                "emissions",
            ],
        },
    ],

    "Paint and surface coating": [
        {
            "title": "40 CFR § 63.11170 — Applicability of Subpart HHHHHH",
            "url": "https://www.ecfr.gov/current/title-40/section-63.11170",
            "authority": 3,
            "keywords": [
                "surface coating",
                "motor vehicle",
                "spray application",
                "paint",
                "applicability",
            ],
        },
        {
            "title": "40 CFR § 63.11173 — General Requirements for Subpart HHHHHH",
            "url": "https://www.ecfr.gov/current/title-40/section-63.11173",
            "authority": 3,
            "keywords": [
                "paint stripping",
                "surface coating",
                "spray",
                "management practices",
                "training",
            ],
        },
        {
            "title": "EPA — About EPA's Auto Body Rule",
            "url": "https://www.epa.gov/collision-repair-campaign/about-epas-auto-body-rule",
            "authority": 2,
            "keywords": [
                "auto body",
                "surface coating",
                "paint stripping",
                "training",
                "notification",
            ],
        },
    ],

    "General environmental requirements": [
        {
            "title": "Michigan EGLE — Automotive Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "authority": 2,
            "keywords": [
                "automotive",
                "repair",
                "air",
                "water",
                "hazardous waste",
                "environmental",
            ],
        },
        {
            "title": "Michigan EGLE — Environmental Rules",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/regulations",
            "authority": 2,
            "keywords": [
                "environmental",
                "rules",
                "regulations",
                "air",
                "water",
                "waste",
            ],
        },
        {
            "title": "Michigan EGLE — Administrative Rules",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/regulations/administrative-rules",
            "authority": 2,
            "keywords": [
                "administrative rules",
                "environmental",
                "regulations",
                "rules",
            ],
        },
    ],

    "Stormwater and water discharges": [
        {
            "title": "40 CFR Part 122 — EPA Administered Permit Programs",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-122",
            "authority": 3,
            "keywords": [
                "stormwater",
                "discharge",
                "water",
                "permit",
                "pollutant",
            ],
        },
        {
            "title": "Michigan EGLE — Automotive Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "authority": 2,
            "keywords": [
                "water",
                "stormwater",
                "discharge",
                "automotive",
                "repair",
            ],
        },
    ],
}


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_text(text: str) -> str:
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

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_status(status: str) -> str:
    value = str(status or "").strip().lower()

    if "action" in value:
        return "Action Required"

    if "not applicable" in value or value == "n/a":
        return "Not Applicable"

    if "compliant" in value:
        return "Compliant"

    return "Needs Review"


# ============================================================
# RELEVANCE SCORING
# ============================================================

IMPORTANT_TERMS = [
    "must",
    "shall",
    "required",
    "requirement",
    "applicable",
    "applicability",
    "notification",
    "record",
    "recordkeeping",
    "training",
    "certification",
    "container",
    "storage",
    "disposal",
    "management practice",
    "emission",
    "spray",
    "coating",
    "paint stripping",
    "hazardous waste",
    "generator",
    "manifest",
]


def score_relevance(
    text: str,
    keywords: List[str],
    business_description: str,
) -> int:

    lower = text.lower()
    score = 0

    for keyword in keywords:
        if keyword.lower() in lower:
            score += 3

    for term in IMPORTANT_TERMS:
        if term in lower:
            score += 1

    business_words = re.findall(
        r"[a-zA-Z]{4,}",
        business_description.lower(),
    )

    for word in set(business_words):
        if word in lower:
            score += 1

    return score


# ============================================================
# LOCAL EVIDENCE EXTRACTION
# ============================================================

def extract_relevant_passages(
    text: str,
    keywords: List[str],
    business_description: str,
    max_chars: int = 1800,
) -> str:

    text = clean_text(text)

    if not text:
        return ""

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    scored = []

    for sentence in sentences:

        sentence = sentence.strip()

        if len(sentence) < 40:
            continue

        lower = sentence.lower()
        score = 0

        for keyword in keywords:
            if keyword.lower() in lower:
                score += 5

        for term in IMPORTANT_TERMS:
            if term in lower:
                score += 2

        if re.search(
            r"\b(shall|must|required|applicable|notification)\b",
            lower,
        ):
            score += 4

        if score > 0:
            scored.append(
                (score, sentence)
            )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected = []
    total = 0

    for _, sentence in scored:

        sentence = sentence[:450]

        if total + len(sentence) > max_chars:
            break

        selected.append(
            sentence
        )

        total += len(sentence)

        if len(selected) >= 7:
            break

    return "\n".join(
        f"- {sentence}"
        for sentence in selected
    )


# ============================================================
# PLAYWRIGHT
# ============================================================

@st.cache_resource(show_spinner=False)
def ensure_playwright_browser() -> str:

    try:

        with sync_playwright() as p:

            path = p.chromium.executable_path

            if os.path.exists(path):
                return path

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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    with sync_playwright() as p:

        path = p.chromium.executable_path

        if not os.path.exists(path):
            raise RuntimeError(
                "Playwright installed Chromium but the browser "
                "executable could not be found."
            )

        return path


def scrape_page(url: str) -> str:

    browser_path = ensure_playwright_browser()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            executable_path=browser_path,
            headless=True,
        )

        page = browser.new_page(
            user_agent=(
                "EcoComply/1.0 "
                "(educational environmental compliance research tool)"
            )
        )

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(1200)

            text = page.locator(
                "body"
            ).inner_text()

            return clean_text(text)

        finally:
            browser.close()


# ============================================================
# TOPIC DETECTION
# ============================================================

TOPIC_KEYWORDS = {
    "Hazardous waste": [
        "hazardous waste",
        "solvent",
        "used solvent",
        "waste paint",
        "waste thinner",
        "manifest",
        "waste container",
        "chemical waste",
    ],

    "Materials storage and releases": [
        "storage",
        "chemical",
        "solvent",
        "release",
        "spill",
        "container",
        "materials",
    ],

    "Air emissions and VOCs": [
        "voc",
        "volatile organic compound",
        "air emission",
        "air emissions",
        "spray",
        "paint",
        "coating",
        "solvent",
    ],

    "Paint and surface coating": [
        "paint",
        "painting",
        "surface coating",
        "spray booth",
        "spray application",
        "paint stripping",
    ],

    "General environmental requirements": [
        "environmental",
        "compliance",
        "automotive repair",
        "repair shop",
        "regulations",
    ],

    "Stormwater and water discharges": [
        "stormwater",
        "storm water",
        "water discharge",
        "discharge",
        "drain",
        "wastewater",
    ],
}


def detect_topics(
    description: str,
) -> List[str]:

    lower = description.lower()
    detected = []

    for topic, keywords in TOPIC_KEYWORDS.items():

        if any(
            keyword in lower
            for keyword in keywords
        ):
            detected.append(topic)

    if not detected:

        detected = [
            "General environmental requirements",
            "Hazardous waste",
        ]

    return detected


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

            url = source["url"]

            if url in seen_urls:
                continue

            seen_urls.add(url)

            item = dict(source)
            item["topic"] = topic

            sources.append(item)

    return sources


# ============================================================
# EVIDENCE RETRIEVAL
# ============================================================

def retrieve_evidence(
    business_description: str,
    topics: List[str],
) -> List[Dict[str, Any]]:

    catalog = build_source_catalog(topics)

    results = []

    progress = st.progress(0)

    status = st.empty()

    for index, source in enumerate(catalog):

        status.info(
            "Searching official source "
            f"{index + 1} of {len(catalog)}: "
            f"{source['title']}"
        )

        try:

            full_text = scrape_page(
                source["url"]
            )

            if len(full_text) < 250:
                continue

            blocked_phrases = [
                "access denied",
                "request blocked",
                "verify you are human",
                "captcha",
            ]

            if any(
                phrase in full_text.lower()
                for phrase in blocked_phrases
            ):
                continue

            score = score_relevance(
                full_text,
                source["keywords"],
                business_description,
            )

            evidence = extract_relevant_passages(
                full_text,
                source["keywords"],
                business_description,
            )

            if not evidence:
                continue

            results.append(
                {
                    "title": source["title"],
                    "url": source["url"],
                    "topic": source["topic"],
                    "authority": source["authority"],
                    "score": score,
                    "evidence": evidence,
                    "full_text": full_text,
                }
            )

        except Exception:
            continue

        progress.progress(
            (index + 1) / max(len(catalog), 1)
        )

    status.empty()
    progress.empty()

    # Authority boost:
    #
    # Direct regulations outrank guidance pages,
    # which outrank general overviews.
    for result in results:

        result["ranking_score"] = (
            result["score"]
            + result["authority"] * 12
        )

    results.sort(
        key=lambda item: item["ranking_score"],
        reverse=True,
    )

    return results[:6]


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(
    text: str,
) -> Dict[str, Any]:

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:

        return json.loads(text)

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        flags=re.S,
    )

    if match:
        return json.loads(
            match.group(0)
        )

    raise ValueError(
        "The AI returned invalid JSON."
    )


# ============================================================
# CITATION VALIDATION
# ============================================================

def validate_requirement(
    requirement: Dict[str, Any],
    evidence_sources: List[Dict[str, Any]],
) -> Dict[str, Any]:

    citation = str(
        requirement.get(
            "citation",
            "",
        )
    ).strip()

    matched_source = None

    for source in evidence_sources:

        title = source["title"]

        if citation.lower() == title.lower():
            matched_source = source
            break

        if title.lower() in citation.lower():
            matched_source = source
            break

    if matched_source is None:

        requirement["citation"] = (
            "Retrieved official source"
        )

        requirement["citation_validated"] = False
        requirement["source_url"] = ""

    else:

        requirement["citation"] = (
            matched_source["title"]
        )

        requirement["citation_validated"] = True
        requirement["source_url"] = (
            matched_source["url"]
        )

    requirement["status"] = normalize_status(
        requirement.get(
            "status",
            "Needs Review",
        )
    )

    return requirement


def validate_analysis(
    analysis: Dict[str, Any],
    evidence_sources: List[Dict[str, Any]],
) -> Dict[str, Any]:

    requirements = analysis.get(
        "requirements",
        [],
    )

    if not isinstance(
        requirements,
        list,
    ):
        requirements = []

    validated = []

    for requirement in requirements:

        if not isinstance(
            requirement,
            dict,
        ):
            continue

        validated.append(
            validate_requirement(
                requirement,
                evidence_sources,
            )
        )

    analysis["requirements"] = validated

    counts = {
        "Compliant": 0,
        "Needs Review": 0,
        "Action Required": 0,
        "Not Applicable": 0,
    }

    for requirement in validated:

        status = requirement["status"]

        counts[status] += 1

    analysis["counts"] = counts

    if counts["Action Required"] > 0:

        analysis["overall_status"] = (
            "Action Required"
        )

    elif counts["Needs Review"] > 0:

        analysis["overall_status"] = (
            "Needs Review"
        )

    elif counts["Compliant"] > 0:

        analysis["overall_status"] = (
            "Compliant"
        )

    else:

        analysis["overall_status"] = (
            "Needs Review"
        )

    return analysis


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_compliance(
    business_description: str,
    evidence_sources: List[Dict[str, Any]],
) -> Dict[str, Any]:

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Add it to Streamlit secrets."
        )

    client = Groq(
        api_key=api_key
    )

    compact_sources = []

    for index, source in enumerate(
        evidence_sources,
        start=1,
    ):

        compact_sources.append(
            {
                "source_id": f"S{index}",
                "title": source["title"],
                "topic": source["topic"],
                "authority_level": source["authority"],
                "url": source["url"],
                "evidence": source["evidence"][:1400],
            }
        )

    business_description = (
        business_description[:2500]
    )

    system_prompt = """
You are EcoComply's environmental compliance analysis engine.

You receive:
1. A business description.
2. Evidence retrieved from official government sources.

Rules:

- Use ONLY the supplied evidence.
- Never invent a regulation, citation, deadline, penalty, form, permit,
  threshold, exemption, or requirement.
- Prefer direct eCFR regulatory sources over EPA or state guidance when
  making a specific legal requirement claim.
- An EPA/EGLE guidance page may establish that a topic is relevant,
  describe a program, or point to forms/resources, but do not turn
  general guidance into a specific legal obligation unless the evidence
  actually supports that conclusion.
- If the evidence is insufficient to establish a requirement, say so.
- Do not claim that a business is legally compliant.
- "Compliant" means the supplied business evidence appears to satisfy
  the supplied regulatory evidence.
- If the business provides no evidence about a requirement, use
  "Needs Review".
- "Action Required" should be used only when the supplied business
  evidence indicates a clear mismatch with a requirement.
- "Not Applicable" should only be used when the supplied evidence
  establishes that the requirement does not apply.
- Keep requirements focused and concrete.
- Cite a retrieved source by its exact title.
- The source URL must come from the supplied evidence.
- Distinguish between:
    A. what the source explicitly requires,
    B. what the source describes or recommends,
    C. what EcoComply cannot establish from the available business evidence.

Return JSON only.
"""

    user_prompt = f"""
BUSINESS DESCRIPTION:
{business_description}

OFFICIAL RETRIEVED EVIDENCE:
{json.dumps(compact_sources, separators=(",", ":"))}

Return this structure:

{{
  "summary": "2-4 sentence assessment",
  "requirements": [
    {{
      "name": "short requirement name",
      "status": "Compliant | Needs Review | Action Required | Not Applicable",
      "requirement": "What the evidence establishes",
      "citation": "EXACT retrieved source title",
      "regulatory_evidence": "Short evidence-based explanation",
      "business_evidence": "What the business description establishes",
      "why_flagged": "Why EcoComply reached this status",
      "recommended_action": "Specific next step supported by the evidence"
    }}
  ],
  "next_steps": [
    "short evidence-based next step"
  ]
}}

Create no more than 6 requirements.
"""

    estimated_input_tokens = (
        len(system_prompt)
        + len(user_prompt)
    ) // 4

    if estimated_input_tokens > 4800:

        raise RuntimeError(
            "The regulatory evidence packet was too large "
            "for the current API limit. Reduce the evidence "
            "packet and try again."
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
        max_tokens=2200,
        reasoning_effort="low",
    )

    raw = response.choices[0].message.content

    analysis = extract_json(raw)

    return validate_analysis(
        analysis,
        evidence_sources,
    )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "Business profile"
)

preset = st.sidebar.selectbox(
    "Start with a profile",
    [
        "Custom",
        "Auto body shop",
        "Automotive repair shop",
        "Small manufacturing shop",
    ],
)

PRESETS = {
    "Auto body shop": (
        "A small automotive collision repair shop that sands, paints, "
        "and refinishes vehicles. The shop uses spray equipment, paints, "
        "solvents, and other chemicals. It generates used solvent "
        "containers and other waste from repair and painting activities."
    ),

    "Automotive repair shop": (
        "A small automotive repair shop that performs mechanical repairs, "
        "uses oils, solvents, cleaners and other chemicals, and generates "
        "used automotive fluids and waste materials."
    ),

    "Small manufacturing shop": (
        "A small manufacturing business that uses paints, solvents, "
        "industrial chemicals and production materials. The facility "
        "generates process waste and stores chemical materials on site."
    ),
}


if preset != "Custom":

    default_description = (
        PRESETS[preset]
    )

else:

    default_description = ""


business_description = st.sidebar.text_area(
    "Describe the business",
    value=default_description,
    height=220,
    help=(
        "Describe activities, materials, waste, equipment, storage, "
        "and emissions. Do not include sensitive personal information."
    ),
)

st.sidebar.caption(
    "EcoComply performs preliminary educational research "
    "using retrieved official sources."
)


# ============================================================
# SESSION STATE
# ============================================================

if "analysis" not in st.session_state:
    st.session_state.analysis = None

if "sources" not in st.session_state:
    st.session_state.sources = []

if "topics" not in st.session_state:
    st.session_state.topics = []


# ============================================================
# RUN BUTTON
# ============================================================

run_analysis = st.button(
    "🔎 Research compliance",
    type="primary",
    use_container_width=True,
)


if run_analysis:

    if not business_description.strip():

        st.warning(
            "Please describe the business before starting the research."
        )

        st.stop()

    st.session_state.analysis = None
    st.session_state.sources = []
    st.session_state.topics = []

    topics = detect_topics(
        business_description
    )

    st.session_state.topics = topics

    st.header(
        "🔎 Regulatory research"
    )

    st.write(
        "Targeted topics: "
        + ", ".join(topics)
    )

    try:

        sources = retrieve_evidence(
            business_description,
            topics,
        )

        if not sources:

            st.error(
                "EcoComply could not retrieve usable official "
                "regulatory evidence for this business description."
            )

            st.stop()

        st.session_state.sources = sources

        st.success(
            f"Research complete — retrieved {len(sources)} usable "
            "official sources. Relevant passages were extracted "
            "locally before the AI analysis."
        )

    except Exception as exc:

        st.error(
            "Regulatory retrieval failed."
        )

        st.exception(exc)

        st.stop()

    try:

        with st.spinner(
            "Analyzing the retrieved regulatory evidence..."
        ):

            analysis = analyze_compliance(
                business_description,
                st.session_state.sources,
            )

        st.session_state.analysis = analysis

    except Exception as exc:

        st.error(
            "The compliance analysis could not be completed."
        )

        st.exception(exc)

        st.stop()


# ============================================================
# RESULTS
# ============================================================

analysis = st.session_state.analysis
sources = st.session_state.sources
topics = st.session_state.topics


if analysis:

    st.header(
        "📋 Compliance assessment"
    )

    counts = analysis.get(
        "counts",
        {
            "Compliant": 0,
            "Needs Review": 0,
            "Action Required": 0,
            "Not Applicable": 0,
        },
    )

    overall = analysis.get(
        "overall_status",
        "Needs Review",
    )

    requirements = analysis.get(
        "requirements",
        [],
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Overall",
            overall,
        )

    with col2:

        st.metric(
            "Requirements",
            len(requirements),
        )

    with col3:

        st.metric(
            "Needs Review",
            counts.get(
                "Needs Review",
                0,
            ),
        )

    with col4:

        st.metric(
            "Action Required",
            counts.get(
                "Action Required",
                0,
            ),
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "Assessment summary"
    )

    st.write(
        analysis.get(
            "summary",
            "No summary was returned.",
        )
    )

    # --------------------------------------------------------
    # EVIDENCE COVERAGE
    # --------------------------------------------------------

    st.subheader(
        "📊 Evidence coverage"
    )

    st.info(
        f"EcoComply evaluated {len(requirements)} requirements "
        f"using {len(sources)} retrieved official sources."
    )

    validated_count = sum(
        1
        for requirement in requirements
        if requirement.get(
            "citation_validated"
        )
    )

    st.caption(
        f"{validated_count} of {len(requirements)} "
        "requirement citations were matched to a retrieved source."
    )

    # --------------------------------------------------------
    # EVIDENCE CHAIN
    # --------------------------------------------------------

    st.subheader(
        "🔗 How EcoComply reached these results"
    )

    chain_col1, chain_col2 = st.columns(2)

    with chain_col1:

        st.markdown(
            "**1. Business evidence**"
        )

        st.write(
            "What the business description says it does."
        )

        st.markdown(
            "**2. Regulatory evidence**"
        )

        st.write(
            "What an official government source says, "
            "requires, or describes."
        )

    with chain_col2:

        st.markdown(
            "**3. Gap analysis**"
        )

        st.write(
            "Whether the available business evidence establishes "
            "that requirement."
        )

        st.markdown(
            "**4. Next step**"
        )

        st.write(
            "What additional evidence or action would resolve "
            "the uncertainty."
        )

    # --------------------------------------------------------
    # REQUIREMENTS
    # --------------------------------------------------------

    st.subheader(
        "Regulatory requirements"
    )

    if not requirements:

        st.info(
            "No specific requirements were generated from "
            "the retrieved evidence."
        )

    for number, requirement in enumerate(
        requirements,
        start=1,
    ):

        name = requirement.get(
            "name",
            "Unnamed requirement",
        )

        status = normalize_status(
            requirement.get(
                "status",
                "Needs Review",
            )
        )

        st.markdown(
            f"### {number}. {name}"
        )

        if status == "Compliant":

            st.success(
                "Status: Compliant"
            )

        elif status == "Action Required":

            st.error(
                "Status: Action Required"
            )

        elif status == "Not Applicable":

            st.info(
                "Status: Not Applicable"
            )

        else:

            st.warning(
                "Status: Needs Review"
            )

        st.markdown(
            "**Requirement**"
        )

        st.write(
            requirement.get(
                "requirement",
                "No requirement description returned.",
            )
        )

        st.markdown(
            "**Citation**"
        )

        citation = requirement.get(
            "citation",
            "Retrieved official source",
        )

        citation_validated = requirement.get(
            "citation_validated",
            False,
        )

        source_url = requirement.get(
            "source_url",
            "",
        )

        if citation_validated and source_url:

            st.markdown(
                f"[{citation}]({source_url})"
            )

        else:

            st.warning(
                "EcoComply could not validate this citation "
                "against the retrieved source list."
            )

        st.markdown(
            "**Regulatory evidence**"
        )

        st.write(
            requirement.get(
                "regulatory_evidence",
                "No regulatory evidence explanation returned.",
            )
        )

        st.markdown(
            "**Business evidence**"
        )

        st.write(
            requirement.get(
                "business_evidence",
                "No business evidence was provided.",
            )
        )

        st.markdown(
            "**Why flagged**"
        )

        st.write(
            requirement.get(
                "why_flagged",
                "No explanation returned.",
            )
        )

        st.markdown(
            "**Recommended next step**"
        )

        st.write(
            requirement.get(
                "recommended_action",
                "Obtain additional evidence before drawing "
                "a conclusion.",
            )
        )

        st.divider()

    # --------------------------------------------------------
    # ACTION PLAN
    # --------------------------------------------------------

    next_steps = analysis.get(
        "next_steps",
        [],
    )

    st.subheader(
        "🛠️ Action plan"
    )

    if next_steps:

        for step in next_steps:

            st.markdown(
                f"- {step}"
            )

    else:

        st.write(
            "No additional next steps were generated."
        )

    # --------------------------------------------------------
    # SOURCES
    # --------------------------------------------------------

    st.subheader(
        "📚 Retrieved official sources"
    )

    for source in sources:

        authority = source.get(
            "authority",
            1,
        )

        if authority >= 3:

            authority_text = (
                "Direct regulation"
            )

        elif authority == 2:

            authority_text = (
                "Official guidance"
            )

        else:

            authority_text = (
                "Overview"
            )

        with st.expander(
            source["title"]
        ):

            st.write(
                f"**Topic:** {source['topic']}"
            )

            st.write(
                f"**Source type:** {authority_text}"
            )

            st.write(
                f"**Retrieval score:** {source['score']}"
            )

            st.markdown(
                f"[Open official source]({source['url']})"
            )

            st.markdown(
                "**Retrieved evidence:**"
            )

            st.write(
                source["evidence"]
            )

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    st.subheader(
        "💾 Export"
    )

    export_data = {
        "app": "EcoComply",
        "business_description": business_description,
        "targeted_topics": topics,
        "overall_status": overall,
        "requirements": requirements,
        "next_steps": next_steps,
        "retrieved_sources": [
            {
                "title": source["title"],
                "url": source["url"],
                "topic": source["topic"],
                "authority": source["authority"],
                "retrieval_score": source["score"],
                "evidence": source["evidence"],
            }
            for source in sources
        ],
    }

    st.download_button(
        "Download assessment JSON",
        data=json.dumps(
            export_data,
            indent=2,
        ),
        file_name="ecocomply_assessment.json",
        mime="application/json",
        use_container_width=True,
    )

    # --------------------------------------------------------
    # LIMITATIONS
    # --------------------------------------------------------

    st.subheader(
        "⚠️ Important limitations"
    )

    st.info(
        "EcoComply provides a preliminary educational assessment "
        "based on the business information and official sources it "
        "retrieved. It does not establish legal compliance, replace "
        "professional environmental or legal advice, or guarantee "
        "that every requirement applicable to a facility has been "
        "identified."
    )


# ============================================================
# LANDING PAGE
# ============================================================

else:

    st.header(
        "How it works"
    )

    st.markdown(
        """
        **1. Describe the business**

        Tell EcoComply what the business does, what materials it uses,
        and what wastes or emissions it produces.

        **2. Retrieve official sources**

        EcoComply searches a controlled catalog of official eCFR, EPA,
        and Michigan EGLE sources.

        **3. Extract evidence**

        Relevant passages are selected locally before they are sent to
        the AI, keeping the analysis focused and reducing unnecessary
        API usage.

        **4. Analyze the gaps**

        EcoComply compares the business evidence against the retrieved
        regulatory evidence.

        **5. Show the evidence trail**

        Generated requirements are connected to the retrieved source
        used to support them.
        """
    )

    st.header(
        "🧭 Evidence hierarchy"
    )

    st.write(
        "EcoComply prioritizes evidence in this order:"
    )

    st.markdown(
        """
        **Direct regulation → Official agency guidance → General overview**
        """
    )

    st.write(
        "This helps prevent a broad informational page from being "
        "treated as if it were the exact legal text of a requirement."
    )

    st.header(
        "🚀 Ready to research?"
    )

    st.write(
        "Choose a business profile or enter your own description in "
        "the sidebar, then select **Research compliance**."
    )
