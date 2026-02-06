import streamlit as st
import os
import asyncio
import json
import logging
import threading
import time
from pathlib import Path

# Load environment variables from .env file
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

from CreditDecisionAgent import make_agent, run_credit_decision

# Logging: file logger for UI runs (path configurable via CREDIT_DECISION_LOG)
LOG_FILE = os.getenv("CREDIT_DECISION_LOG", "credit_decision.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    filename=LOG_FILE,
    filemode="a",
)
logger = logging.getLogger("credit_decision_ui")

# DB tools (Strands wrappers) for persisting and querying applications
from CreditDecisionStrandsDBTools import (
    insert_application,
    update_application_status,
    update_application_agent_output,
    list_applications,
    get_application,
    find_latest_by_applicant,
)

# Page configuration following OrchestrateAI guidelines
st.set_page_config(
    page_title="OrchestrateAI - Credit Decision Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .status-approved {
        background-color: #d4edda;
        color: #155724;
        padding: 8px 12px;
        border-radius: 5px;
        font-weight: bold;
    }
    .status-denied {
        background-color: #f8d7da;
        color: #721c24;
        padding: 8px 12px;
        border-radius: 5px;
        font-weight: bold;
    }
    .status-pending {
        background-color: #fff3cd;
        color: #856404;
        padding: 8px 12px;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ==================== HEADER ====================
col1, col2 = st.columns([0.8, 0.2])
with col1:
    st.title("🤖 OrchestrateAI Credit Decision Agent")
    st.markdown("*Multi-agent AI system powered by AWS Bedrock*")
with col2:
    st.markdown("")
    st.markdown("")
    if st.button("🌙 Settings"):
        st.session_state.show_settings = not st.session_state.get("show_settings", False)

# ==================== LEFT PANE: SIDEBAR FORM ====================
st.sidebar.header("📝 Applicant Information")
st.sidebar.markdown("Enter credit application details")

with st.sidebar.form("applicant_form"):
    st.subheader("Personal Info")
    name = st.text_input("Full Name", value="John Smith")
    age = st.number_input("Age", min_value=18, max_value=100, value=35)

    st.subheader("Financial Info")
    income = st.number_input("Annual Income ($)", min_value=0, value=75000, step=1000)
    employment = st.selectbox(
        "Employment Status",
        ["Full-time", "Part-time", "Self-employed", "Unemployed", "Retired"]
    )

    st.subheader("Credit Profile")
    credit_score = st.number_input("Credit Score", min_value=300, max_value=850, value=720)
    dti_ratio = st.slider("DTI Ratio", 0.0, 1.0, 0.35, 0.01)
    existing_debts = st.number_input("Existing Debts ($)", min_value=0, value=25000, step=1000)

    st.subheader("Credit Request")
    requested_credit = st.number_input("Requested Credit ($)", min_value=1000, value=15000, step=1000)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        submitted = st.form_submit_button("🚀 Process", type="primary", use_container_width=True)
    with col_btn2:
        st.form_submit_button("🔄 Clear", type="secondary", use_container_width=True)

# ==================== RIGHT PANE: QUICK STATS ====================
st.sidebar.divider()
st.sidebar.subheader("📊 Quick Stats")
try:
    all_apps = list_applications()
    if all_apps:
        apps_list = json.loads(all_apps) if isinstance(all_apps, str) else all_apps
        total = len(apps_list)
        approved = sum(1 for a in apps_list if a.get("decision") == "APPROVED")
        denied = sum(1 for a in apps_list if a.get("decision") == "DENIED")
        pending = sum(1 for a in apps_list if a.get("decision") == "PENDING")
        
        st.sidebar.metric("Total Apps", total)
        st.sidebar.metric("✅ Approved", approved)
        st.sidebar.metric("❌ Denied", denied)
        st.sidebar.metric("⏳ Pending", pending)
        
        if total > 0:
            approval_rate = (approved / total) * 100
            st.sidebar.metric("Approval Rate", f"{approval_rate:.1f}%")
except:
    st.sidebar.info("No data yet")

# ==================== CENTER PANE: MAIN CONTENT ====================
if submitted:
    # Prepare applicant data
    applicant_data = {
        "applicant_name": name,
        "age": age,
        "income": income,
        "employment_status": employment,
        "credit_score": credit_score,
        "dti_ratio": dti_ratio,
        "existing_debts": existing_debts,
        "requested_credit": requested_credit,
        "source": "web",
        "application_status": "PROCESSING",
        "agent_output": {},
    }

    with st.spinner("🤖 Processing application through AI agents..."):
        try:
            # persist initial application record
            insert_resp = insert_application(applicant_data)
            try:
                insert_obj = json.loads(insert_resp)
                app_id = insert_obj.get("inserted_id")
            except Exception:
                app_id = None

            if app_id:
                st.info(f"Saved application to DB (id={app_id}) - processing...")

            # Initialize agent and run orchestration
            agent = None
            try:
                logger.info("Initializing Strands agent")
                agent = make_agent()
            except Exception as e:
                logger.exception("make_agent() failed: %s", str(e))

            result = None
            if app_id:
                # Run in background thread
                def _agent_worker(aid: int):
                    try:
                        logger.info("Background agent worker started for app_id=%s", aid)
                        run_credit_decision(aid)
                        logger.info("Background agent worker finished for app_id=%s", aid)
                    except Exception:
                        logger.exception("Background agent worker error for app_id=%s", aid)

                t = threading.Thread(target=_agent_worker, args=(app_id,), daemon=True)
                t.start()

                # Poll DB for progress
                placeholder = st.empty()
                poll_start = time.time()
                while True:
                    try:
                        raw_app = get_application(app_id)
                        appobj = json.loads(raw_app) if isinstance(raw_app, str) else raw_app
                        agent_out = appobj.get("agent_output")
                        if agent_out:
                            try:
                                parsed = json.loads(agent_out) if isinstance(agent_out, str) else agent_out
                            except Exception:
                                parsed = agent_out
                            try:
                                placeholder.json(parsed)
                            except Exception:
                                placeholder.text(str(parsed)[:2000])

                            if isinstance(parsed, dict) and parsed.get("processing_status") == "completed":
                                result = parsed
                                break
                    except Exception:
                        placeholder.text("Waiting for agent to persist progress...")

                    if time.time() - poll_start > 300:
                        placeholder.text("Timed out waiting for agent.")
                        break
                    time.sleep(1)

            # Normalize result
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict) and 'result' in parsed:
                        result = parsed['result']
                    else:
                        result = parsed
                except Exception:
                    st.error("❌ Agent returned non-JSON response")
                    st.text(result)
                    result = {"error": "non_json_response"}

            # Display results
            st.success("✅ Application processed successfully!")

            final_decision = result.get('final_decision') if isinstance(result, dict) else None
            audit_report = result.get('audit_report') if isinstance(result, dict) else None
            data_collection = result.get('data_collection') if isinstance(result, dict) else None
            risk_assessment = result.get('risk_assessment') if isinstance(result, dict) else None

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                dec = final_decision.get('decision') if isinstance(final_decision, dict) else 'UNKNOWN'
                st.metric("Decision", dec)
            with col2:
                conf = final_decision.get('confidence') if isinstance(final_decision, dict) else 0
                st.metric("Confidence", f"{conf}%")
            with col3:
                audit_score = audit_report.get('audit_compliance_score') if isinstance(audit_report, dict) else 0
                st.metric("Audit Score", f"{audit_score}/100")

            # Detailed tabs
            tab_progress, tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["🛰️ Progress", "📊 Data", "⚠️ Risk", "🤖 Decision", "📋 Audit", "📄 Full"]
            )

            with tab1:
                st.subheader("Data Collection")
                if data_collection and not data_collection.get('error'):
                    st.json(data_collection)
                else:
                    st.error("No data collection results")

            with tab2:
                st.subheader("Risk Assessment")
                if risk_assessment and not risk_assessment.get('error'):
                    st.json(risk_assessment)
                else:
                    st.error("No risk assessment results")

            with tab3:
                st.subheader("Final Decision")
                if final_decision and not final_decision.get('error'):
                    decision = final_decision.get('decision', 'UNKNOWN')
                    if decision == 'APPROVE':
                        st.success("✅ Application Approved!")
                    elif decision == 'DENY':
                        st.error("❌ Application Denied")
                    elif decision == 'REFER':
                        st.warning("⚠️ Referred for Manual Review")
                    st.json(final_decision)
                else:
                    st.error("No decision results")

            with tab4:
                st.subheader("Audit Report")
                if audit_report and not audit_report.get('error'):
                    st.json(audit_report)
                else:
                    st.error("No audit results")

            with tab5:
                st.subheader("Full Report")
                st.json(result)

            with tab_progress:
                st.subheader("Processing Status")
                proc_status = result.get("processing_status") if isinstance(result, dict) else None
                st.markdown(f"**Status:** {proc_status or 'unknown'}")

            # Update database
            try:
                if app_id and final_decision:
                    decision = final_decision.get("decision") or "UNKNOWN"
                    confidence = final_decision.get("confidence")
                    update_application_status(app_id, decision, reason=final_decision.get("reason"), confidence=confidence)
                    update_application_agent_output(app_id, result)
                    st.text(f"Saved application id: {app_id}")
            except Exception as e:
                logger.exception("Failed to update DB: %s", str(e))

        except Exception as e:
            st.error(f"❌ Error processing application: {str(e)}")
            st.exception(e)
            logger.exception("Error processing application: %s", str(e))

else:
    # Welcome message when no submission
    st.info("👈 Fill out the form in the sidebar and click 'Process' to get started!")

    st.header("🔍 OrchestrateAI Credit Decision System")
    st.markdown("""
    Multi-agent AI system powered by AWS Bedrock:

    ### 🤖 Multi-Agent Architecture
    - **📊 Data Collector**: Analyzes applicant data completeness and quality
    - **⚠️ Risk Assessor**: Evaluates credit risk using AI analysis
    - **🤖 Decision Engine**: Makes approval/denial decisions with reasoning
    - **📋 Audit Agent**: Ensures compliance and maintains audit trails

    ### ✅ Key Benefits
    - ⚡ **Faster Approvals**: Automated processing reduces decision time
    - 📉 **Better Accuracy**: Advanced risk assessment improves results
    - 🔍 **Fully Auditable**: Complete decision reasoning and compliance tracking
    """)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("🎯 Quick Start")
        st.markdown("Try with the sample data already loaded in the form")
    with col2:
        if st.button("Load Sample", use_container_width=True):
            st.rerun()

# ==================== FOOTER ====================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #35B8FF;'>
    <strong>Powered by OrchestrateAI</strong><br>
    Multi-Agent Credit Decision System | AWS Bedrock & Anthropic Claude
</div>
""", unsafe_allow_html=True)
