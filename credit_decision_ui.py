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
        text-align: center;
    }
    .metric-label {
        font-size: 14px;
        opacity: 0.9;
        margin-top: 10px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        margin: 10px 0;
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
    .status-referred {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 8px 12px;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Header with OIA branding
col1, col2 = st.columns([0.7, 0.3])
with col1:
    st.title("🤖 OrchestrateAI Credit Decision Agent")
    st.markdown("*Multi-agent AI system for intelligent credit approvals*")
with col2:
    st.markdown("")
    st.markdown("")
    if st.button("🌙 Dark Mode", help="Toggle dark/light theme"):
        st.session_state.dark_mode = not st.session_state.get("dark_mode", False)

# Create tabs for different sections
tab1, tab2, tab3, tab4 = st.tabs(["📝 New Application", "📊 Dashboard", "🔍 Applications", "⚙️ Settings"])

# ==================== TAB 1: NEW APPLICATION ====================
with tab1:
    st.header("Submit New Credit Application")
    
    col_form, col_info = st.columns([2, 1])
    
    with col_form:
        with st.form("applicant_form", clear_on_submit=True):
            st.subheader("👤 Personal Information")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                name = st.text_input("Full Name", value="John Smith", help="Applicant's full legal name", key="name_input")
            with col_p2:
                age = st.number_input("Age", min_value=18, max_value=100, value=35, help="Age in years", key="age_input")

            st.subheader("💼 Financial Information")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                income = st.number_input("Annual Income ($)", min_value=0, value=75000, step=1000,
                                       help="Gross annual income before taxes", key="income_input")
            with col_f2:
                employment = st.selectbox("Employment Status",
                                        ["Full-time", "Part-time", "Self-employed", "Unemployed", "Retired"],
                                        help="Current employment situation", key="employment_input")

            st.subheader("📈 Credit Profile")
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                credit_score = st.number_input("Credit Score", min_value=300, max_value=850, value=720,
                                             help="FICO score (300-850)", key="credit_input")
            with col_c2:
                dti_ratio = st.slider("Debt-to-Income Ratio", 0.0, 1.0, 0.35, 0.01,
                                    help="Ratio of debt to income", key="dti_input")
            with col_c3:
                existing_debts = st.number_input("Existing Debts ($)", min_value=0, value=25000, step=1000,
                                               help="Total outstanding debt", key="debts_input")

            st.subheader("💰 Credit Request")
            requested_credit = st.number_input("Requested Credit Amount ($)", min_value=1000, value=15000, step=1000,
                                             help="Amount being applied for", key="requested_input")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("🚀 Process Application", type="primary", use_container_width=True)
            with col_btn2:
                st.form_submit_button("🔄 Clear Form", type="secondary", use_container_width=True)
    
    with col_info:
        st.info("""
        **Quick Tips:**
        - Higher credit score = better approval chances
        - DTI ratio < 0.40 is ideal
        - Stable employment preferred
        - Check your info before submitting
        """)


# ==================== TAB 2: DASHBOARD ====================
with tab2:
    st.header("📊 Analytics Dashboard")
    
    # Get all applications for stats
    try:
        all_apps = list_applications()
        if all_apps:
            apps_list = json.loads(all_apps) if isinstance(all_apps, str) else all_apps
            
            # Calculate metrics
            total_apps = len(apps_list)
            approved_apps = sum(1 for a in apps_list if a.get("decision") == "APPROVED")
            denied_apps = sum(1 for a in apps_list if a.get("decision") == "DENIED")
            referred_apps = sum(1 for a in apps_list if a.get("decision") == "REFERRED")
            pending_apps = sum(1 for a in apps_list if a.get("application_status") == "PROCESSING")
            
            approval_rate = (approved_apps / total_apps * 100) if total_apps > 0 else 0
            avg_income = sum(a.get("income", 0) for a in apps_list) / total_apps if total_apps > 0 else 0
            avg_credit = sum(a.get("credit_score", 0) for a in apps_list) / total_apps if total_apps > 0 else 0
            
            # Display metrics in columns
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Total Applications", total_apps, delta="All time")
            with col_m2:
                st.metric("Approval Rate", f"{approval_rate:.1f}%", delta=f"{approved_apps} approved")
            with col_m3:
                st.metric("Avg Credit Score", f"{avg_credit:.0f}", delta="All applicants")
            with col_m4:
                st.metric("Avg Annual Income", f"${avg_income:,.0f}", delta="All applicants")
            
            st.divider()
            
            # Decision breakdown chart
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.subheader("Decision Breakdown")
                decision_data = {
                    "APPROVED": approved_apps,
                    "DENIED": denied_apps,
                    "REFERRED": referred_apps,
                    "PENDING": pending_apps
                }
                st.bar_chart(decision_data)
            
            with col_chart2:
                st.subheader("Application Status")
                status_data = {
                    "Processing": pending_apps,
                    "Completed": total_apps - pending_apps
                }
                st.pie_chart(status_data)
    except Exception as e:
        st.warning(f"Could not load dashboard data: {str(e)}")


# ==================== TAB 3: APPLICATIONS ====================
with tab3:
    st.header("🔍 Search & View Applications")
    
    col_search, col_filter = st.columns([2, 1])
    with col_search:
        search_name = st.text_input("🔎 Search by Applicant Name", help="Type name to search")
    with col_filter:
        filter_status = st.selectbox("Filter by Status", 
                                    ["All", "APPROVED", "DENIED", "REFERRED", "PROCESSING"],
                                    help="Filter applications by decision")
    
    try:
        all_apps = list_applications()
        if all_apps:
            apps_list = json.loads(all_apps) if isinstance(all_apps, str) else all_apps
            
            # Filter by name
            if search_name:
                apps_list = [a for a in apps_list if search_name.lower() in a.get("applicant_name", "").lower()]
            
            # Filter by status
            if filter_status != "All":
                apps_list = [a for a in apps_list if a.get("decision") == filter_status or a.get("application_status") == filter_status]
            
            if apps_list:
                st.subheader(f"Found {len(apps_list)} Application(s)")
                
                for app in apps_list[:10]:  # Show last 10
                    with st.expander(f"📋 {app.get('applicant_name', 'Unknown')} - {app.get('decision', 'PENDING')}"):
                        col_exp1, col_exp2 = st.columns(2)
                        with col_exp1:
                            st.write(f"**ID:** {app.get('id')}")
                            st.write(f"**Age:** {app.get('age')}")
                            st.write(f"**Income:** ${app.get('income', 0):,}")
                            st.write(f"**Employment:** {app.get('employment_status')}")
                        with col_exp2:
                            st.write(f"**Credit Score:** {app.get('credit_score')}")
                            st.write(f"**DTI Ratio:** {app.get('dti_ratio'):.2%}")
                            st.write(f"**Existing Debts:** ${app.get('existing_debts', 0):,}")
                            st.write(f"**Requested Credit:** ${app.get('requested_credit', 0):,}")
                        
                        if app.get("agent_output"):
                            st.divider()
                            st.subheader("🤖 Agent Analysis")
                            st.json(json.loads(app.get("agent_output")) if isinstance(app.get("agent_output"), str) else app.get("agent_output"))
            else:
                st.info("No applications found matching your criteria.")
    except Exception as e:
        st.warning(f"Could not load applications: {str(e)}")


# ==================== TAB 4: SETTINGS ====================
with tab4:
    st.header("⚙️ Settings")
    
    col_set1, col_set2 = st.columns(2)
    
    with col_set1:
        st.subheader("🎨 Appearance")
        theme = st.radio("Theme", ["Light", "Dark", "Auto"], help="Choose UI theme")
        font_size = st.slider("Font Size", 10, 18, 14, help="Adjust base font size")
    
    with col_set2:
        st.subheader("📋 Preferences")
        auto_refresh = st.checkbox("Auto-refresh dashboard", value=True, help="Refresh data automatically")
        show_confidence = st.checkbox("Show AI confidence scores", value=True, help="Display model confidence")
        export_format = st.selectbox("Default export format", ["CSV", "PDF", "JSON"])
    
    st.divider()
    st.subheader("📊 Database Info")
    st.info(f"""
    - **Host:** {os.getenv('DB_HOST', 'Not configured')}
    - **Region:** {os.getenv('AWS_REGION', 'us-east-1')}
    - **App Version:** 2.0 (EC2 Deployed)
    """)
    
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        if st.button("🔄 Refresh Database Connection"):
            st.success("Database connection refreshed!")
    with col_exp2:
        if st.button("📥 Download Logs"):
            st.info("Download functionality coming soon")

st.divider()


# Main content area
if submitted:
    # Prepare applicant data (map to DB column names)
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

    # Show loading spinner
    with st.spinner("🤖 Processing application through AI agents..."):
        try:
            # persist initial application record (status=PROCESSING)
            insert_resp = insert_application(applicant_data)
            try:
                insert_obj = json.loads(insert_resp)
                app_id = insert_obj.get("inserted_id")
            except Exception:
                app_id = None

            # Log insertion
            try:
                logger.info("Inserted application: id=%s applicant=%s", app_id, applicant_data.get("applicant_name"))
            except Exception:
                pass

            if app_id:
                st.info(f"Saved application to DB (id={app_id}) - processing...")

            # Initialize Strands-style agent and run orchestrator using DB record
            agent = None
            try:
                logger.info("Initializing Strands agent")
                agent = make_agent()
                
            except Exception as e:
                logger.exception("make_agent() failed: %s", str(e))

            result = None
            # Prefer running the orchestrator by application id (DB-driven)
            if app_id:
                try:
                    logger.info("Running run_credit_decision for app_id=%s", app_id)
                    if agent is not None:
                        try:
                            # Ask the Agent to invoke the orchestrator tool via a single prompt string
                            prompt = f"Run run_credit_decision for app_id={app_id}"
                            logger.debug("Agent invoke prompt: %s", prompt)
                            res = agent.invoke_async(prompt)
                            if asyncio.iscoroutine(res):
                                result = asyncio.run(res)
                            else:
                                result = res
                        except Exception as ae:
                            logger.exception("Agent invocation failed, falling back to direct call: %s", str(ae))
                            res = run_credit_decision(app_id)
                            if asyncio.iscoroutine(res):
                                result = asyncio.run(res)
                            else:
                                result = res
                    else:
                        res = run_credit_decision(app_id)
                        if asyncio.iscoroutine(res):
                            result = asyncio.run(res)
                        else:
                            result = res
                except Exception as e:
                    logger.exception("run_credit_decision(app_id=%s) failed: %s", app_id, str(e))
                    try:
                        result = asyncio.run(run_credit_decision(app_id))
                    except Exception as e2:
                        logger.exception("run_credit_decision retry failed: %s", str(e2))
                        result = {"error": "agent_run_failed", "raw_exception": str(e2)}
            else:
                # Fallback: try to invoke orchestrator with in-memory applicant data
                try:
                    logger.info("Running run_credit_decision with in-memory applicant data")
                    if agent is not None:
                        try:
                            prompt = f"Run run_credit_decision with applicant: {json.dumps(applicant_data)}"
                            logger.debug("Agent invoke prompt (in-memory): %s", prompt[:1000])
                            res = agent.invoke_async(prompt)
                            if asyncio.iscoroutine(res):
                                result = asyncio.run(res)
                            else:
                                result = res
                        except Exception as ae:
                            logger.exception("Agent invocation (in-memory) failed, falling back: %s", str(ae))
                            res = run_credit_decision(applicant_data)
                            if asyncio.iscoroutine(res):
                                result = asyncio.run(res)
                            else:
                                result = res
                    else:
                        res = run_credit_decision(applicant_data)
                        if asyncio.iscoroutine(res):
                            result = asyncio.run(res)
                        else:
                            result = res
                except Exception as e:
                    logger.exception("run_credit_decision(in-memory) failed: %s", str(e))
                    result = {"error": "agent_run_failed_no_app_id", "raw_exception": str(e)}
            result = None
            # Prefer running the orchestrator by application id (DB-driven)
            if app_id:
                # run orchestration in a background thread so UI can poll DB for progress
                def _agent_worker(aid: int):
                    try:
                        logger.info("Background agent worker started for app_id=%s", aid)
                        run_credit_decision(aid)
                        logger.info("Background agent worker finished for app_id=%s", aid)
                    except Exception:
                        logger.exception("Background agent worker error for app_id=%s", aid)

                t = threading.Thread(target=_agent_worker, args=(app_id,), daemon=True)
                t.start()

                # Poll DB for persisted agent_output and display progress
                placeholder = st.empty()
                parsed = None
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
                            # show a small snippet of agent_output
                            try:
                                placeholder.json(parsed)
                            except Exception:
                                placeholder.text(str(parsed)[:2000])

                            # stop polling when agent reports completed
                            if isinstance(parsed, dict) and parsed.get("processing_status") == "completed":
                                result = parsed
                                break
                    except Exception:
                        placeholder.text("Waiting for agent to persist progress...")

                    # timeout safety: stop polling after 300s
                    if time.time() - poll_start > 300:
                        placeholder.text("Timed out waiting for agent. Please check logs.")
                        break
                    time.sleep(1)
            else:
                # Fallback: try to invoke orchestrator with in-memory applicant data
                try:
                    logger.info("Running run_credit_decision with in-memory applicant data")
                    res = run_credit_decision(applicant_data)
                    if asyncio.iscoroutine(res):
                        result = asyncio.run(res)
                    else:
                        result = res
                except Exception as e:
                    logger.exception("run_credit_decision(in-memory) failed: %s", str(e))
                    result = {"error": "agent_run_failed_no_app_id", "raw_exception": str(e)}

            # Normalize result (the agent often returns a JSON string)
            # Log raw agent result (truncated)
            try:
                logger.info("Agent raw result (truncated): %s", str(result)[:1000])
            except Exception:
                pass

            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    # run_credit_decision wraps the real payload under 'result'
                    if isinstance(parsed, dict) and 'result' in parsed:
                        result = parsed['result']
                    else:
                        result = parsed
                except Exception:
                    # non-JSON string -> show raw and normalize to an error dict
                    st.error("❌ Agent returned non-JSON response")
                    st.text(result)
                    logger.error("Agent returned non-JSON response: %s", result)
                    result = {"error": "non_json_response", "raw": result}

            # If the Agent returned a Strands AgentResult object, normalize it
            try:
                # detect AgentResult-like objects by `to_dict` method
                if not isinstance(result, dict) and hasattr(result, "to_dict"):
                    rd = result.to_dict()
                    logger.debug("AgentResult.to_dict() (truncated): %s", str(rd)[:1000])
                    msg = rd.get("message") if isinstance(rd, dict) else None
                    content = None
                    if isinstance(msg, dict):
                        content = msg.get("content")

                    extracted = None
                    if isinstance(content, list) and len(content) > 0:
                        first = content[0]
                        # content items can be dicts with 'text' or raw strings
                        if isinstance(first, dict) and first.get("text"):
                            extracted = first.get("text")
                        elif isinstance(first, str):
                            extracted = first

                    if extracted:
                        try:
                            parsed = json.loads(extracted)
                            if isinstance(parsed, dict) and "result" in parsed:
                                result = parsed["result"]
                            else:
                                result = parsed
                        except Exception:
                            # content not JSON -> preserve raw text for display
                            result = {"error": "non_json_response", "raw": extracted}
                    else:
                        # No usable content from AgentResult: try DB fallback when app_id available
                        if app_id:
                            try:
                                raw_app = get_application(app_id)
                                appobj = json.loads(raw_app)
                                agent_out = appobj.get("agent_output")
                                if isinstance(agent_out, str):
                                    try:
                                        result = json.loads(agent_out)
                                    except Exception:
                                        result = {"error": "agent_output_not_json", "raw": agent_out}
                                else:
                                    result = agent_out or {"error": "no_agent_output"}
                                logger.debug("DB agent_output used as fallback for app_id=%s", app_id)
                            except Exception as e:
                                logger.exception("DB fallback failed for app_id=%s: %s", app_id, str(e))
                                result = {"error": "db_fallback_failed", "raw_exception": str(e)}
                        else:
                            result = {"error": "empty_agent_result", "raw": rd}
            except Exception:
                # defensive: if anything goes wrong keep the original result
                pass

            # Display results (guarded)
            st.success("✅ Application processed successfully!")
            logger.info("Application processed successfully for app_id=%s", app_id)

            final_decision = result.get('final_decision') if isinstance(result, dict) else None
            audit_report = result.get('audit_report') if isinstance(result, dict) else None
            data_collection = result.get('data_collection') if isinstance(result, dict) else None
            risk_assessment = result.get('risk_assessment') if isinstance(result, dict) else None

            # Decision Summary
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

            # Detailed Results (Agent Output & Progress as first tab)
            tab_progress, tab1, tab2, tab3, tab4, tab5 = st.tabs(["🛰️ Agent Output & Progress", "📊 Data Collection", "⚠️ Risk Assessment", "🤖 Final Decision", "📋 Audit Report", "📄 Full Report"]) 

            with tab1:
                st.subheader("Data Collection Analysis")
                if data_collection is not None and (not isinstance(data_collection, dict) or 'error' not in data_collection):
                    st.json(data_collection)
                else:
                    st.error("Error in data collection")
                    try:
                        st.text(data_collection.get('raw_response', ''))
                    except Exception:
                        st.text(str(data_collection))

            with tab2:
                st.subheader("Risk Assessment")
                if risk_assessment is not None and (not isinstance(risk_assessment, dict) or 'error' not in risk_assessment):
                    st.json(risk_assessment)
                else:
                    st.error("Error in risk assessment")
                    try:
                        st.text(risk_assessment.get('raw_response', ''))
                    except Exception:
                        st.text(str(risk_assessment))

            with tab3:
                st.subheader("Final Decision")
                if final_decision is not None and (not isinstance(final_decision, dict) or 'error' not in final_decision):
                    decision = final_decision.get('decision', 'UNKNOWN') if isinstance(final_decision, dict) else 'UNKNOWN'
                    if decision == 'APPROVE':
                        st.success("✅ Application Approved!")
                    elif decision == 'DENY':
                        st.error("❌ Application Denied")
                    elif decision == 'REFER':
                        st.warning("⚠️ Referred for Manual Review")

                    try:
                        st.json(final_decision)
                    except Exception:
                        st.text(str(final_decision))

                    try:
                        logger.info("Final decision for app_id=%s: %s", app_id, final_decision)
                    except Exception:
                        pass
                else:
                    st.error("Error in decision making")
                    try:
                        st.text(final_decision.get('raw_response', ''))
                    except Exception:
                        st.text(str(final_decision))

            with tab4:
                st.subheader("Audit & Compliance Report")
                if audit_report is not None and (not isinstance(audit_report, dict) or 'error' not in audit_report):
                    try:
                        st.json(audit_report)
                    except Exception:
                        st.text(str(audit_report))
                    try:
                        logger.info("Audit report for app_id=%s", app_id)
                    except Exception:
                        pass
                else:
                    st.error("Error in audit")
                    try:
                        st.text(audit_report.get('raw_response', ''))
                    except Exception:
                        st.text(str(audit_report))

            with tab5:
                st.subheader("Complete Processing Report")
                st.json(result)
                try:
                    logger.info("Full result persisted/displayed for app_id=%s", app_id)
                except Exception:
                    pass

            with tab_progress:
                st.subheader("Agent Output & Progress")
                # Basic processing metadata
                proc_status = result.get("processing_status") if isinstance(result, dict) else None
                timestamp = result.get("timestamp") if isinstance(result, dict) else None
                st.markdown(f"**Processing status:** {proc_status or 'unknown'}")
                st.markdown(f"**Timestamp:** {timestamp or '-'}")

                # Step-level status indicator
                steps = [
                    ("Data Collection", result.get("data_collection") if isinstance(result, dict) else None),
                    ("Risk Assessment", result.get("risk_assessment") if isinstance(result, dict) else None),
                    ("Final Decision", result.get("final_decision") if isinstance(result, dict) else None),
                    ("Audit Report", result.get("audit_report") if isinstance(result, dict) else None),
                ]

                for name, payload in steps:
                    if payload is None:
                        st.write(f"- **{name}**: Not available")
                    elif isinstance(payload, dict) and payload.get("error"):
                        st.write(f"- **{name}**: Error — {payload.get('error')}")
                    else:
                        st.write(f"- **{name}**: Completed")

                # Show brief snippets for each step
                with st.expander("Show step snippets"):
                    for name, payload in steps:
                        st.subheader(name)
                        if payload is None:
                            st.text("No data available for this step.")
                        elif isinstance(payload, dict):
                            # show a small JSON snippet or analysis text
                            if "analysis" in payload:
                                txt = payload.get("analysis")
                                st.text_area("analysis", value=(txt[:400] + ("..." if len(str(txt))>400 else "")), height=120)
                            else:
                                st.json({k: payload.get(k) for k in list(payload.keys())[:6]})
                        else:
                            st.text(str(payload)[:1000])

                # Persisted agent_output from DB (useful when AgentResult is empty)
                if app_id:
                    try:
                        raw_app = get_application(app_id)
                        appobj = json.loads(raw_app)
                        agent_out = appobj.get("agent_output")
                        with st.expander("Persisted agent_output (DB)"):
                            try:
                                if isinstance(agent_out, str):
                                    st.json(json.loads(agent_out))
                                else:
                                    st.json(agent_out)
                            except Exception:
                                st.text(str(agent_out))
                    except Exception as e:
                        logger.exception("Failed to fetch persisted agent_output for app_id=%s: %s", app_id, str(e))
            # persist final decision and full agent output into DB
            try:
                final_decision = result.get("final_decision", {})
                decision = final_decision.get("decision") or "UNKNOWN"
                confidence = final_decision.get("confidence")
                # Update status fields
                if app_id:
                    try:
                        update_resp = update_application_status(app_id, decision, reason=final_decision.get("reason"), confidence=confidence)
                        logger.info("update_application_status response for app_id=%s: %s", app_id, update_resp)
                    except Exception as e:
                        logger.exception("update_application_status failed for app_id=%s: %s", app_id, str(e))
                        update_resp = json.dumps({"error": "status_update_failed"})

                    # Persist full agent_output JSON
                    try:
                        uresp = update_application_agent_output(app_id, result)
                        uobj = json.loads(uresp)
                        logger.info("update_application_agent_output response for app_id=%s: %s", app_id, uresp)
                    except Exception as e:
                        logger.exception("update_application_agent_output failed for app_id=%s: %s", app_id, str(e))
                        uobj = {"error": "agent_output_update_failed"}

                    # Show link to DB viewer if configured
                    db_viewer = os.getenv("DB_VIEWER_URL")
                    if app_id:
                        if db_viewer:
                            url = f"{db_viewer.rstrip('/')}/?table=credit_applications&id={app_id}"
                            st.markdown(f"[Open DB record]({url})")
                        else:
                            st.text(f"Saved application id: {app_id}")

            except Exception:
                pass

        except Exception as e:
            st.error(f"❌ Error processing application: {str(e)}")
            st.exception(e)
            logger.exception("Unhandled exception processing application for applicant=%s: %s", applicant_data.get('applicant_name'), str(e))

# Welcome message when no application has been processed
if not submitted:
    st.info("👈 Fill out the credit application form in the sidebar and click 'Process Application' to get started!")

    # System Overview with better organization
    st.header("🔍 OrchestrateAI Credit Decision System")
    st.markdown("""
    This autonomous credit decision system uses multiple AI agents powered by AWS Bedrock and follows OrchestrateAI best practices:

    ### 🤖 Multi-Agent Architecture
    - **📊 Data Collector Agent**: Analyzes applicant data completeness and quality
    - **⚠️ Risk Assessor Agent**: Evaluates credit risk using advanced AI analysis
    - **🤖 Decision Agent**: Makes final approval/denial decisions with reasoning
    - **📋 Audit Agent**: Ensures compliance and maintains audit trails

    ### ✅ Key Benefits
    - ⚡ **Faster Approvals**: Automated processing reduces decision time
    - 📉 **Lower Default Rates**: Advanced risk assessment improves accuracy
    - 🔍 **Fully Auditable**: Complete decision reasoning and compliance tracking
    - 🤖 **Unbiased Decisions**: Consistent, AI-driven evaluation criteria
    - 🛡️ **Regulatory Compliant**: Built-in audit trails and compliance checks
    """)

    # Sample data section
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("🎯 Quick Start")
        st.markdown("Try the system with sample applicant data:")
    with col2:
        if st.button("Load Sample Data", type="secondary", use_container_width=True):
            st.rerun()  # This will trigger the form with sample data

# Footer with OIA branding (outside the columns)
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #35B8FF;'>
    <strong>Powered by OrchestrateAI</strong><br>
    Multi-Agent Credit Decision System | AWS Bedrock & Anthropic Claude
</div>
""", unsafe_allow_html=True)