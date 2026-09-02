import json
import os
import re
import html
import subprocess
import sys
from urllib.parse import urljoin, urlparse

import streamlit as st
from groq import Groq
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="EcoComply",
    page_icon="🌱",
    layout="wide",
)


# ============================================================
# PLAYWRIGHT CONFIGURATION
# ============================================================

PLAYWRIGHT_BROWSER_PATH = os.path.expanduser(
    "~/.cache/ms-playwright"
)

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = (
    PLAYWRIGHT_BROWSER_PATH
)


# ============================================================
# OFFICIAL SOURCES
# ============================================================

OFFICIAL_SOURCES = {
    "eCFR": "https://www.ecfr.gov/",
    "EPA": "https://www.epa.gov/laws-regulations",
    "Michigan EGLE": (
        "https://www.michigan.gov/egle/"
        "regulatory-assistance/regulations"
    ),
    "Michigan Environmental Guide": (
        "https://www.michigan.gov/egle/"
        "regulatory-assistance/compliance-assistance/"
        "environmental-regulations-guide"
    ),
}


ALLOWED_DOMAINS = {
    "ecfr.gov",
    "www.ecfr.gov",
    "epa.gov",
    "www.epa.gov",
    "michigan.gov",
    "www.michigan.gov",
}


# ============================================================
# TOPIC CATALOG
# ============================================================
#
# These are SEARCH TARGETS, not claims that the regulation
# applies to the business.
#
# EcoComply retrieves these official sources and then lets
# the AI determine applicability from the business facts.
#
# ============================================================

REGULATORY_TOPICS = [

    {
        "name": "Hazardous waste",
        "keywords": [
            "hazardous waste",
            "hazardous material",
            "hazardous materials",
            "paint thinner",
            "thinner",
            "solvent",
            "solvents",
            "used solvent",
            "spent solvent",
            "waste paint",
            "paint waste",
            "chemical waste",
        ],
        "cfr_urls": [
            (
                "40 CFR Part 261 — "
                "Identification and Listing of Hazardous Waste",
                "https://www.ecfr.gov/current/title-40/"
                "chapter-I/subchapter-I/part-261"
            ),
            (
                "40 CFR Part 262 — "
                "Standards Applicable to Generators "
                "of Hazardous Waste",
                "https://www.ecfr.gov/current/title-40/"
                "chapter-I/subchapter-I/part-262"
            ),
        ],
        "egle_urls": [
            (
                "Michigan EGLE Administrative Rules — "
                "Hazardous Waste Management",
                "https://www.michigan.gov/egle/"
                "regulatory-assistance/regulations/"
                "administrative-rules"
            ),
        ],
    },

    {
        "name": "Air emissions and VOCs",
        "keywords": [
            "air emissions",
            "air pollution",
            "voc",
            "volatile organic",
            "volatile organic compound",
            "paint",
            "painting",
            "paint booth",
            "coating",
            "coatings",
            "spray paint",
            "spraying",
            "solvent emissions",
        ],
        "cfr_urls": [
            (
                "40 CFR Part 63 — "
                "National Emission Standards for "
                "Hazardous Air Pollutants",
                "https://www.ecfr.gov/current/title-40/"
                "chapter-I/subchapter-C/part-63"
            ),
            (
                "40 CFR Part 60 — "
                "Standards of Performance for "
                "New Stationary Sources",
                "https://www.ecfr.gov/current/title-40/"
                "chapter-I/subchapter-C/part-60"
            ),
        ],
        "egle_urls": [
            (
                "Michigan EGLE Air Laws and Rules",
                "https://www.michigan.gov/egle/about/"
                "organization/Air-Quality/laws-and-rules"
            ),
        ],
    },

    {
        "name": "Paint and surface coating",
        "keywords": [
            "auto body",
            "auto repair",
            "body shop",
            "automotive refinishing",
            "vehicle refinishing",
            "surface coating",
            "surface coatings",
            "paint booth",
            "spray booth",
            "spray coating",
            "paint stripping",
            "paint stripper",
            "refinishing",
        ],
        "cfr_urls": [
            (
                "40 CFR Part 63 — "
                "National Emission Standards for "
                "Hazardous Air Pollutants",
                "https://www.ecfr.gov/current/title-40/"
                "chapter-I/subchapter-C/part-63"
            ),
        ],
        "egle_urls": [
            (
                "Michigan EGLE Air Laws and Rules",
                "https://www.michigan.gov/egle/about/"
                "organization/Air-Quality/laws-and-rules"
            ),
        ],
    },

    {
        "name": "Materials storage and releases",
        "keywords": [
            "storage",
            "stored",
            "drum",
            "drums",
            "container",
            "containers",
            "spill",
            "spills",
            "leak",
            "leaks",
            "release",
            "chemical storage",
            "material storage",
        ],
        "cfr_urls": [
            (
                "40 CFR Part 264 — "
                "Standards for Owners and Operators "
                "of Hazardous Waste Treatment, "
                "Storage, and Disposal Facilities",
                "https://www.ecfr.gov/current/title-40/"
                "chapter-I/subchapter-I/part-264"
            ),
        ],
        "egle_urls": [
            (
                "Michigan Guide to Environmental Regulations",
                "https://www.michigan.gov/egle/"
                "regulatory-assistance/compliance-assistance/"
                "environmental-regulations-guide"
            ),
        ],
    },

    {
        "name": "Stormwater and water discharges",
        "keywords": [
            "stormwater",
            "storm water",
            "runoff",
            "water discharge",
            "wastewater",
            "sewer",
            "drain",
            "drainage",
            "surface water",
            "water pollution",
        ],
        "cfr_urls": [
            (
                "40 CFR Part 122 — "
                "EPA Administered Permit Programs",
                "https://www.ecfr.gov/current/title-40/"
                "chapter-I/subchapter-D/part-122"
            ),
        ],
        "egle_urls": [
            (
                "Michigan EGLE Stormwater Rules and Regulations",
                "https://www.michigan.gov/egle/about/"
                "organization/water-resources/"
                "stormwater-rules"
            ),
        ],
    },

    {
        "name": "General environmental requirements",
        "keywords": [
            "environmental",
            "environment",
            "compliance",
            "regulation",
            "regulations",
            "permit",
            "permits",
            "facility",
            "business",
            "waste",
        ],
        "cfr_urls": [],
        "egle_urls": [
            (
                "Michigan Guide to Environmental Regulations",
                "https://www.michigan.gov/egle/"
                "regulatory-assistance/compliance-assistance/"
                "environmental-regulations-guide"
            ),
            (
                "Michigan EGLE Environmental Rules and Regulations",
                "https://www.michigan.gov/egle/"
                "regulatory-assistance/regulations"
            ),
        ],
    },
]


# ============================================================
# PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>

        .stApp {
            background-color: #ffffff;
            color: #1f2937;
        }

        [data-testid="stSidebar"] {
            background-color: #f5f7f6;
            border-right: 1px solid #dfe5e1;
        }

        [data-testid="stSidebar"] * {
            color: #1f2937;
        }

        h1, h2, h3, h4 {
            color: #173b27;
        }

        .hero {
            padding: 1.5rem 0 1rem 0;
        }

        .hero h1 {
            font-size: 3rem;
            margin-bottom: 0.2rem;
            color: #16733a;
        }

        .hero p {
            font-size: 1.15rem;
            color: #4b5563;
            max-width: 900px;
        }

        .status-card {
            padding: 1.2rem;
            border-radius: 14px;
            background-color: #f3f8f4;
            border: 1px solid #cfe2d4;
            margin-bottom: 1rem;
            color: #1f2937;
        }

        .source-card {
            padding: 1rem;
            border-radius: 12px;
            background-color: #f7f9f8;
            border: 1px solid #dce5df;
            margin-bottom: 0.7rem;
            color: #1f2937;
        }

        .evidence-box {
            padding: 1rem;
            border-left: 4px solid #2f9e5b;
            background-color: #f4f8f5;
            border-radius: 8px;
            margin: 0.5rem 0;
            color: #1f2937;
        }

        .warning-box {
            padding: 1rem;
            border-left: 4px solid #d69e2e;
            background-color: #fff9e8;
            border-radius: 8px;
            margin: 0.7rem 0;
            color: #4a3b16;
        }

        .danger-box {
            padding: 1rem;
            border-left: 4px solid #d64545;
            background-color: #fff2f2;
            border-radius: 8px;
            margin: 0.7rem 0;
            color: #5c1e1e;
        }

        .small-muted {
            color: #6b7280;
            font-size: 0.85rem;
        }

        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
        }

        textarea,
        input {
            color: #1f2937 !important;
        }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# PLAYWRIGHT SETUP
# ============================================================

def ensure_playwright_browser():

    os.makedirs(
        PLAYWRIGHT_BROWSER_PATH,
        exist_ok=True,
    )

    with sync_playwright() as p:
        executable = p.chromium.executable_path

    if os.path.exists(executable):
        return

    st.info(
        "First-time setup: installing Chromium "
        "for EcoComply. This may take a minute."
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
        env=os.environ.copy(),
    )

    if result.returncode != 0:

        raise RuntimeError(
            "Playwright could not install Chromium.\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    with sync_playwright() as p:
        executable = p.chromium.executable_path

    if not os.path.exists(executable):

        raise RuntimeError(
            "Playwright reported that Chromium was installed, "
            "but the expected browser executable could not "
            "be found:\n"
            f"{executable}"
        )


# ============================================================
# GENERAL UTILITIES
# ============================================================

def clean_text(
    text,
    max_length=12000,
):

    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = text.strip()

    return text[:max_length]


def is_allowed_url(url):

    try:

        parsed = urlparse(url)

        return (
            parsed.scheme in {
                "http",
                "https",
            }
            and parsed.netloc.lower()
            in ALLOWED_DOMAINS
        )

    except Exception:
        return False


def extract_cfr_references(text):

    if not text:
        return []

    patterns = [

        (
            r"\b\d+\s+CFR\s+"
            r"(?:Part\s+)?"
            r"\d+(?:\.\d+)*"
            r"(?:\([a-zA-Z0-9]+\))?"
        ),

        (
            r"\bCFR\s+"
            r"\d+(?:\.\d+)*"
        ),
    ]

    references = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            normalized = re.sub(
                r"\s+",
                " ",
                match,
            ).strip()

            if normalized.lower() not in {
                x.lower()
                for x in references
            }:

                references.append(
                    normalized
                )

    return references[:20]


def looks_like_access_page(
    title,
    text,
):

    combined = (
        f"{title} {text}"
    ).lower()

    bad_phrases = [
        "request access",
        "access request",
        "captcha",
        "verify you are human",
        "checking your browser",
        "just a moment",
        "enable javascript and cookies",
        "access denied",
        "forbidden",
        "security check",
    ]

    for phrase in bad_phrases:

        if phrase in combined:
            return True

    return False


def safe_urljoin(
    base_url,
    href,
):

    try:

        full_url = urljoin(
            base_url,
            href,
        )

        if is_allowed_url(
            full_url
        ):
            return full_url

    except Exception:
        pass

    return None


# ============================================================
# TOPIC DETECTION
# ============================================================

def detect_topics(
    business_description
):

    text = business_description.lower()

    detected = []

    for topic in REGULATORY_TOPICS:

        score = 0
        matched_keywords = []

        for keyword in topic[
            "keywords"
        ]:

            if keyword in text:

                score += 1

                matched_keywords.append(
                    keyword
                )

        if score > 0:

            detected.append(
                {
                    "name": topic["name"],
                    "score": score,
                    "matched_keywords":
                        matched_keywords,
                    "cfr_urls":
                        topic["cfr_urls"],
                    "egle_urls":
                        topic["egle_urls"],
                }
            )

    # Always include general Michigan
    # regulatory material.
    if not any(
        x["name"]
        == "General environmental requirements"
        for x in detected
    ):

        general_topic = next(
            x
            for x in REGULATORY_TOPICS
            if x["name"]
            == "General environmental requirements"
        )

        detected.append(
            {
                "name":
                    general_topic["name"],
                "score": 1,
                "matched_keywords":
                    [],
                "cfr_urls":
                    general_topic[
                        "cfr_urls"
                    ],
                "egle_urls":
                    general_topic[
                        "egle_urls"
                    ],
            }
        )

    detected.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return detected


# ============================================================
# PAGE SCRAPER
# ============================================================

def scrape_page(
    page,
    url,
    source_name,
    source_title=None,
):

    if not is_allowed_url(url):
        return None

    try:

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        if response is None:
            return None

        page.wait_for_timeout(
            700
        )

        title = page.title()

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=10000
        )

        body_text = clean_text(
            body_text,
            15000,
        )

        # ----------------------------------------------------
        # Reject access/CAPTCHA pages.
        # ----------------------------------------------------

        if looks_like_access_page(
            title,
            body_text,
        ):

            return None

        if len(body_text) < 250:

            return None

        cfr_references = (
            extract_cfr_references(
                body_text
            )
        )

        # ----------------------------------------------------
        # Collect official links.
        # ----------------------------------------------------

        links = []

        anchors = page.locator(
            "a"
        )

        count = min(
            anchors.count(),
            150,
        )

        for i in range(count):

            try:

                href = (
                    anchors
                    .nth(i)
                    .get_attribute(
                        "href"
                    )
                )

                if not href:
                    continue

                full_url = safe_urljoin(
                    url,
                    href,
                )

                if full_url:
                    links.append(
                        full_url
                    )

            except Exception:
                continue

        return {
            "source": source_name,
            "title": (
                source_title
                or clean_text(
                    title,
                    500,
                )
            ),
            "url": url,
            "text": body_text,
            "cfr_references":
                cfr_references,
            "links": list(
                dict.fromkeys(
                    links
                )
            )[:75],
        }

    except Exception:
        return None


# ============================================================
# REGULATORY RETRIEVAL
# ============================================================

def retrieve_regulatory_evidence(
    business_description
):

    ensure_playwright_browser()

    topics = detect_topics(
        business_description
    )

    evidence = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            user_agent=(
                "EcoComply/1.0 "
                "(educational environmental "
                "compliance research tool)"
            ),
            viewport={
                "width": 1280,
                "height": 900,
            },
        )

        page = context.new_page()

        try:

            # ------------------------------------------------
            # Retrieve targeted CFR pages.
            # ------------------------------------------------

            cfr_seen = set()

            for topic in topics:

                for (
                    title,
                    url,
                ) in topic[
                    "cfr_urls"
                ]:

                    if url in cfr_seen:
                        continue

                    cfr_seen.add(url)

                    result = scrape_page(
                        page,
                        url,
                        "eCFR",
                        title,
                    )

                    if result:

                        result[
                            "topic"
                        ] = topic["name"]

                        result[
                            "topic_keywords"
                        ] = topic[
                            "matched_keywords"
                        ]

                        evidence.append(
                            result
                        )

            # ------------------------------------------------
            # Retrieve targeted Michigan pages.
            # ------------------------------------------------

            egle_seen = set()

            for topic in topics:

                for (
                    title,
                    url,
                ) in topic[
                    "egle_urls"
                ]:

                    if url in egle_seen:
                        continue

                    egle_seen.add(url)

                    result = scrape_page(
                        page,
                        url,
                        "Michigan EGLE",
                        title,
                    )

                    if result:

                        result[
                            "topic"
                        ] = topic["name"]

                        result[
                            "topic_keywords"
                        ] = topic[
                            "matched_keywords"
                        ]

                        evidence.append(
                            result
                        )

        finally:

            browser.close()

    # ========================================================
    # RELEVANCE SCORING
    # ========================================================

    business_words = {
        word.lower()
        for word in re.findall(
            r"[A-Za-z]{4,}",
            business_description,
        )
    }

    for item in evidence:

        text = item.get(
            "text",
            "",
        ).lower()

        score = 0

        # Business vocabulary
        for word in business_words:

            if word in text:
                score += 1

        # Topic keywords
        for keyword in item.get(
            "topic_keywords",
            [],
        ):

            if keyword.lower() in text:
                score += 3

        # Regulatory signals
        regulatory_terms = [
            "shall",
            "must",
            "required",
            "requirement",
            "applicability",
            "applicable",
            "prohibited",
            "permit",
            "recordkeeping",
            "reporting",
            "generator",
            "waste",
            "emission",
            "storage",
        ]

        for term in regulatory_terms:

            if term in text:
                score += 1

        # CFR references are strong evidence.
        score += (
            len(
                item.get(
                    "cfr_references",
                    [],
                )
            )
            * 2
        )

        item[
            "relevance_score"
        ] = score

    evidence.sort(
        key=lambda x: x.get(
            "relevance_score",
            0,
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Remove duplicates.
    # --------------------------------------------------------

    unique = {}

    for item in evidence:

        url = item["url"]

        if url not in unique:

            unique[url] = item

    evidence = list(
        unique.values()
    )

    return evidence


# ============================================================
# COMPACT EVIDENCE PACKET
# ============================================================

def build_evidence_prompt(
    evidence
):

    chunks = []

    total_chars = 0

    # Stay safely below the 8,000 TPM
    # request limit.
    MAX_TOTAL_CHARS = 17000

    MAX_SOURCE_CHARS = 3200

    MAX_SOURCES = 6

    for index, item in enumerate(
        evidence[:MAX_SOURCES],
        start=1,
    ):

        remaining = (
            MAX_TOTAL_CHARS
            - total_chars
        )

        if remaining <= 500:
            break

        source_text = item.get(
            "text",
            "",
        )

        source_text = clean_text(
            source_text,
            min(
                MAX_SOURCE_CHARS,
                remaining,
            ),
        )

        if not source_text:
            continue

        cfr_refs = item.get(
            "cfr_references",
            [],
        )

        chunk = f"""
--- SOURCE {index} ---
Source: {item.get("source", "")}
Topic: {item.get("topic", "")}
Title: {item.get("title", "")}
URL: {item.get("url", "")}
CFR references found: {", ".join(cfr_refs)}

Retrieved official text:
{source_text}
"""

        chunks.append(
            chunk
        )

        total_chars += len(
            chunk
        )

    return "\n".join(
        chunks
    )


# ============================================================
# GROQ
# ============================================================

def get_groq_client():

    api_key = st.secrets.get(
        "GROQ_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GROQ_API_KEY is not configured "
            "in Streamlit secrets."
        )

    return Groq(
        api_key=api_key
    )


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_compliance(
    business_description,
    evidence,
):

    client = get_groq_client()

    evidence_text = (
        build_evidence_prompt(
            evidence
        )
    )

    system_prompt = """
You are EcoComply, an environmental compliance
analysis assistant.

You perform a PRELIMINARY educational assessment
using retrieved official regulatory material.

==================================================
ABSOLUTE EVIDENCE RULES
==================================================

1. Use ONLY the regulatory evidence supplied
   in the user message.

2. Do NOT use your general knowledge to invent
   missing regulations.

3. Do NOT invent CFR citations.

4. Do NOT invent source URLs.

5. Do NOT invent penalties.

6. Do NOT invent grants or incentives.

7. Do NOT treat a topic merely mentioned in a
   business description as proof that a regulation
   applies.

8. Applicability must be based on the supplied
   regulatory evidence and the business facts.

9. If there is not enough evidence, use
   "Needs Review."

10. Never state that the business is legally
    compliant with certainty.

11. "Compliant" means the supplied business
    evidence appears consistent with the retrieved
    requirement. It does NOT mean legally certified.

12. Every regulatory requirement must include:
    - requirement
    - explanation
    - business evidence
    - action
    - citation
    - source title
    - source URL
    - confidence

13. The citation and source URL must come from
    the supplied evidence.

14. If retrieved material is guidance rather than
    binding regulation, clearly describe it as
    guidance.

15. Do not turn recommendations into legal
    requirements.

==================================================
STATUS DEFINITIONS
==================================================

Compliant:
The available business evidence appears to
satisfy the retrieved requirement.

Needs Review:
There is not enough information to determine
compliance confidently.

Action Required:
The business evidence appears inconsistent
with a retrieved requirement.

Not Applicable:
The retrieved material clearly indicates that
the requirement does not apply.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON.
"""

    user_prompt = f"""
BUSINESS DESCRIPTION:

{business_description[:3500]}


RETRIEVED OFFICIAL REGULATORY EVIDENCE:

{evidence_text}


Analyze the business using ONLY the evidence
above.

Return this JSON:

{{
  "business_type": "string",

  "overall_status":
    "Compliant | Needs Review | Action Required",

  "summary": "string",

  "requirements": [
    {{
      "title": "string",

      "status":
        "Compliant | Needs Review | Action Required | Not Applicable",

      "requirement": "string",

      "explanation": "string",

      "business_evidence": "string",

      "action": "string",

      "citation": "string",

      "source_title": "string",

      "source_url": "string",

      "confidence":
        "High | Medium | Low"
    }}
  ],

  "next_steps": [
    "string"
  ],

  "risk_warning": "string",

  "grant_or_incentive": "string",

  "limitations": [
    "string"
  ]
}}

IMPORTANT:

If the retrieved evidence does not contain
an actual requirement, do NOT invent one.

If applicability depends on facts that the
business description does not provide, use
"Needs Review."

If no legitimate requirement can be supported,
return an empty requirements list and explain
why in the summary.
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

        max_tokens=4000,
    )

    raw = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    # Remove Markdown fences.
    raw = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    raw = re.sub(
        r"\s*```$",
        "",
        raw,
    )

    try:

        return json.loads(
            raw
        )

    except json.JSONDecodeError:

        start = raw.find(
            "{"
        )

        end = raw.rfind(
            "}"
        )

        if (
            start != -1
            and end != -1
        ):

            candidate = raw[
                start:end + 1
            ]

            try:

                return json.loads(
                    candidate
                )

            except json.JSONDecodeError:
                pass

        raise RuntimeError(
            "The AI returned invalid JSON.\n\n"
            f"Model response:\n{raw}"
        )


# ============================================================
# UI HELPERS
# ============================================================

def status_emoji(
    status
):

    mapping = {
        "Compliant": "✅",
        "Needs Review": "⚠️",
        "Action Required": "🔴",
        "Not Applicable": "➖",
    }

    return mapping.get(
        status,
        "❓",
    )


def render_requirement(
    requirement,
    index,
):

    status = requirement.get(
        "status",
        "Needs Review",
    )

    title = requirement.get(
        "title",
        f"Requirement {index}",
    )

    with st.expander(
        f"{status_emoji(status)} {title}"
    ):

        st.markdown(
            f"**Status:** {status}"
        )

        st.markdown(
            "### Requirement"
        )

        st.write(
            requirement.get(
                "requirement",
                "No requirement text provided.",
            )
        )

        st.markdown(
            "### Why EcoComply flagged this"
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

        st.write(
            requirement.get(
                "business_evidence",
                "No business evidence provided.",
            )
        )

        st.markdown(
            "### Recommended action"
        )

        st.write(
            requirement.get(
                "action",
                "No action provided.",
            )
        )

        st.markdown(
            "### Regulatory source"
        )

        citation = requirement.get(
            "citation",
            "Not provided",
        )

        source_title = requirement.get(
            "source_title",
            "Official source",
        )

        source_url = requirement.get(
            "source_url",
            "",
        )

        st.write(
            f"**Citation:** {citation}"
        )

        st.write(
            f"**Source:** {source_title}"
        )

        if (
            source_url
            and is_allowed_url(
                source_url
            )
        ):

            st.markdown(
                f"[Open official source]({source_url})"
            )

        st.write(
            "**Confidence:** "
            f"{requirement.get('confidence', 'Low')}"
        )


def render_source(
    item
):

    source = html.escape(
        item.get(
            "source",
            "Unknown",
        )
    )

    topic = html.escape(
        item.get(
            "topic",
            "General",
        )
    )

    title = html.escape(
        item.get(
            "title",
            "Untitled",
        )
    )

    url = item.get(
        "url",
        "",
    )

    score = item.get(
        "relevance_score",
        0,
    )

    cfr_refs = ", ".join(
        item.get(
            "cfr_references",
            [],
        )
    )

    st.markdown(
        f"""
        <div class="source-card">

            <strong>{source}</strong><br>

            <strong>Topic:</strong> {topic}<br>

            {title}<br>

            <span class="small-muted">
                Relevance score: {score}
            </span>

        </div>
        """,
        unsafe_allow_html=True,
    )

    if cfr_refs:

        st.caption(
            f"CFR references found: {cfr_refs}"
        )

    if is_allowed_url(
        url
    ):

        st.markdown(
            f"[Open official source]({url})"
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🌱 EcoComply"
    )

    st.write(
        "Preliminary environmental compliance "
        "research using official regulatory sources."
    )

    st.markdown("---")

    st.markdown(
        "### Quick-start examples"
    )

    presets = {

        "Auto Body Shop": (
            "I operate an auto body repair shop "
            "in Michigan. We use solvent-based "
            "paints and store leftover paint "
            "thinner in metal drums."
        ),

        "Commercial Bakery": (
            "I operate a commercial bakery in "
            "Michigan. We use gas ovens and "
            "produce food waste and grease "
            "during normal operations."
        ),

        "Furniture Refinishing": (
            "I operate a furniture refinishing "
            "business in Michigan. We use "
            "chemical stripping products, "
            "lacquer, and produce sawdust."
        ),
    }

    selected_preset = st.selectbox(
        "Example business",
        [
            "None"
        ]
        + list(
            presets.keys()
        ),
    )

    if selected_preset != "None":

        if st.button(
            "Use example",
            use_container_width=True,
        ):

            st.session_state[
                "business_description"
            ] = presets[
                selected_preset
            ]

            st.rerun()

    st.markdown("---")

    st.markdown(
        "### Official sources"
    )

    for (
        name,
        url,
    ) in OFFICIAL_SOURCES.items():

        st.markdown(
            f"- [{name}]({url})"
        )

    st.markdown("---")

    st.caption(
        "EcoComply is an educational prototype "
        "and does not replace professional legal "
        "or environmental compliance advice."
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">

        <h1>🌱 EcoComply</h1>

        <p>
            Turn a plain-language description of a
            business into a traceable preliminary
            environmental compliance assessment
            using official regulatory sources.
        </p>

    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    **How it works:**

    Business description → targeted regulatory topics
    → official source retrieval → evidence filtering
    → AI analysis → traceable requirements and next steps.
    """
)

st.markdown("---")


# ============================================================
# BUSINESS INPUT
# ============================================================

default_business = st.session_state.get(
    "business_description",
    "",
)

business_description = st.text_area(
    "Describe the business and its activities",

    value=default_business,

    height=180,

    placeholder=(
        "Example: We operate an auto body shop "
        "in Michigan. We use solvent-based paints, "
        "store leftover thinner in drums, and "
        "generate used filters and paint waste."
    ),
)

generate = st.button(
    "🔎 Analyze Environmental Compliance",
    type="primary",
    use_container_width=True,
)


# ============================================================
# ANALYSIS
# ============================================================

if generate:

    if not business_description.strip():

        st.warning(
            "Please describe the business "
            "before running an analysis."
        )

        st.stop()

    st.session_state[
        "business_description"
    ] = business_description

    st.markdown("---")

    st.subheader(
        "🔎 Regulatory research"
    )

    # --------------------------------------------------------
    # Detect topics
    # --------------------------------------------------------

    detected_topics = detect_topics(
        business_description
    )

    if detected_topics:

        topic_names = [
            x["name"]
            for x in detected_topics[:5]
        ]

        st.caption(
            "Targeted topics: "
            + ", ".join(
                topic_names
            )
        )

    progress = st.empty()

    # --------------------------------------------------------
    # Retrieve
    # --------------------------------------------------------

    try:

        progress.info(
            "Retrieving targeted regulatory "
            "material from official sources..."
        )

        evidence = (
            retrieve_regulatory_evidence(
                business_description
            )
        )

        progress.success(
            f"Retrieved {len(evidence)} "
            "usable official source pages."
        )

    except Exception as exc:

        progress.empty()

        st.error(
            "❌ Regulatory retrieval failed"
        )

        st.code(
            str(exc)
        )

        st.stop()

    # --------------------------------------------------------
    # No evidence
    # --------------------------------------------------------

    if not evidence:

        progress.empty()

        st.warning(
            "EcoComply could not retrieve usable "
            "regulatory text from the official sources."
        )

        st.info(
            "No compliance determination was made. "
            "This is intentional: EcoComply will not "
            "invent regulations when source retrieval fails."
        )

        st.stop()

    # --------------------------------------------------------
    # AI analysis
    # --------------------------------------------------------

    with st.spinner(
        "Analyzing retrieved regulatory evidence..."
    ):

        try:

            analysis = analyze_compliance(
                business_description,
                evidence,
            )

        except Exception as exc:

            st.error(
                "❌ Compliance analysis failed"
            )

            st.code(
                str(exc)
            )

            st.stop()

    # ========================================================
    # RESULTS
    # ========================================================

    st.markdown("---")

    st.subheader(
        "📋 Compliance assessment"
    )

    overall_status = analysis.get(
        "overall_status",
        "Needs Review",
    )

    summary = analysis.get(
        "summary",
        "No summary was provided.",
    )

    requirements = analysis.get(
        "requirements",
        [],
    )

    next_steps = analysis.get(
        "next_steps",
        [],
    )

    # --------------------------------------------------------
    # Status counts
    # --------------------------------------------------------

    compliant_count = sum(
        1
        for r in requirements
        if r.get(
            "status"
        ) == "Compliant"
    )

    review_count = sum(
        1
        for r in requirements
        if r.get(
            "status"
        ) == "Needs Review"
    )

    action_count = sum(
        1
        for r in requirements
        if r.get(
            "status"
        ) == "Action Required"
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Overall",
            (
                f"{status_emoji(overall_status)} "
                f"{overall_status}"
            ),
        )

    with col2:

        st.metric(
            "Requirements",
            len(requirements),
        )

    with col3:

        st.metric(
            "Action Required",
            action_count,
        )

    with col4:

        st.metric(
            "Needs Review",
            review_count,
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="status-card">

            <strong>Summary</strong>

            <br><br>

            {html.escape(summary)}

        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Requirements
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "📑 Regulatory requirements"
    )

    if not requirements:

        st.info(
            "No specific requirements were identified "
            "that could be supported by the retrieved evidence."
        )

    else:

        for (
            index,
            requirement,
        ) in enumerate(
            requirements,
            start=1,
        ):

            render_requirement(
                requirement,
                index,
            )

    # --------------------------------------------------------
    # Next steps
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "➡️ Recommended next steps"
    )

    if next_steps:

        for step in next_steps:

            st.markdown(
                f"- {step}"
            )

    else:

        st.write(
            "No specific next steps were generated."
        )

    # --------------------------------------------------------
    # Warning
    # --------------------------------------------------------

    risk_warning = analysis.get(
        "risk_warning",
        "",
    )

    if risk_warning:

        st.markdown("---")

        st.markdown(
            f"""
            <div class="warning-box">

                <strong>
                    ⚠️ Important
                </strong>

                <br><br>

                {html.escape(risk_warning)}

            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Grants
    # --------------------------------------------------------

    grant = analysis.get(
        "grant_or_incentive",
        "",
    )

    if grant:

        st.markdown("---")

        st.subheader(
            "💡 Grants or incentives"
        )

        st.info(
            grant
        )

    # --------------------------------------------------------
    # Sources
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "🔗 Retrieved official sources"
    )

    for item in evidence:

        render_source(
            item
        )

    # --------------------------------------------------------
    # Raw JSON
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader(
        "🧾 Structured assessment data"
    )

    with st.expander(
        "View raw JSON"
    ):

        st.json(
            analysis
        )

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    json_data = json.dumps(
        analysis,
        indent=2,
        ensure_ascii=False,
    )

    st.download_button(
        label="⬇️ Download assessment JSON",

        data=json_data,

        file_name=(
            "ecocomply_assessment.json"
        ),

        mime="application/json",

        use_container_width=True,
    )

    # --------------------------------------------------------
    # Limitations
    # --------------------------------------------------------

    limitations = analysis.get(
        "limitations",
        [],
    )

    st.markdown("---")

    st.subheader(
        "⚠️ Limitations"
    )

    if limitations:

        for limitation in limitations:

            st.markdown(
                f"- {limitation}"
            )

    else:

        st.markdown(
            "- Regulatory applicability can "
            "depend on site-specific facts."
        )

        st.markdown(
            "- This assessment is not legal advice."
        )

        st.markdown(
            "- EcoComply only analyzes the evidence "
            "it was able to retrieve."
        )

    # --------------------------------------------------------
    # Final disclaimer
    # --------------------------------------------------------

    st.markdown("---")

    st.caption(
        "EcoComply provides a preliminary educational "
        "assessment and does not replace professional "
        "legal, environmental, or regulatory advice."
    )


# ============================================================
# EMPTY STATE
# ============================================================

else:

    st.markdown("---")

    col1, col2, col3 = (
        st.columns(3)
    )

    with col1:

        st.markdown(
            """
            ### 🔎 Retrieve

            Identify likely regulatory topics
            and retrieve material directly from
            official government sources.
            """
        )

    with col2:

        st.markdown(
            """
            ### 🧠 Analyze

            Compare the business description
            against the retrieved regulatory
            evidence.
            """
        )

    with col3:

        st.markdown(
            """
            ### 🧾 Explain

            Show the requirement, business
            evidence, reasoning, citation,
            source, and recommended action.
            """
        )

    st.markdown("---")

    st.info(
        "Enter a business description above "
        "to begin."
    )
