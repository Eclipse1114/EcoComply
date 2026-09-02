import json
import os
import re
import html
import subprocess
import sys
from urllib.parse import quote_plus, urljoin, urlparse

import streamlit as st
from groq import Groq
from playwright.sync_api import sync_playwright


# =========================================================
# PLAYWRIGHT CONFIGURATION
# =========================================================

# Explicitly tell Playwright where its browser binaries live.
# This makes the installer and browser launcher use the same location.
PLAYWRIGHT_BROWSER_PATH = os.path.expanduser("~/.cache/ms-playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_BROWSER_PATH


def ensure_playwright_browser():
    """
    Make sure Playwright's Chromium headless shell is installed.

    Streamlit Community Cloud installs the Python Playwright package
    from requirements.txt, but the browser binary is separate.
    """

    os.makedirs(PLAYWRIGHT_BROWSER_PATH, exist_ok=True)

    # Ask Playwright itself which executable it expects.
    with sync_playwright() as p:
        executable = p.chromium.executable_path

    # If the executable already exists, we're ready.
    if os.path.exists(executable):
        return

    st.info("First-time setup: installing the Chromium browser used by EcoComply...")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "playwright",
            "install",
            "--only-shell",
            "chromium",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Playwright could not install Chromium.\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    # Verify that the browser actually appeared.
    if not os.path.exists(executable):
        raise RuntimeError(
            "Playwright reported that Chromium was installed, "
            "but the expected browser executable could not be found:\n"
            f"{executable}"
        )


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="EcoComply - Environmental Compliance Assistant",
    page_icon="🌱",
    layout="wide",
)


# =========================================================
# CONFIGURATION
# =========================================================

MODEL_NAME = "openai/gpt-oss-120b"

MAX_SOURCE_CHARS = 12000
MAX_SOURCES = 8

OFFICIAL_SOURCES = {
    "eCFR": "https://www.ecfr.gov/",
    "EPA": "https://www.epa.gov/laws-regulations",
    "Michigan EGLE": (
        "https://www.michigan.gov/egle/regulatory-assistance/regulations"
    ),
}


# Only allow EcoComply to retrieve from official regulatory domains.
ALLOWED_DOMAINS = {
    "ecfr.gov",
    "epa.gov",
    "michigan.gov",
}


# =========================================================
# API KEY
# =========================================================

groq_key = os.getenv("GROQ_API_KEY")

if not groq_key:
    try:
        groq_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        groq_key = None


if groq_key:
    client = Groq(api_key=groq_key)
else:
    client = None


# =========================================================
# STYLING
# =========================================================

st.markdown(
    """
    <style>

    :root {
        --leafy-green: #2E7D32;
        --leafy-green-dark: #1B5E20;
        --aqua-blue: #0288D1;
        --sky-blue-light: #E0F7FA;
        --soft-green: #F4FBF7;
        --border-green: #C8E6C9;
        --text-dark: #17351D;
        --muted: #5F6B63;
    }

    .main-title {
        color: var(--leafy-green);
        font-weight: 800;
        font-size: 2.7rem;
        margin-bottom: 0;
    }

    .sub-caption {
        color: var(--aqua-blue);
        font-size: 1.08rem;
        font-weight: 500;
        margin-bottom: 25px;
    }

    div.stButton > button:first-child {
        background: linear-gradient(
            135deg,
            var(--leafy-green),
            var(--leafy-green-dark)
        ) !important;

        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        font-weight: bold !important;
    }

    div.stButton > button:first-child:hover {
        box-shadow: 0 4px 14px rgba(46, 125, 50, 0.25) !important;
    }

    [data-testid="stSidebar"] {
        background-color: var(--soft-green) !important;
        border-right: 2px solid var(--border-green) !important;
    }

    [data-testid="stSidebar"] h2 {
        color: var(--leafy-green) !important;
    }

    .summary-box {
        background-color: var(--sky-blue-light);
        border-left: 6px solid var(--aqua-blue);
        padding: 18px;
        border-radius: 7px;
        color: #004D40;
        font-size: 1.05rem;
        margin-bottom: 20px;
    }

    .metric-card {
        background: white;
        border: 1px solid #B2EBF2;
        border-top: 4px solid var(--aqua-blue);
        padding: 16px;
        border-radius: 8px;
        min-height: 105px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }

    .metric-title {
        font-size: 0.78rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }

    .metric-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--leafy-green);
        margin-top: 7px;
    }

    .source-card {
        background: #FAFAFA;
        border: 1px solid #E0E0E0;
        border-left: 4px solid var(--aqua-blue);
        padding: 14px;
        border-radius: 7px;
        margin-bottom: 10px;
    }

    .source-title {
        font-weight: 700;
        color: var(--leafy-green-dark);
    }

    .source-citation {
        font-family: monospace;
        font-size: 0.9rem;
        color: #444;
    }

    .status-compliant {
        background: #E8F5E9;
        color: #1B5E20;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
    }

    .status-review {
        background: #FFF8E1;
        color: #8D6E00;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
    }

    .status-action {
        background: #FFEBEE;
        color: #B71C1C;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
    }

    .status-na {
        background: #ECEFF1;
        color: #455A64;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
    }

    .disclaimer {
        background: #FFF8E1;
        border: 1px solid #FFE082;
        border-radius: 7px;
        padding: 12px;
        font-size: 0.9rem;
        color: #5D4037;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    "<h1 class='main-title'>🌱 EcoComply</h1>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class='sub-caption'>
    Evidence-backed environmental compliance analysis for small businesses
    </p>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are EcoComply, an environmental compliance analysis assistant.

Your job is NOT to invent regulations from memory.

The application provides you with:
1. A description of a business and its operations.
2. Retrieved material from official regulatory sources.

You must analyze the business ONLY against the provided evidence.

IMPORTANT RULES:

1. Do not invent statutes, regulations, citations, penalties, grants,
   requirements, deadlines, or source URLs.

2. Do not claim that a business is legally compliant with certainty.

3. If the evidence is insufficient to determine whether something applies,
   use "Needs Review".

4. If the business description explicitly says it already performs a
   requirement, acknowledge that evidence rather than telling the business
   to perform the same action again.

5. Distinguish between:
   - Compliant
   - Needs Review
   - Action Required
   - Not Applicable

6. "Compliant" means the provided business description appears consistent
   with the retrieved requirement. It does NOT mean legal compliance has
   been independently verified.

7. "Action Required" means the provided business information indicates a
   likely gap between the operation and the retrieved requirement.

8. "Needs Review" means the regulation may apply but the information
   provided is insufficient to determine the status.

9. Every requirement must include the regulatory citation and source URL
   that came from the retrieved evidence.

10. Never fabricate a source URL.

11. Keep explanations understandable to a small-business owner.

12. If a grant or incentive was not found in the provided evidence,
   explicitly say that no verified program was identified instead of
   inventing one.

13. Do not treat general EPA informational pages as proof that a specific
   regulation applies.

14. Prefer specific regulatory text over general informational material.

Return ONLY valid JSON using this schema:

{
    "business_type": "...",
    "overall_status": "Compliant | Needs Review | Action Required",
    "summary": "...",
    "requirements": [
        {
            "title": "...",
            "status": "Compliant | Needs Review | Action Required | Not Applicable",
            "requirement": "...",
            "explanation": "...",
            "business_evidence": "...",
            "action": "...",
            "citation": "...",
            "source_title": "...",
            "source_url": "...",
            "confidence": "High | Medium | Low"
        }
    ],
    "next_steps": [
        "...",
        "..."
    ],
    "risk_warning": "...",
    "grant_or_incentive": "...",
    "limitations": [
        "..."
    ]
}
"""


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def clean_text(text: str) -> str:
    """Normalize whitespace while preserving readable text."""

    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_allowed_url(url: str) -> bool:
    """Only permit official regulatory domains."""

    if not url:
        return False

    try:
        hostname = urlparse(url).hostname

        if not hostname:
            return False

        hostname = hostname.lower()

        return (
            hostname in ALLOWED_DOMAINS
            or any(
                hostname.endswith("." + domain)
                for domain in ALLOWED_DOMAINS
            )
        )

    except Exception:
        return False


def safe_url(url: str) -> str:
    """Return a URL only if it belongs to an approved domain."""

    if is_allowed_url(url):
        return url

    return ""


def extract_cfr_references(text: str) -> list[str]:
    """
    Pull likely CFR references from retrieved text.

    Examples:
    40 CFR 262.15
    40 CFR § 63.111
    """

    pattern = (
        r"\b\d+\s+CFR\s+(?:§\s*)?"
        r"\d+(?:\.\d+)*\b"
    )

    matches = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    cleaned = []

    for match in matches:

        normalized = re.sub(
            r"\s+",
            " ",
            match,
        ).strip()

        if normalized not in cleaned:
            cleaned.append(normalized)

    return cleaned


def keyword_list(
    business_description: str,
) -> list[str]:
    """
    Convert the business description into broad regulatory concepts.
    """

    description = business_description.lower()

    concepts = []

    keyword_groups = {

        "hazardous waste": [
            "hazardous waste",
            "waste",
            "solvent",
            "thinner",
            "chemical",
            "paint",
            "lacquer",
            "stripper",
        ],

        "air emissions": [
            "paint",
            "spray",
            "coating",
            "lacquer",
            "solvent",
            "oven",
            "gas",
            "emission",
            "volatile organic",
            "voc",
        ],

        "wastewater": [
            "wastewater",
            "sewer",
            "drain",
            "discharge",
            "grease",
            "water",
        ],

        "solid waste": [
            "trash",
            "food waste",
            "scrap",
            "sawdust",
            "solid waste",
        ],

        "chemical storage": [
            "chemical",
            "solvent",
            "drum",
            "container",
            "storage",
            "paint",
        ],
    }

    for concept, keywords in keyword_groups.items():

        if any(
            keyword in description
            for keyword in keywords
        ):
            concepts.append(concept)

    if not concepts:
        concepts.append(
            "environmental compliance small business"
        )

    return concepts[:5]


# =========================================================
# PLAYWRIGHT RETRIEVAL
# =========================================================

def retrieve_ecfr_sources(
    page,
    query: str,
) -> list[dict]:

    """
    Search eCFR using its public search interface.
    """

    results = []

    search_url = (
        "https://www.ecfr.gov/search"
        f"?search%5Bquery%5D={quote_plus(query)}"
    )

    try:

        page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(1500)

        links = page.locator("a").all()

        seen = set()

        for link in links:

            try:

                href = link.get_attribute("href")
                title = clean_text(
                    link.inner_text()
                )

                if not href or not title:
                    continue

                full_url = urljoin(
                    "https://www.ecfr.gov/",
                    href,
                )

                if not is_allowed_url(full_url):
                    continue

                if "/current/title-" not in full_url:
                    continue

                if full_url in seen:
                    continue

                seen.add(full_url)

                results.append(
                    {
                        "source": "eCFR",
                        "title": title[:250],
                        "url": full_url,
                    }
                )

                if len(results) >= 5:
                    break

            except Exception:
                continue

    except Exception:
        pass

    return results


def retrieve_official_page(
    page,
    url: str,
    source_name: str,
) -> dict | None:

    """Open an official page and extract readable text."""

    if not is_allowed_url(url):
        return None

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(1000)

        title = clean_text(
            page.title()
        )

        body_text = page.locator(
            "body"
        ).inner_text()

        body_text = clean_text(
            body_text
        )

        if not body_text:
            return None

        body_text = body_text[
            :MAX_SOURCE_CHARS
        ]

        return {
            "source": source_name,
            "title": title[:300],
            "url": url,
            "text": body_text,
            "cfr_references": extract_cfr_references(
                body_text
            ),
        }

    except Exception:
        return None


def retrieve_regulatory_evidence(
    business_description: str,
) -> tuple[list[dict], list[str]]:

    """
    Main evidence-retrieval pipeline.
    """

    # IMPORTANT:
    # Make absolutely certain the browser exists BEFORE
    # attempting to launch it.
    ensure_playwright_browser()

    concepts = keyword_list(
        business_description
    )

    evidence = []
    retrieval_status = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
        )

        context = browser.new_context(
            user_agent=(
                "EcoComply/1.0 "
                "(educational environmental compliance research tool)"
            ),
            viewport={
                "width": 1440,
                "height": 900,
            },
        )

        page = context.new_page()

        # -------------------------------------------------
        # eCFR
        # -------------------------------------------------

        retrieval_status.append(
            "Searching eCFR..."
        )

        ecfr_results = []

        for concept in concepts:

            ecfr_results.extend(
                retrieve_ecfr_sources(
                    page,
                    concept,
                )
            )

        # Deduplicate.
        unique_ecfr = []

        seen_urls = set()

        for result in ecfr_results:

            if result["url"] in seen_urls:
                continue

            seen_urls.add(
                result["url"]
            )

            unique_ecfr.append(
                result
            )

        # Retrieve actual regulation pages.
        for result in unique_ecfr[:5]:

            page_data = retrieve_official_page(
                page,
                result["url"],
                "eCFR",
            )

            if page_data:
                evidence.append(
                    page_data
                )

        if any(
            item["source"] == "eCFR"
            for item in evidence
        ):
            retrieval_status.append(
                "✓ eCFR evidence retrieved"
            )
        else:
            retrieval_status.append(
                "⚠ eCFR search returned no usable evidence"
            )

        # -------------------------------------------------
        # EPA
        # -------------------------------------------------

        retrieval_status.append(
            "Checking EPA..."
        )

        epa_page = retrieve_official_page(
            page,
            OFFICIAL_SOURCES["EPA"],
            "EPA",
        )

        if epa_page:

            evidence.append(
                epa_page
            )

            retrieval_status.append(
                "✓ EPA regulatory information retrieved"
            )

        else:

            retrieval_status.append(
                "⚠ EPA page could not be retrieved"
            )

        # -------------------------------------------------
        # Michigan EGLE
        # -------------------------------------------------

        if "michigan" in business_description.lower():

            retrieval_status.append(
                "Checking Michigan EGLE..."
            )

            egle_page = retrieve_official_page(
                page,
                OFFICIAL_SOURCES["Michigan EGLE"],
                "Michigan EGLE",
            )

            if egle_page:

                evidence.append(
                    egle_page
                )

                retrieval_status.append(
                    "✓ Michigan EGLE regulatory information retrieved"
                )

            else:

                retrieval_status.append(
                    "⚠ Michigan EGLE page could not be retrieved"
                )

        context.close()
        browser.close()

    # -----------------------------------------------------
    # Deduplicate evidence
    # -----------------------------------------------------

    unique_evidence = []

    seen = set()

    for item in evidence:

        key = (
            item.get("source"),
            item.get("url"),
        )

        if key in seen:
            continue

        seen.add(key)

        unique_evidence.append(
            item
        )

    return (
        unique_evidence[:MAX_SOURCES],
        retrieval_status,
    )


# =========================================================
# AI ANALYSIS
# =========================================================

def build_evidence_packet(
    evidence: list[dict],
) -> str:

    """Convert retrieved pages into a compact evidence packet."""

    if not evidence:
        return (
            "NO REGULATORY EVIDENCE WAS "
            "SUCCESSFULLY RETRIEVED."
        )

    sections = []

    for index, item in enumerate(
        evidence,
        start=1,
    ):

        section = f"""
SOURCE {index}
Source: {item.get("source", "Unknown")}
Title: {item.get("title", "Unknown")}
URL: {item.get("url", "")}

CFR REFERENCES FOUND:
{", ".join(item.get("cfr_references", [])) or "None detected"}

RETRIEVED TEXT:
{item.get("text", "")}
"""

        sections.append(
            section
        )

    return "\n\n".join(
        sections
    )


@st.cache_data(
    show_spinner=False,
    ttl=3600,
)
def generate_compliance_report(
    business_description: str,
    evidence_json: str,
) -> dict:

    if not client:

        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    evidence = json.loads(
        evidence_json
    )

    evidence_packet = build_evidence_packet(
        evidence
    )

    user_prompt = f"""
BUSINESS PROFILE
================
{business_description}


REGULATORY EVIDENCE
===================
{evidence_packet}


TASK
====
Analyze the business against the retrieved evidence.

Do not assume that a requirement applies merely because it sounds relevant.

For each requirement:
- identify what the source actually requires,
- compare it against the business description,
- identify existing practices that appear consistent,
- identify gaps,
- identify missing information,
- provide the exact citation when available,
- provide the source URL supplied in the evidence.

If a source does not provide enough information to make a determination,
use "Needs Review".

Remember:
You are producing a preliminary educational assessment, not a legal
determination.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        response_format={
            "type": "json_object"
        },
        temperature=0.1,
    )

    raw = response.choices[0].message.content

    report = json.loads(
        raw
    )

    return normalize_report(
        report
    )


def normalize_report(
    report: dict,
) -> dict:

    """Ensure the model response has the expected structure."""

    if not isinstance(report, dict):

        raise ValueError(
            "AI returned an invalid report."
        )

    report.setdefault(
        "business_type",
        "Business",
    )

    report.setdefault(
        "overall_status",
        "Needs Review",
    )

    report.setdefault(
        "summary",
        "No summary was provided.",
    )

    report.setdefault(
        "requirements",
        [],
    )

    report.setdefault(
        "next_steps",
        [],
    )

    report.setdefault(
        "risk_warning",
        "Potential compliance risks could not be fully determined.",
    )

    report.setdefault(
        "grant_or_incentive",
        "No verified assistance program was identified in the retrieved evidence.",
    )

    report.setdefault(
        "limitations",
        [],
    )

    valid_statuses = {
        "Compliant",
        "Needs Review",
        "Action Required",
        "Not Applicable",
    }

    cleaned_requirements = []

    for requirement in report["requirements"]:

        if not isinstance(
            requirement,
            dict,
        ):
            continue

        status = requirement.get(
            "status",
            "Needs Review",
        )

        if status not in valid_statuses:
            status = "Needs Review"

        cleaned_requirements.append(
            {
                "title": requirement.get(
                    "title",
                    "Regulatory Requirement",
                ),
                "status": status,
                "requirement": requirement.get(
                    "requirement",
                    "",
                ),
                "explanation": requirement.get(
                    "explanation",
                    "",
                ),
                "business_evidence": requirement.get(
                    "business_evidence",
                    "",
                ),
                "action": requirement.get(
                    "action",
                    "",
                ),
                "citation": requirement.get(
                    "citation",
                    "Citation not identified",
                ),
                "source_title": requirement.get(
                    "source_title",
                    "Official source",
                ),
                "source_url": safe_url(
                    requirement.get(
                        "source_url",
                        "",
                    )
                ),
                "confidence": requirement.get(
                    "confidence",
                    "Low",
                ),
            }
        )

    report["requirements"] = (
        cleaned_requirements
    )

    return report


# =========================================================
# UI HELPERS
# =========================================================

def status_html(
    status: str,
) -> str:

    classes = {
        "Compliant": "status-compliant",
        "Needs Review": "status-review",
        "Action Required": "status-action",
        "Not Applicable": "status-na",
    }

    class_name = classes.get(
        status,
        "status-review",
    )

    return (
        f"<span class='{class_name}'>"
        f"{html.escape(status)}"
        f"</span>"
    )


def count_statuses(
    requirements: list[dict],
) -> dict:

    counts = {
        "Compliant": 0,
        "Needs Review": 0,
        "Action Required": 0,
        "Not Applicable": 0,
    }

    for item in requirements:

        status = item.get(
            "status"
        )

        if status in counts:
            counts[status] += 1

    return counts


def build_markdown_report(
    report: dict,
    business_description: str,
) -> str:

    requirements = report.get(
        "requirements",
        [],
    )

    lines = [
        "# EcoComply Environmental Compliance Assessment",
        "",
        f"**Business Type:** {report.get('business_type', 'N/A')}",
        f"**Overall Status:** {report.get('overall_status', 'N/A')}",
        "",
        "## Business Profile",
        "",
        business_description,
        "",
        "## Executive Summary",
        "",
        report.get("summary", ""),
        "",
        "## Regulatory Requirements",
        "",
    ]

    for index, item in enumerate(
        requirements,
        start=1,
    ):

        lines.extend(
            [
                f"### {index}. {item.get('title', 'Requirement')}",
                "",
                f"**Status:** {item.get('status', 'Needs Review')}",
                "",
                f"**Requirement:** {item.get('requirement', '')}",
                "",
                f"**Why:** {item.get('explanation', '')}",
                "",
                f"**Business Evidence:** {item.get('business_evidence', '')}",
                "",
                f"**Recommended Action:** {item.get('action', '')}",
                "",
                f"**Citation:** {item.get('citation', '')}",
                "",
                f"**Source:** {item.get('source_title', '')}",
                "",
                f"**Source URL:** {item.get('source_url', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "## Next Steps",
            "",
        ]
    )

    for step in report.get(
        "next_steps",
        [],
    ):

        lines.append(
            f"- [ ] {step}"
        )

    lines.extend(
        [
            "",
            "## Risk Warning",
            "",
            report.get(
                "risk_warning",
                "",
            ),
            "",
            "## Small Business Assistance",
            "",
            report.get(
                "grant_or_incentive",
                "",
            ),
            "",
            "## Limitations",
            "",
        ]
    )

    for limitation in report.get(
        "limitations",
        [],
    ):

        lines.append(
            f"- {limitation}"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "EcoComply provides a preliminary educational assessment "
            "and does not replace professional legal, environmental, "
            "or regulatory advice.",
        ]
    )

    return "\n".join(
        lines
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header(
        "🏢 Business Profile"
    )

    st.subheader(
        "Quick Presets"
    )

    preset = st.selectbox(
        "Choose a test profile:",
        [
            "Custom Input",
            "Auto Body Shop (Paint & Solvents)",
            "Commercial Bakery (Ovens & Waste)",
            "Furniture Refinishing (Wood Dust & Stains)",
        ],
    )

    preset_texts = {

        "Auto Body Shop (Paint & Solvents)": (
            "I run an auto body shop in Michigan. "
            "We spray paint 5 cars a week using solvent-based paints "
            "and store leftover thinners in metal drums."
        ),

        "Commercial Bakery (Ovens & Waste)": (
            "I operate a commercial bakery in Michigan that runs "
            "3 large gas ovens 12 hours a day and generates bulk "
            "food waste and grease."
        ),

        "Furniture Refinishing (Wood Dust & Stains)": (
            "I run a small woodworking and furniture restoration shop "
            "in Michigan that uses chemical strippers, lacquer finishes, "
            "and generates heavy sawdust."
        ),
    }

    default_text = preset_texts.get(
        preset,
        "",
    )

    user_input = st.text_area(
        "Describe your business operations:",
        value=default_text,
        placeholder=(
            "Example: I operate a small metal fabrication shop "
            "that uses solvent degreasers..."
        ),
        height=190,
    )

    st.caption(
        "Tip: Include your state, materials, waste streams, "
        "equipment, quantities, and storage practices."
    )

    submit_btn = st.button(
        "⚡ Analyze Compliance",
        type="primary",
        use_container_width=True,
    )

    st.markdown("---")

    st.subheader(
        "🔎 Evidence Sources"
    )

    st.caption(
        "EcoComply restricts automated regulatory retrieval "
        "to official sources."
    )

    for name, url in OFFICIAL_SOURCES.items():

        st.markdown(
            f"**{name}**  \n"
            f"{url}"
        )


# =========================================================
# MAIN ANALYSIS
# =========================================================

if submit_btn:

    if not user_input.strip():

        st.warning(
            "Please describe your business operations first."
        )

    elif not groq_key:

        st.error(
            "GROQ_API_KEY is missing. Add it to your environment "
            "variables or Streamlit secrets."
        )

    else:

        st.session_state.pop(
            "report",
            None,
        )

        st.session_state.pop(
            "evidence",
            None,
        )

        st.session_state.pop(
            "retrieval_status",
            None,
        )

        # -------------------------------------------------
        # STEP 1 — RETRIEVAL
        # -------------------------------------------------

        with st.status(
            "🔎 Researching official regulations...",
            expanded=True,
        ) as research_status:

            try:

                evidence, retrieval_status = (
                    retrieve_regulatory_evidence(
                        user_input
                    )
                )

                for status_line in retrieval_status:
                    st.write(status_line)

                if evidence:

                    research_status.update(
                        label=(
                            f"✓ Retrieved {len(evidence)} "
                            "official source(s)"
                        ),
                        state="complete",
                    )

                else:

                    research_status.update(
                        label=(
                            "⚠ No usable regulatory evidence found"
                        ),
                        state="error",
                    )

                st.session_state[
                    "evidence"
                ] = evidence

                st.session_state[
                    "retrieval_status"
                ] = retrieval_status

            except Exception as e:

                research_status.update(
                    label="❌ Regulatory retrieval failed",
                    state="error",
                )

                st.error(
                    f"Could not retrieve regulatory sources: {e}"
                )

        # -------------------------------------------------
        # STEP 2 — AI ANALYSIS
        # -------------------------------------------------

        evidence = st.session_state.get(
            "evidence",
            [],
        )

        if evidence:

            with st.spinner(
                "🧠 Comparing your business against the retrieved requirements..."
            ):

                try:

                    report = generate_compliance_report(
                        user_input,
                        json.dumps(
                            evidence,
                            ensure_ascii=False,
                        ),
                    )

                    st.session_state[
                        "report"
                    ] = report

                except Exception as e:

                    st.error(
                        "The regulatory research succeeded, "
                        "but the AI analysis failed."
                    )

                    st.code(
                        str(e)
                    )

        else:

            st.warning(
                "EcoComply could not retrieve enough official "
                "regulatory evidence to safely generate an assessment."
            )


# =========================================================
# DISPLAY RESULTS
# =========================================================

if "report" in st.session_state:

    report = st.session_state[
        "report"
    ]

    requirements = report.get(
        "requirements",
        [],
    )

    counts = count_statuses(
        requirements
    )

    # -----------------------------------------------------
    # OVERALL STATUS
    # -----------------------------------------------------

    st.subheader(
        f"Compliance Analysis — "
        f"{report.get('business_type', 'Business')}"
    )

    overall_status = report.get(
        "overall_status",
        "Needs Review",
    )

    st.markdown(
        status_html(
            overall_status
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        "<br>",
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # METRICS
    # -----------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">
                    Compliant
                </div>
                <div class="metric-value">
                    {counts["Compliant"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">
                    Action Required
                </div>
                <div class="metric-value">
                    {counts["Action Required"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">
                    Needs Review
                </div>
                <div class="metric-value">
                    {counts["Needs Review"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">
                    Requirements
                </div>
                <div class="metric-value">
                    {len(requirements)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<br>",
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    st.subheader(
        "📋 Executive Summary"
    )

    st.markdown(
        f"""
        <div class="summary-box">
            {html.escape(
                report.get(
                    "summary",
                    "No summary provided.",
                )
            )}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # REQUIREMENTS
    # -----------------------------------------------------

    st.subheader(
        "⚖️ Requirement-by-Requirement Analysis"
    )

    if not requirements:

        st.info(
            "No specific requirements were identified "
            "from the retrieved evidence."
        )

    for index, requirement in enumerate(
        requirements
    ):

        title = requirement.get(
            "title",
            f"Requirement {index + 1}",
        )

        status = requirement.get(
            "status",
            "Needs Review",
        )

        with st.expander(
            f"{index + 1}. {title} — {status}"
        ):

            st.markdown(
                status_html(status),
                unsafe_allow_html=True,
            )

            st.markdown(
                "### What the regulation requires"
            )

            st.write(
                requirement.get(
                    "requirement",
                    "No requirement description provided.",
                )
            )

            st.markdown(
                "### Why EcoComply reached this result"
            )

            st.write(
                requirement.get(
                    "explanation",
                    "No explanation provided.",
                )
            )

            st.markdown(
                "### Business evidence"
            )

            st.info(
                requirement.get(
                    "business_evidence",
                    "No specific business evidence identified.",
                )
            )

            st.markdown(
                "### Recommended action"
            )

            st.write(
                requirement.get(
                    "action",
                    "No additional action identified.",
                )
            )

            st.markdown("---")

            citation_col, confidence_col = st.columns(2)

            with citation_col:

                st.markdown(
                    "**Citation**"
                )

                st.code(
                    requirement.get(
                        "citation",
                        "Not identified",
                    )
                )

            with confidence_col:

                st.markdown(
                    "**Confidence**"
                )

                st.write(
                    requirement.get(
                        "confidence",
                        "Low",
                    )
                )

            st.markdown(
                f"""
                <div class="source-card">
                    <div class="source-title">
                        Official Source
                    </div>
                    <div>
                        {html.escape(
                            requirement.get(
                                "source_title",
                                "Official source",
                            )
                        )}
                    </div>
                    <br>
                    <div class="source-citation">
                        {html.escape(
                            requirement.get(
                                "citation",
                                "Citation unavailable",
                            )
                        )}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            source_url = requirement.get(
                "source_url",
                "",
            )

            if source_url:

                st.link_button(
                    "🔗 Open Official Source",
                    source_url,
                )

    # -----------------------------------------------------
    # NEXT STEPS
    # -----------------------------------------------------

    st.subheader(
        "✅ Recommended Next Steps"
    )

    next_steps = report.get(
        "next_steps",
        [],
    )

    if next_steps:

        for index, step in enumerate(
            next_steps
        ):

            st.checkbox(
                step,
                key=f"next_step_{index}",
            )

    else:

        st.info(
            "No additional next steps were identified."
        )

    # -----------------------------------------------------
    # RISK WARNING
    # -----------------------------------------------------

    st.subheader(
        "⚠️ Risk & Limitation Warning"
    )

    st.warning(
        report.get(
            "risk_warning",
            "Potential risks could not be fully determined.",
        )
    )

    # -----------------------------------------------------
    # SUPPORT
    # -----------------------------------------------------

    st.subheader(
        "💡 Verified Assistance / Support"
    )

    st.success(
        report.get(
            "grant_or_incentive",
            "No verified program was identified in the retrieved evidence.",
        )
    )

    # -----------------------------------------------------
    # SOURCES
    # -----------------------------------------------------

    st.subheader(
        "🔎 Retrieved Regulatory Sources"
    )

    evidence = st.session_state.get(
        "evidence",
        [],
    )

    for source in evidence:

        with st.expander(
            f"{source.get('source', 'Source')} — "
            f"{source.get('title', 'Official source')}"
        ):

            st.write(
                source.get(
                    "text",
                    "",
                )
            )

            source_url = source.get(
                "url",
                "",
            )

            if source_url:

                st.link_button(
                    "Open Source",
                    source_url,
                )

            references = source.get(
                "cfr_references",
                [],
            )

            if references:

                st.markdown(
                    "**CFR references detected:**"
                )

                for reference in references:

                    st.code(
                        reference
                    )

    # -----------------------------------------------------
    # RAW JSON
    # -----------------------------------------------------

    st.subheader(
        "🧩 Structured Report Data"
    )

    with st.expander(
        "View raw JSON"
    ):

        st.json(
            report
        )

    # -----------------------------------------------------
    # DOWNLOADS
    # -----------------------------------------------------

    markdown_report = build_markdown_report(
        report,
        user_input if "user_input" in locals() else "",
    )

    st.download_button(
        "⬇️ Download Markdown Report",
        data=markdown_report,
        file_name="ecocomply_report.md",
        mime="text/markdown",
    )

    st.download_button(
        "⬇️ Download JSON Report",
        data=json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        file_name="ecocomply_report.json",
        mime="application/json",
    )

    # -----------------------------------------------------
    # DISCLAIMER
    # -----------------------------------------------------

    st.markdown(
        """
        <div class="disclaimer">
        <strong>Important:</strong> EcoComply provides a preliminary
        educational assessment based on the information supplied by the
        user and the regulatory material it retrieves. It does not replace
        professional legal, environmental, or regulatory advice.
        </div>
        """,
        unsafe_allow_html=True,
    )
