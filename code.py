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


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="EcoComply",
    page_icon="🌱",
    layout="wide",
)

# ------------------------------------------------------------
# Playwright browser location
# ------------------------------------------------------------

PLAYWRIGHT_BROWSER_PATH = os.path.expanduser(
    "~/.cache/ms-playwright"
)

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = (
    PLAYWRIGHT_BROWSER_PATH
)


# ------------------------------------------------------------
# Official regulatory sources
# ------------------------------------------------------------

OFFICIAL_SOURCES = {
    "eCFR": "https://www.ecfr.gov/",
    "EPA": "https://www.epa.gov/laws-regulations",
    "Michigan EGLE": (
        "https://www.michigan.gov/egle/"
        "regulatory-assistance/regulations"
    ),
}


# ------------------------------------------------------------
# Domains EcoComply is allowed to retrieve
# ------------------------------------------------------------

ALLOWED_DOMAINS = {
    "ecfr.gov",
    "www.ecfr.gov",
    "epa.gov",
    "www.epa.gov",
    "michigan.gov",
    "www.michigan.gov",
}


# ============================================================
# PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>

        /* -------------------------------------------------- */
        /* Main application                                   */
        /* -------------------------------------------------- */

        .stApp {
            background-color: #ffffff;
            color: #1f2937;
        }

        /* -------------------------------------------------- */
        /* Sidebar                                             */
        /* -------------------------------------------------- */

        [data-testid="stSidebar"] {
            background-color: #f5f7f6;
            border-right: 1px solid #dfe5e1;
        }

        [data-testid="stSidebar"] * {
            color: #1f2937;
        }

        /* -------------------------------------------------- */
        /* Headings                                             */
        /* -------------------------------------------------- */

        h1, h2, h3, h4 {
            color: #173b27;
        }

        /* -------------------------------------------------- */
        /* Hero                                                */
        /* -------------------------------------------------- */

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
            max-width: 850px;
        }

        /* -------------------------------------------------- */
        /* Cards                                                */
        /* -------------------------------------------------- */

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

        /* -------------------------------------------------- */
        /* Buttons                                              */
        /* -------------------------------------------------- */

        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
        }

        /* -------------------------------------------------- */
        /* Text inputs                                          */
        /* -------------------------------------------------- */

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
    """
    Make sure the normal Playwright Chromium browser exists.

    The Python Playwright package and Chromium browser binaries
    are installed separately on Streamlit Community Cloud.
    """

    os.makedirs(
        PLAYWRIGHT_BROWSER_PATH,
        exist_ok=True,
    )

    # Ask Playwright where it expects Chromium.
    with sync_playwright() as p:
        executable = p.chromium.executable_path

    # Already installed.
    if os.path.exists(executable):
        return

    st.info(
        "First-time setup: installing Chromium for "
        "EcoComply. This may take a minute."
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

    # Verify installation.
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
# UTILITY FUNCTIONS
# ============================================================

def clean_text(text, max_length=12000):
    """
    Normalize scraped text and prevent enormous prompts.
    """

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
    """
    Only allow retrieval from approved official domains.
    """

    try:
        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        return (
            parsed.scheme in {"http", "https"}
            and domain in ALLOWED_DOMAINS
        )

    except Exception:
        return False


def extract_cfr_references(text):
    """
    Find CFR-style references such as:

    40 CFR Part 63
    40 CFR 63.111
    40 CFR § 63.111
    """

    if not text:
        return []

    patterns = [
        (
            r"\b40\s+CFR\s+"
            r"(?:Part\s+)?"
            r"\d+(?:\.\d+)*"
            r"(?:\([a-zA-Z0-9]+\))?"
        ),
        (
            r"\b\d+\s+CFR\s+"
            r"(?:Part\s+)?"
            r"\d+(?:\.\d+)*"
            r"(?:\([a-zA-Z0-9]+\))?"
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

    return references[:10]


def safe_urljoin(base_url, href):
    """
    Join URLs while preventing navigation to unapproved domains.
    """

    try:

        full_url = urljoin(
            base_url,
            href,
        )

        if is_allowed_url(full_url):
            return full_url

    except Exception:
        pass

    return None


# ============================================================
# REGULATORY SEARCH
# ============================================================

def build_search_urls(business_description):
    """
    Build official regulatory search URLs.

    The AI never chooses arbitrary websites.
    """

    query = quote_plus(
        business_description
    )

    return [
        (
            "eCFR",
            (
                "https://www.ecfr.gov/search?"
                f"search%5Bquery%5D={query}"
            ),
        ),
    ]


# ============================================================
# PLAYWRIGHT RETRIEVAL
# ============================================================

def scrape_page(page, url):
    """
    Retrieve readable text and links from an official page.
    """

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

        page.wait_for_timeout(1000)

        title = page.title()

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=10000
        )

        body_text = clean_text(
            body_text
        )

        links = []

        anchors = page.locator("a")

        for i in range(
            min(anchors.count(), 100)
        ):

            try:

                anchor = anchors.nth(i)

                href = anchor.get_attribute(
                    "href"
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
            "url": url,
            "title": clean_text(
                title,
                500,
            ),
            "text": body_text,
            "links": list(
                dict.fromkeys(
                    links
                )
            )[:50],
        }

    except Exception:
        return None


def retrieve_regulatory_evidence(
    business_description
):
    """
    Retrieve regulatory evidence using Playwright.

    EcoComply focuses on official sources rather than
    arbitrary websites.
    """

    ensure_playwright_browser()

    search_urls = build_search_urls(
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

            for source_name, search_url in search_urls:

                result = scrape_page(
                    page,
                    search_url,
                )

                if not result:
                    continue

                evidence.append(
                    {
                        "source": source_name,
                        "url": result["url"],
                        "title": result["title"],
                        "text": result["text"],
                    }
                )

                # Follow a limited number of official
                # eCFR result links.
                for link in result["links"][:10]:

                    if not is_allowed_url(
                        link
                    ):
                        continue

                    if (
                        "ecfr.gov"
                        not in urlparse(
                            link
                        ).netloc.lower()
                    ):
                        continue

                    sub_result = scrape_page(
                        page,
                        link,
                    )

                    if (
                        sub_result
                        and sub_result["text"]
                    ):

                        evidence.append(
                            {
                                "source": source_name,
                                "url": sub_result[
                                    "url"
                                ],
                                "title": sub_result[
                                    "title"
                                ],
                                "text": sub_result[
                                    "text"
                                ],
                            }
                        )

        finally:

            browser.close()

    # --------------------------------------------------------
    # Remove duplicate URLs
    # --------------------------------------------------------

    unique = {}

    for item in evidence:

        key = item["url"]

        if key not in unique:
            unique[key] = item

    evidence = list(
        unique.values()
    )

    # --------------------------------------------------------
    # Relevance scoring
    # --------------------------------------------------------

    filtered = []

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
        )

        if not text:
            continue

        score = 0

        lower_text = text.lower()

        for word in business_words:

            if word in lower_text:
                score += 1

        if "cfr" in lower_text:
            score += 2

        if "regulation" in lower_text:
            score += 1

        if "environmental" in lower_text:
            score += 1

        if "requirement" in lower_text:
            score += 1

        # CFR references are especially useful.
        cfr_refs = extract_cfr_references(
            text
        )

        score += len(cfr_refs)

        item["relevance_score"] = score

        item["cfr_references"] = cfr_refs

        filtered.append(item)

    filtered.sort(
        key=lambda x: x.get(
            "relevance_score",
            0,
        ),
        reverse=True,
    )

    return filtered[:15]


# ============================================================
# AI EVIDENCE PACKET
# ============================================================

def build_evidence_prompt(evidence):
    """
    Build a compact evidence packet.

    Groq's current limit for this model is 8,000 tokens
    per minute, so we intentionally cap the evidence.
    """

    chunks = []

    total_chars = 0

    MAX_TOTAL_CHARS = 18000
    MAX_SOURCE_CHARS = 3500
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
Title: {item.get("title", "")}
URL: {item.get("url", "")}
CFR references found: {", ".join(cfr_refs)}

Retrieved regulatory text:
{source_text}
"""

        chunks.append(chunk)

        total_chars += len(chunk)

    return "\n".join(chunks)


# ============================================================
# GROQ CLIENT
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
    """
    Ask the model to perform a structured preliminary
    compliance analysis.
    """

    client = get_groq_client()

    evidence_text = (
        build_evidence_prompt(
            evidence
        )
    )

    system_prompt = """
You are EcoComply, an environmental compliance
analysis assistant.

Your job is to perform a PRELIMINARY educational
assessment.

CRITICAL RULES:

1. Use ONLY the regulatory evidence supplied
   in the user message.

2. Never invent a regulation.

3. Never invent a CFR citation.

4. Never invent a source URL.

5. Never invent a penalty.

6. Never invent a grant or incentive.

7. If the evidence is insufficient, say
   "Needs Review."

8. Do not claim that a business is legally
   compliant with certainty.

9. Distinguish between an actual regulatory
   requirement and a recommendation.

10. Do not assume every environmental regulation
    applies to every business.

11. Only list requirements supported by the
    supplied evidence.

12. Every requirement must contain a citation
    and source URL from the supplied evidence.

13. If the evidence does not contain enough
    information, say so.

14. Be conservative. False confidence is worse
    than flagging something for review.

15. Do not use your general knowledge to fill
    gaps in the retrieved evidence.

STATUS DEFINITIONS:

Compliant:
The supplied business evidence appears to
satisfy the retrieved requirement.

Needs Review:
There is not enough information to determine
compliance confidently.

Action Required:
The supplied business evidence appears
inconsistent with a retrieved requirement.

Not Applicable:
The retrieved requirement clearly does not
apply to this business.

Return ONLY valid JSON.
"""

    user_prompt = f"""
BUSINESS DESCRIPTION:

{business_description[:4000]}


REGULATORY EVIDENCE:

{evidence_text}


Return this exact JSON structure:

{{
  "business_type": "string",
  "overall_status": "Compliant | Needs Review | Action Required",
  "summary": "string",

  "requirements": [
    {{
      "title": "string",
      "status": "Compliant | Needs Review | Action Required | Not Applicable",
      "requirement": "string",
      "explanation": "string",
      "business_evidence": "string",
      "action": "string",
      "citation": "string",
      "source_title": "string",
      "source_url": "string",
      "confidence": "High | Medium | Low"
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

Only use information supported by the supplied
regulatory evidence.

Do not make up missing information.

If there is not enough evidence to make a
determination, use "Needs Review."
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

        # Reduced from 7000 to help stay comfortably
        # within the Groq token limit.
        max_tokens=4500,
    )

    raw = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    # --------------------------------------------------------
    # Remove accidental Markdown JSON fences
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        return json.loads(
            raw
        )

    except json.JSONDecodeError:

        # Try extracting the JSON object if the model
        # accidentally added explanatory text.
        start = raw.find("{")
        end = raw.rfind("}")

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

def status_emoji(status):

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


def render_source(item):

    source = html.escape(
        item.get(
            "source",
            "Unknown",
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

    st.markdown(
        f"""
        <div class="source-card">
            <strong>{source}</strong><br>
            {title}<br>
            <span class="small-muted">
                Relevance score: {score}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_allowed_url(url):

        st.markdown(
            f"[Open source]({url})"
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
        "research powered by official sources."
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

    for name, url in (
        OFFICIAL_SOURCES.items()
    ):

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
# MAIN PAGE
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

    Business description → official regulatory sources
    → retrieved evidence → AI analysis
    → traceable requirements and next steps.
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

    progress = st.empty()

    # --------------------------------------------------------
    # Retrieve evidence
    # --------------------------------------------------------

    try:

        progress.info(
            "Searching official regulatory sources..."
        )

        evidence = (
            retrieve_regulatory_evidence(
                business_description
            )
        )

        progress.success(
            f"Retrieved {len(evidence)} "
            "official source pages."
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

        st.warning(
            "EcoComply could not retrieve enough "
            "regulatory evidence to perform "
            "an analysis."
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

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

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
    # Count statuses
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
            "No specific requirements were "
            "identified from the retrieved evidence."
        )

    else:

        for index, requirement in enumerate(
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
    # Risk warning
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
    # Grants / incentives
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
    # Download JSON
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

            Search controlled official
            regulatory sources rather than
            relying on arbitrary web pages.
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
            and recommended action.
            """
        )

    st.markdown("---")

    st.info(
        "Enter a business description above "
        "to begin."
    )
