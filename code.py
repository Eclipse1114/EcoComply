import streamlit as st
from groq import Groq
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import subprocess
import sys
import re
import json
import html


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="EcoComply",
    page_icon="🌱",
    layout="wide",
)


# ============================================================
# LIGHT UI
# ============================================================

st.markdown(
    """
    <style>
        .stApp {
            background-color: #ffffff;
            color: #1f2937;
        }

        [data-testid="stHeader"] {
            background-color: #ffffff;
        }

        [data-testid="stSidebar"] {
            background-color: #f8fafc;
        }

        h1, h2, h3 {
            color: #111827 !important;
        }

        p, li, label, span {
            color: #374151;
        }

        .source-card {
            border: 1px solid #d1d5db;
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 12px;
            background: #f9fafb;
        }

        .small-muted {
            color: #6b7280 !important;
            font-size: 0.85rem;
        }

        .status-card {
            border: 1px solid #d1d5db;
            border-radius: 10px;
            padding: 15px;
            background: #f9fafb;
            text-align: center;
        }

        .requirement-card {
            border: 1px solid #d1d5db;
            border-radius: 10px;
            padding: 18px;
            margin-bottom: 14px;
            background: #ffffff;
        }

        .citation {
            font-family: monospace;
            font-size: 0.9rem;
            color: #374151;
        }

        a {
            color: #2563eb !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_DOMAINS = {
    "ecfr.gov",
    "www.ecfr.gov",
    "epa.gov",
    "www.epa.gov",
    "michigan.gov",
    "www.michigan.gov",
}

BLOCKED_PAGE_PHRASES = [
    "request access",
    "access denied",
    "captcha",
    "verify you are human",
    "checking your browser",
    "robot check",
    "temporarily unavailable",
    "enable javascript",
]


# ============================================================
# REGULATORY SOURCE CATALOG
#
# These are deliberately specific official pages.
# EcoComply does NOT let the AI invent URLs.
# ============================================================

REGULATORY_TOPICS = {
    "Hazardous waste": [
        {
            "agency": "eCFR",
            "title": "40 CFR Part 261 — Identification and Listing of Hazardous Waste",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-261",
            "keywords": [
                "hazardous waste",
                "spent solvent",
                "solvent",
                "paint thinner",
                "waste paint",
                "discarded",
                "waste",
            ],
        },
        {
            "agency": "eCFR",
            "title": "40 CFR Part 262 — Standards Applicable to Generators of Hazardous Waste",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-262",
            "keywords": [
                "hazardous waste",
                "generator",
                "storage",
                "container",
                "drum",
                "label",
                "accumulation",
            ],
        },
        {
            "agency": "Michigan EGLE",
            "title": "Michigan EGLE — Hazardous Waste",
            "url": "https://www.michigan.gov/egle/about/organization/materials-management/hazardous-waste",
            "keywords": [
                "hazardous waste",
                "waste",
                "generator",
                "manifest",
                "storage",
            ],
        },
        {
            "agency": "Michigan EGLE",
            "title": "Michigan EGLE — Hazardous Waste Disposal Guidance",
            "url": "https://www.michigan.gov/egle/about/organization/materials-management/hazardous-waste/liquid-industrial-byproducts/hw-disposal-guidance",
            "keywords": [
                "solvent",
                "paint",
                "auto body",
                "waste",
                "hazardous",
            ],
        },
    ],

    "Materials storage and releases": [
        {
            "agency": "eCFR",
            "title": "40 CFR Part 264 — Standards for Owners and Operators of Hazardous Waste Treatment, Storage, and Disposal Facilities",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-I/part-264",
            "keywords": [
                "storage",
                "container",
                "drum",
                "spill",
                "release",
                "secondary containment",
                "hazardous material",
            ],
        },
        {
            "agency": "Michigan EGLE",
            "title": "Michigan EGLE — Environmental Assistance for the Auto Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "keywords": [
                "auto body",
                "automotive",
                "repair",
                "collision",
                "hazardous waste",
                "paint",
                "solvent",
            ],
        },
    ],

    "Air emissions and VOCs": [
        {
            "agency": "eCFR",
            "title": "40 CFR § 63.11169 — What This Subpart Covers",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11169",
            "keywords": [
                "paint",
                "surface coating",
                "paint stripping",
                "motor vehicle",
                "mobile equipment",
            ],
        },
        {
            "agency": "eCFR",
            "title": "40 CFR § 63.11170 — Am I Subject to This Subpart?",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11170",
            "keywords": [
                "paint",
                "surface coating",
                "spray",
                "motor vehicle",
                "auto body",
                "mobile equipment",
            ],
        },
        {
            "agency": "eCFR",
            "title": "40 CFR § 63.11173 — What Are My General Requirements for Complying With This Subpart?",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11173",
            "keywords": [
                "paint",
                "spray",
                "surface coating",
                "filter",
                "spray gun",
                "training",
            ],
        },
        {
            "agency": "eCFR",
            "title": "40 CFR § 63.11175 — What Notifications Must I Submit?",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11175",
            "keywords": [
                "notification",
                "paint",
                "surface coating",
                "auto body",
            ],
        },
        {
            "agency": "EPA",
            "title": "EPA — About EPA's Auto Body Rule",
            "url": "https://www.epa.gov/collision-repair-campaign/about-epas-auto-body-rule",
            "keywords": [
                "auto body",
                "collision repair",
                "paint",
                "surface coating",
                "6H",
            ],
        },
        {
            "agency": "Michigan EGLE",
            "title": "Michigan EGLE — Air Laws and Rules",
            "url": "https://www.michigan.gov/egle/about/organization/Air-Quality/laws-and-rules",
            "keywords": [
                "air",
                "VOC",
                "volatile organic",
                "emission",
                "paint",
                "coating",
            ],
        },
    ],

    "Paint and surface coating": [
        {
            "agency": "eCFR",
            "title": "40 CFR Subpart HHHHHH — Paint Stripping and Miscellaneous Surface Coating Operations",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH",
            "keywords": [
                "paint",
                "surface coating",
                "spray",
                "paint stripping",
                "motor vehicle",
                "auto body",
            ],
        },
        {
            "agency": "eCFR",
            "title": "40 CFR § 63.11170 — Applicability of the Auto Body Rule",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-63/subpart-HHHHHH/section-63.11170",
            "keywords": [
                "paint",
                "surface coating",
                "motor vehicle",
                "mobile equipment",
                "spray",
            ],
        },
        {
            "agency": "EPA",
            "title": "EPA — About EPA's Auto Body Rule",
            "url": "https://www.epa.gov/collision-repair-campaign/about-epas-auto-body-rule",
            "keywords": [
                "auto body",
                "paint",
                "surface coating",
                "collision repair",
            ],
        },
    ],

    "General environmental requirements": [
        {
            "agency": "Michigan EGLE",
            "title": "Michigan EGLE — Environmental Assistance for the Auto Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "keywords": [
                "auto body",
                "automotive",
                "repair",
                "environmental",
                "hazardous waste",
                "air",
                "water",
            ],
        },
        {
            "agency": "Michigan EGLE",
            "title": "Michigan Guide to Environmental Regulations",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/environmental-regulations-guide",
            "keywords": [
                "environmental",
                "regulation",
                "air",
                "water",
                "waste",
            ],
        },
        {
            "agency": "Michigan EGLE",
            "title": "Michigan EGLE — Environmental Rules and Regulations",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/regulations",
            "keywords": [
                "regulation",
                "rules",
                "environmental",
            ],
        },
    ],

    "Stormwater and water discharges": [
        {
            "agency": "eCFR",
            "title": "40 CFR Part 122 — EPA Administered Permit Programs",
            "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-122",
            "keywords": [
                "stormwater",
                "water discharge",
                "discharge",
                "runoff",
                "water",
            ],
        },
        {
            "agency": "Michigan EGLE",
            "title": "Michigan EGLE — Environmental Assistance for the Auto Repair Industry",
            "url": "https://www.michigan.gov/egle/regulatory-assistance/compliance-assistance/automotive-repair-industry",
            "keywords": [
                "water",
                "stormwater",
                "runoff",
                "automotive",
                "repair",
            ],
        },
    ],
}


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    """
    Remove HTML markup that an AI model may accidentally return.
    This fixes visible <strong>, <br>, <h1>, etc.
    """
    if value is None:
        return ""

    value = str(value)

    value = html.unescape(value)

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"</p\s*>",
        "\n\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
    )

    value = value.replace("\r\n", "\n")
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def normalize_url(url):
    if not url:
        return None

    url = url.strip()

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return None

    if parsed.netloc.lower() not in ALLOWED_DOMAINS:
        return None

    return url


def looks_like_blocked_page(text, title=""):
    combined = f"{title}\n{text}".lower()

    return any(
        phrase in combined
        for phrase in BLOCKED_PAGE_PHRASES
    )


def contains_regulatory_content(text):
    """
    Prevent generic access/landing pages from becoming evidence.
    We don't require every EGLE page to contain CFR text because
    agency guidance pages can still contain useful compliance
    information.
    """

    lowered = text.lower()

    regulatory_markers = [
        "cfr",
        "section",
        "shall",
        "must",
        "requirement",
        "requirements",
        "applicability",
        "hazardous waste",
        "surface coating",
        "emission",
        "generator",
        "notification",
    ]

    matches = sum(
        1 for marker in regulatory_markers
        if marker in lowered
    )

    return matches >= 2


# ============================================================
# PLAYWRIGHT INSTALLATION
# ============================================================

@st.cache_resource(show_spinner=False)
def ensure_playwright_browser():
    """
    Streamlit Community Cloud does not automatically install
    Playwright browser binaries when the Python package is installed.
    """

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            executable = p.chromium.executable_path

        # If the executable exists, we're done.
        import os

        if os.path.exists(executable):
            return executable

    except Exception:
        pass

    st.info(
        "First-time setup: installing the Chromium browser used by EcoComply..."
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "playwright",
            "install",
            "chromium",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Playwright could not install Chromium.\n\n"
            + result.stderr[-3000:]
        )

    with sync_playwright() as p:
        executable = p.chromium.executable_path

    if not os.path.exists(executable):
        raise RuntimeError(
            "Playwright reported that Chromium was installed, "
            "but the browser executable could not be found:\n"
            + executable
        )

    return executable


# ============================================================
# TOPIC DETECTION
# ============================================================

def detect_topics(business_description):
    """
    Determine which regulatory areas are worth researching.

    This is intentionally conservative. A topic is selected only
    when the business description contains relevant terms.
    """

    text = business_description.lower()

    detected = []

    topic_keywords = {
        "Hazardous waste": [
            "hazardous waste",
            "waste",
            "solvent",
            "paint thinner",
            "thinner",
            "discard",
            "spent",
            "drum",
        ],

        "Materials storage and releases": [
            "storage",
            "stored",
            "drum",
            "container",
            "spill",
            "release",
            "tank",
            "secondary containment",
        ],

        "Air emissions and VOCs": [
            "voc",
            "volatile organic",
            "emission",
            "air",
            "paint",
            "spray",
            "spray booth",
            "coating",
            "solvent",
        ],

        "Paint and surface coating": [
            "paint",
            "painting",
            "paint booth",
            "surface coating",
            "refinish",
            "refinishing",
            "spray",
            "automotive",
            "auto body",
            "collision repair",
        ],

        "General environmental requirements": [
            "environmental",
            "auto body",
            "automotive",
            "repair",
            "business",
            "facility",
        ],

        "Stormwater and water discharges": [
            "stormwater",
            "storm water",
            "runoff",
            "discharge",
            "wastewater",
            "water",
        ],
    }

    for topic, keywords in topic_keywords.items():

        if any(keyword in text for keyword in keywords):
            detected.append(topic)

    if not detected:
        detected.append("General environmental requirements")

    return detected


# ============================================================
# SCRAPER
# ============================================================

def scrape_page(page, source):
    """
    Retrieve one controlled official source.

    We do not recursively crawl the internet.
    """

    url = normalize_url(source["url"])

    if not url:
        return None

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # Give dynamic pages a moment to populate.
        page.wait_for_timeout(1200)

        title = clean_text(page.title())

        body = clean_text(
            page.locator("body").inner_text()
        )

        if not body:
            return None

        if looks_like_blocked_page(body, title):
            return None

        # Reject tiny/empty pages.
        if len(body) < 500:
            return None

        # For regulatory sources, make sure the page actually
        # contains meaningful regulatory/compliance language.
        if not contains_regulatory_content(body):
            return None

        # Keep the evidence manageable.
        body = body[:12000]

        return {
            "agency": source["agency"],
            "title": source["title"],
            "url": url,
            "text": body,
        }

    except Exception:
        return None


# ============================================================
# RELEVANCE SCORING
# ============================================================

def score_source(source, business_description):
    text = (
        source["title"]
        + " "
        + source["text"]
    ).lower()

    business_words = re.findall(
        r"\b[a-zA-Z]{4,}\b",
        business_description.lower(),
    )

    score = 0

    for word in set(business_words):
        if word in text:
            score += 1

    # Regulatory-specific boosts.
    for phrase, points in [
        ("40 cfr", 4),
        ("cfr §", 5),
        ("hazardous waste", 4),
        ("surface coating", 5),
        ("paint stripping", 5),
        ("motor vehicle", 5),
        ("auto body", 5),
        ("generator", 3),
        ("volatile organic", 3),
        ("emission", 3),
        ("storage", 2),
        ("container", 2),
        ("notification", 2),
    ]:
        if phrase in text:
            score += points

    return score


# ============================================================
# RETRIEVAL ENGINE
# ============================================================

def retrieve_regulatory_evidence(
    business_description,
    topics,
):
    """
    Retrieve targeted regulatory pages.

    IMPORTANT:
    We intentionally retrieve exact known regulatory pages rather
    than asking a search engine to return arbitrary pages.
    """

    sources_to_check = []

    for topic in topics:

        for source in REGULATORY_TOPICS.get(topic, []):

            item = dict(source)
            item["topic"] = topic

            sources_to_check.append(item)

    # Remove duplicate URLs.
    unique_sources = {}

    for source in sources_to_check:
        unique_sources[source["url"]] = source

    sources_to_check = list(unique_sources.values())

    ensure_playwright_browser()

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "Chrome/150.0 Safari/537.36"
            )
        )

        page = context.new_page()

        progress = st.progress(
            0,
            text="Retrieving official regulatory sources...",
        )

        total = len(sources_to_check)

        for index, source in enumerate(sources_to_check):

            result = scrape_page(
                page,
                source,
            )

            if result:

                result["topic"] = source["topic"]

                result["relevance"] = score_source(
                    result,
                    business_description,
                )

                results.append(result)

            progress.progress(
                (index + 1) / max(total, 1),
                text=(
                    f"Checking official sources "
                    f"({index + 1}/{total})..."
                ),
            )

        progress.empty()

        browser.close()

    # Deduplicate by URL.
    deduped = {}

    for result in results:

        url = result["url"]

        if (
            url not in deduped
            or result["relevance"] > deduped[url]["relevance"]
        ):
            deduped[url] = result

    results = list(deduped.values())

    results.sort(
        key=lambda x: x["relevance"],
        reverse=True,
    )

    # Keep the strongest sources.
    return results[:10]


# ============================================================
# EVIDENCE PACKET
# ============================================================

def build_evidence_prompt(
    business_description,
    sources,
):
    """
    Create a deliberately size-limited evidence packet so the
    Groq request cannot accidentally exceed its token-per-minute
    limit.
    """

    max_sources = 6
    max_chars_per_source = 3500
    max_total_chars = 17000

    business_description = business_description[:4000]

    evidence_parts = []

    total_chars = 0

    for index, source in enumerate(
        sources[:max_sources],
        start=1,
    ):

        text = source["text"][
            :max_chars_per_source
        ]

        block = f"""
SOURCE {index}

Agency: {source["agency"]}
Topic: {source["topic"]}
Title: {source["title"]}
URL: {source["url"]}

REGULATORY EVIDENCE:
{text}
""".strip()

        if total_chars + len(block) > max_total_chars:
            break

        evidence_parts.append(block)
        total_chars += len(block)

    evidence = "\n\n" + (
        "\n\n".join(evidence_parts)
    )

    return f"""
BUSINESS DESCRIPTION
--------------------
{business_description}

OFFICIAL REGULATORY EVIDENCE
----------------------------
{evidence}

IMPORTANT:
The source material above is the complete evidence available
to you.

You MUST NOT invent regulations, citations, penalties,
deadlines, limits, permits, or requirements.

You MUST NOT use your general knowledge to fill missing
regulatory information.

If a requirement cannot be supported by the supplied evidence,
do not create one.

If the evidence indicates that additional facts are needed,
mark the issue as "Needs Review".

Use exact citations and URLs from the supplied evidence.
""".strip()


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_compliance(
    business_description,
    sources,
):
    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured in Streamlit secrets."
        )

    client = Groq(
        api_key=api_key
    )

    evidence_prompt = build_evidence_prompt(
        business_description,
        sources,
    )

    system_prompt = """
You are EcoComply, a regulatory evidence-analysis assistant.

Your job is to compare a business description against ONLY the
official regulatory evidence supplied by the application.

You are NOT a lawyer and must not claim that a business is
legally compliant.

CORE RULE:
Never invent a regulation.

Every regulatory requirement MUST be directly supported by the
provided evidence.

Every requirement must include:
- requirement
- citation
- source_url
- evidence
- business_evidence
- explanation
- status

Allowed statuses:
- "Compliant"
- "Needs Review"
- "Action Required"
- "Not Applicable"

Use "Needs Review" when the supplied business information is
insufficient to determine compliance.

Use "Action Required" only when the evidence clearly establishes
that the described practice conflicts with a requirement.

Use "Compliant" only when the evidence and business description
actually establish compliance with the requirement.

Use "Not Applicable" only when the supplied evidence clearly
establishes that the requirement does not apply.

IMPORTANT:
Do not turn general advice into a regulatory requirement.

Do not invent monetary penalties.

Do not invent deadlines.

Do not invent permit requirements.

Do not invent numeric limits.

Do not invent CFR sections.

Return ONLY valid JSON.

Required JSON structure:

{
  "overall_status": "Compliant | Needs Review | Action Required",
  "summary": "short summary",
  "requirements": [
    {
      "title": "short title",
      "status": "Compliant | Needs Review | Action Required | Not Applicable",
      "requirement": "supported requirement",
      "citation": "exact citation from evidence",
      "source_url": "exact source URL",
      "evidence": "relevant regulatory evidence",
      "business_evidence": "relevant fact from business description",
      "explanation": "why the requirement was or was not satisfied",
      "recommended_action": "specific next step"
    }
  ],
  "recommended_next_steps": [
    "next step"
  ],
  "important_warning": "short warning"
}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        temperature=0.1,
        max_tokens=4500,
        response_format={
            "type": "json_object"
        },
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": evidence_prompt,
            },
        ],
    )

    raw = response.choices[0].message.content

    raw = clean_text(raw)

    try:
        return json.loads(raw)

    except json.JSONDecodeError:

        # Sometimes a model may still surround JSON with
        # markdown fences. Remove them.
        cleaned = re.sub(
            r"^```(?:json)?",
            "",
            raw.strip(),
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"```$",
            "",
            cleaned.strip(),
        )

        return json.loads(cleaned)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ EcoComply")

    st.caption(
        "Evidence-based environmental compliance analysis"
    )

    st.divider()

    preset = st.selectbox(
        "Example business",
        [
            "Custom",
            "Auto Body Shop",
            "Commercial Bakery",
            "Furniture Refinishing",
        ],
    )

    st.divider()

    st.markdown(
        "**How EcoComply works**"
    )

    st.markdown(
        """
        1. Identify likely regulatory topics
        2. Retrieve official sources
        3. Extract regulatory evidence
        4. Compare evidence with business practices
        5. Produce a traceable assessment
        """
    )

    st.divider()

    st.caption(
        "EcoComply is an educational prototype and does not "
        "replace professional legal or environmental advice."
    )


# ============================================================
# PRESETS
# ============================================================

PRESETS = {
    "Auto Body Shop": """
We operate an auto body repair shop in Michigan.

We repair and repaint damaged vehicles.

The shop uses solvent-based automotive paints and paint thinner.
Paint and solvent products are stored in metal drums and
containers inside the facility.

Employees use spray equipment to apply coatings to vehicles.
The facility has a paint booth.

Used solvent and paint-related waste are collected for disposal.

The business wants to know whether its current environmental
practices appear to meet applicable federal and Michigan
requirements.
""".strip(),

    "Commercial Bakery": """
We operate a commercial bakery in Michigan.

The facility uses commercial ovens, natural gas, cleaning
chemicals, and produces food waste.

We want to understand what environmental requirements may apply
to air emissions, waste handling, wastewater, and chemical
storage.
""".strip(),

    "Furniture Refinishing": """
We operate a furniture refinishing business in Michigan.

The facility uses solvent-based paints, stains, coatings, and
cleaning solvents.

Products are stored in containers inside the facility.

Workers spray coatings onto furniture and generate used solvent
and paint-related waste.

We want to identify applicable environmental requirements.
""".strip(),
}


# ============================================================
# HEADER
# ============================================================

st.title("🌱 EcoComply")

st.markdown(
    """
    **Evidence-based environmental compliance assistant**

    EcoComply identifies potentially applicable environmental
    requirements, retrieves official regulatory sources, and
    compares those requirements against the business's described
    practices.
    """
)

st.divider()


# ============================================================
# INPUT
# ============================================================

if preset != "Custom":

    default_description = PRESETS[preset]

else:

    default_description = ""


business_description = st.text_area(
    "Describe the business and its environmental practices",
    value=default_description,
    height=250,
    placeholder=(
        "Example: We operate an auto body shop in Michigan. "
        "We use solvent-based paint, store paint thinner in "
        "metal drums, and spray paint vehicles..."
    ),
)


analyze_button = st.button(
    "🔎 Analyze Compliance",
    type="primary",
    use_container_width=True,
)


# ============================================================
# ANALYSIS
# ============================================================

if analyze_button:

    if not business_description.strip():

        st.warning(
            "Please describe the business before running an analysis."
        )

        st.stop()

    try:

        # ----------------------------------------------------
        # TOPIC DETECTION
        # ----------------------------------------------------

        topics = detect_topics(
            business_description
        )

        st.markdown("### 🔎 Regulatory research")

        st.write(
            "Targeted topics: "
            + ", ".join(topics)
        )

        # ----------------------------------------------------
        # RETRIEVAL
        # ----------------------------------------------------

        sources = retrieve_regulatory_evidence(
            business_description,
            topics,
        )

        if not sources:

            st.error(
                "EcoComply could not retrieve usable regulatory "
                "evidence from the configured official sources."
            )

            st.info(
                "No AI compliance determination was made because "
                "the evidence layer did not return usable sources."
            )

            st.stop()

        st.success(
            f"Retrieved {len(sources)} usable official source "
            f"pages."
        )

        # ----------------------------------------------------
        # AI ANALYSIS
        # ----------------------------------------------------

        with st.spinner(
            "Comparing business practices against retrieved evidence..."
        ):

            assessment = analyze_compliance(
                business_description,
                sources,
            )

        # ----------------------------------------------------
        # NORMALIZE AI OUTPUT
        # ----------------------------------------------------

        overall_status = clean_text(
            assessment.get(
                "overall_status",
                "Needs Review",
            )
        )

        summary = clean_text(
            assessment.get(
                "summary",
                "No summary was provided.",
            )
        )

        requirements = assessment.get(
            "requirements",
            [],
        )

        next_steps = assessment.get(
            "recommended_next_steps",
            [],
        )

        important_warning = clean_text(
            assessment.get(
                "important_warning",
                "",
            )
        )

        # ----------------------------------------------------
        # ASSESSMENT
        # ----------------------------------------------------

        st.markdown(
            "### 📋 Compliance assessment"
        )

        if overall_status == "Compliant":

            status_display = "✅ Compliant"

        elif overall_status == "Action Required":

            status_display = "🚨 Action Required"

        else:

            status_display = "⚠️ Needs Review"

        action_required_count = sum(
            1
            for item in requirements
            if item.get("status") == "Action Required"
        )

        needs_review_count = sum(
            1
            for item in requirements
            if item.get("status") == "Needs Review"
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.markdown(
                '<div class="status-card">'
                '<strong>Overall</strong><br><br>'
                f'{status_display}'
                '</div>',
                unsafe_allow_html=True,
            )

        with col2:

            st.markdown(
                '<div class="status-card">'
                '<strong>Requirements</strong><br><br>'
                f'{len(requirements)}'
                '</div>',
                unsafe_allow_html=True,
            )

        with col3:

            st.markdown(
                '<div class="status-card">'
                '<strong>Action Required</strong><br><br>'
                f'{action_required_count}'
                '</div>',
                unsafe_allow_html=True,
            )

        with col4:

            st.markdown(
                '<div class="status-card">'
                '<strong>Needs Review</strong><br><br>'
                f'{needs_review_count}'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("#### Summary")

        st.write(summary)

        # ----------------------------------------------------
        # REQUIREMENTS
        # ----------------------------------------------------

        st.markdown(
            "### 📑 Regulatory requirements"
        )

        if not requirements:

            st.info(
                "No specific requirements were identified that "
                "could be supported by the retrieved evidence."
            )

        else:

            for index, requirement in enumerate(
                requirements,
                start=1,
            ):

                title = clean_text(
                    requirement.get(
                        "title",
                        f"Requirement {index}",
                    )
                )

                status = clean_text(
                    requirement.get(
                        "status",
                        "Needs Review",
                    )
                )

                requirement_text = clean_text(
                    requirement.get(
                        "requirement",
                        "",
                    )
                )

                citation = clean_text(
                    requirement.get(
                        "citation",
                        "",
                    )
                )

                source_url = requirement.get(
                    "source_url",
                    "",
                )

                evidence = clean_text(
                    requirement.get(
                        "evidence",
                        "",
                    )
                )

                business_evidence = clean_text(
                    requirement.get(
                        "business_evidence",
                        "",
                    )
                )

                explanation = clean_text(
                    requirement.get(
                        "explanation",
                        "",
                    )
                )

                recommended_action = clean_text(
                    requirement.get(
                        "recommended_action",
                        "",
                    )
                )

                if status == "Compliant":

                    icon = "✅"

                elif status == "Action Required":

                    icon = "🚨"

                elif status == "Not Applicable":

                    icon = "➖"

                else:

                    icon = "⚠️"

                st.markdown(
                    '<div class="requirement-card">',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"#### {icon} {title}"
                )

                st.markdown(
                    f"**Status:** {status}"
                )

                if requirement_text:

                    st.markdown(
                        "**Requirement**"
                    )

                    st.write(
                        requirement_text
                    )

                if citation:

                    st.markdown(
                        "**Citation**"
                    )

                    st.code(
                        citation,
                        language=None,
                    )

                if evidence:

                    with st.expander(
                        "📜 Regulatory evidence"
                    ):

                        st.write(
                            evidence
                        )

                if business_evidence:

                    with st.expander(
                        "🏢 Business evidence"
                    ):

                        st.write(
                            business_evidence
                        )

                if explanation:

                    st.markdown(
                        "**Why EcoComply flagged this**"
                    )

                    st.write(
                        explanation
                    )

                if recommended_action:

                    st.markdown(
                        "**Recommended action**"
                    )

                    st.write(
                        recommended_action
                    )

                if source_url:

                    normalized_source_url = normalize_url(
                        source_url
                    )

                    if normalized_source_url:

                        st.markdown(
                            f"🔗 [Open official source]"
                            f"({normalized_source_url})"
                        )

                st.markdown(
                    "</div>",
                    unsafe_allow_html=True,
                )

        # ----------------------------------------------------
        # NEXT STEPS
        # ----------------------------------------------------

        st.markdown(
            "### ➡️ Recommended next steps"
        )

        if next_steps:

            for step in next_steps:

                step = clean_text(step)

                if step:

                    st.markdown(
                        f"- {step}"
                    )

        else:

            st.write(
                "No additional next steps were provided."
            )

        if important_warning:

            st.warning(
                important_warning
            )

        # ----------------------------------------------------
        # SOURCES
        # ----------------------------------------------------

        st.markdown(
            "### 🔗 Retrieved official sources"
        )

        for source in sources:

            st.markdown(
                '<div class="source-card">',
                unsafe_allow_html=True,
            )

            st.markdown(
                f"**{clean_text(source['agency'])}**"
            )

            st.markdown(
                f"**Topic:** {clean_text(source['topic'])}"
            )

            st.markdown(
                clean_text(source["title"])
            )

            st.markdown(
                f'<span class="small-muted">'
                f'Relevance score: {source["relevance"]}'
                f'</span>',
                unsafe_allow_html=True,
            )

            st.markdown(
                f"[Open official source]({source['url']})"
            )

            with st.expander(
                "View retrieved evidence"
            ):

                st.write(
                    source["text"][:5000]
                )

            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------
        # STRUCTURED DATA
        # ----------------------------------------------------

        st.markdown(
            "### 🧾 Structured assessment data"
        )

        with st.expander(
            "View raw JSON"
        ):

            st.json(
                assessment
            )

        download_data = {
            "business_description": business_description,
            "targeted_topics": topics,
            "retrieved_sources": [
                {
                    "agency": source["agency"],
                    "topic": source["topic"],
                    "title": source["title"],
                    "url": source["url"],
                    "relevance": source["relevance"],
                }
                for source in sources
            ],
            "assessment": assessment,
        }

        st.download_button(
            label="⬇️ Download assessment JSON",
            data=json.dumps(
                download_data,
                indent=2,
            ),
            file_name="ecocomply_assessment.json",
            mime="application/json",
        )

        # ----------------------------------------------------
        # LIMITATIONS
        # ----------------------------------------------------

        st.markdown(
            "### ⚠️ Limitations"
        )

        st.markdown(
            """
            - EcoComply only evaluates requirements supported by
              the retrieved evidence.
            - Applicability can depend on details such as
              facility size, materials used, quantities, emissions,
              waste generation, permits, and operating practices.
            - A preliminary result of "Compliant" does not constitute
              a legal determination of compliance.
            - EcoComply does not replace professional legal or
              environmental compliance advice.
            """
        )

    except Exception as exc:

        st.error(
            "EcoComply encountered an error while performing "
            "the analysis."
        )

        with st.expander(
            "Technical details"
        ):

            st.code(
                str(exc)
            )
