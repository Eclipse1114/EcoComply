import json
import os
from groq import Groq
import streamlit as st

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoComply - AI Environmental Assistant",
    page_icon="🌱",
    layout="wide",
)

# ---------------------------------------------------------
# Initialize Groq Client
# ---------------------------------------------------------
groq_key = os.getenv("GROQ_API_KEY")
if not groq_key and "GROQ_API_KEY" in st.secrets:
    groq_key = st.secrets["GROQ_API_KEY"]

client = Groq(api_key=groq_key)

# ---------------------------------------------------------
# Custom Leafy Green & Aqua/Sky Blue CSS Styling
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    /* Global Color Variables */
    :root {
        --leafy-green: #2E7D32;
        --leafy-green-dark: #1B5E20;
        --aqua-blue: #0288D1;
        --sky-blue-light: #E0F7FA;
    }

    /* Main Header Styling */
    .main-title {
        color: var(--leafy-green);
        font-weight: 800;
        font-size: 2.5rem;
        margin-bottom: 0px;
    }
    
    .sub-caption {
        color: var(--aqua-blue);
        font-size: 1.1rem;
        font-weight: 500;
        margin-bottom: 25px;
    }

    /* Primary Buttons (Leafy Green Gradient) */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, var(--leafy-green), var(--leafy-green-dark)) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:first-child:hover {
        background: linear-gradient(135deg, var(--leafy-green-dark), #003300) !important;
        box-shadow: 0 4px 12px rgba(46, 125, 50, 0.3) !important;
    }

    /* Sidebar Header Accent */
    [data-testid="stSidebar"] {
        background-color: #F4FBF7 !important;
        border-right: 2px solid #C8E6C9 !important;
    }
    
    [data-testid="stSidebar"] h2 {
        color: var(--leafy-green) !important;
    }

    /* Executive Summary Callout Box (Sky Blue Light Theme) */
    .summary-box {
        background-color: var(--sky-blue-light);
        border-left: 6px solid var(--aqua-blue);
        padding: 16px;
        border-radius: 6px;
        color: #004D40;
        font-size: 1.05rem;
        margin-bottom: 20px;
    }

    /* Custom Metric Card (Leafy Green & Aqua Highlight) */
    .metric-card {
        background: white;
        border: 1px solid #B2EBF2;
        border-top: 4px solid var(--aqua-blue);
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .metric-title {
        font-size: 0.85rem;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--leafy-green);
        margin-top: 4px;
    }

    /* Section Subheaders */
    h3 {
        color: var(--leafy-green) !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# App Headers
# ---------------------------------------------------------
st.markdown(
    "<h1 class='main-title'>🌱 EcoComply</h1>", unsafe_allow_html=True
)
st.markdown(
    "<p class='sub-caption'>AI-Powered Environmental Safety & Compliance Assistant for Small Businesses</p>",
    unsafe_allow_html=True,
)

SYSTEM_PROMPT = """
You are EcoComply, an expert AI Environmental Safety & Compliance Assistant for small businesses.

Your goal is to translate dense environmental safety laws, EPA guidelines, and local regulations into actionable, plain-English guidance.

CRITICAL INSTRUCTIONS:
1. Ground answers strictly in official EPA/OSHA statutory standards.
2. Provide exact legal citations (e.g., "40 CFR § 262.15").
3. AUDIT THE INPUT: If the user explicitly states they already perform a compliant practice (e.g., "storing in metal drums"), acknowledge that action as compliant. Do NOT tell them to do what they already state they are doing. Instead, focus the action checklist on MISSING REQUIREMENTS, GAP ANALYSIS, or NEXT-STEP PROCEDURES (e.g., secondary containment, grounding wires, drum labeling, or inspection logs).
4. Always respond ONLY in valid JSON matching this schema:

{
  "business_type": "Extracted business sector",
  "applicable_statute": "Exact EPA/OSHA rule or Code of Federal Regulations title",
  "summary": "2-sentence plain English summary acknowledging existing compliant actions and highlighting key remaining requirements",
  "action_checklist": [
    "Step 1: Specific gap or next physical action item",
    "Step 2: Specific gap or next physical action item",
    "Step 3: Specific gap or next physical action item"
  ],
  "risk_warning": "Potential fines, penalties, or environmental hazards of non-compliance",
  "grant_or_incentive": "Relevant small business assistance program, state EPA grant, or penalty relief policy"
}
"""


@st.cache_data(show_spinner=False)
def generate_compliance_report(business_description: str) -> dict:
    """Calls Groq API (Llama-3.3-70b) to generate structured compliance data."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"My business profile: {business_description}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return json.loads(response.choices[0].message.content)


# ---------------------------------------------------------
# Sidebar - User Inputs & Presets
# ---------------------------------------------------------
with st.sidebar:
    st.header("🏢 Business Profile")

    st.subheader("Quick Presets (Demo)")
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
        "Auto Body Shop (Paint & Solvents)": "I run an auto body shop in Michigan. We spray paint 5 cars a week using solvent-based paints and store leftover thinners in metal drums.",
        "Commercial Bakery (Ovens & Waste)": "I operate a commercial bakery that runs 3 large gas ovens 12 hours a day and generates bulk food waste and grease.",
        "Furniture Refinishing (Wood Dust & Stains)": "I run a small woodworking and furniture restoration shop that uses chemical strippers, lacquer finishes, and generates heavy sawdust.",
    }

    default_text = preset_texts.get(preset, "")

    user_input = st.text_area(
        "Describe your business operations:",
        value=default_text,
        placeholder="e.g., I operate a small metal fabrication shop that uses solvent degreasers...",
        height=180,
    )

    submit_btn = st.button(
        "⚡ Generate Compliance Report",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------
# Main Layout
# ---------------------------------------------------------
if submit_btn:
    if not user_input.strip():
        st.warning(
            "Please enter a business description or select a preset from the sidebar."
        )
    else:
        with st.spinner(
            "Analyzing EPA regulations and building compliance checklist..."
        ):
            try:
                report = generate_compliance_report(user_input)
                st.session_state["report"] = report
            except Exception as e:
                st.error(
                    f"Error generating report. Make sure GROQ_API_KEY is set correctly. Details: {e}"
                )

# Display Results from Session State
if "report" in st.session_state:
    report = st.session_state["report"]

    st.subheader(
        f"Compliance Analysis: {report.get('business_type', 'Business Summary')}"
    )

    # Custom Cards Styled Row
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Governing Regulation / Code</div>
                <div class="metric-value">{report.get('applicable_statute', 'N/A')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top-color: #D32F2F;">
                <div class="metric-title">Compliance Risk / Fine Warning</div>
                <div class="metric-value" style="color: #D32F2F; font-size: 0.95rem;">{report.get('risk_warning', 'High Compliance Area')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Executive Summary in Aqua Sky-Blue Callout Box
    st.subheader("📋 Executive Summary")
    st.markdown(
        f"""
        <div class="summary-box">
            {report.get('summary', 'No summary provided.')}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Interactive Action Checklist
    st.subheader("✅ Actionable Compliance Checklist")
    st.write(
        "Check off steps as your facility completes physical compliance actions:"
    )

    checklist = report.get("action_checklist", [])
    for idx, step in enumerate(checklist):
        st.checkbox(step, key=f"step_{idx}")

    st.markdown("---")

    # Grants & Penalty Relief
    st.subheader("💡 Small Business Grants & Support Programs")
    st.success(
        report.get(
            "grant_or_incentive",
            "Check local SBDC or EPA region office for compliance grants.",
        )
    )

    # Export Report Button
    st.markdown("### 📥 Export Report")

    md_export = f"""# EcoComply Assessment Report
**Business Sector:** {report.get('business_type')}
**Governing Regulation:** {report.get('applicable_statute')}

## Summary
{report.get('summary')}

## Action Checklist
"""
    for item in checklist:
        md_export += f"- [ ] {item}\n"

    md_export += f"\n## Penalty & Hazard Warning\n{report.get('risk_warning')}\n"
    md_export += f"\n## Available Support Programs\n{report.get('grant_or_incentive')}\n"

    st.download_button(
        label="📄 Download Assessment (.md)",
        data=md_export,
        file_name="EcoComply_Report.md",
        mime="text/markdown",
    )
