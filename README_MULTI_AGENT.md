# Credit Decision AI — Multi-Agent README

This repository implements a multi-agent credit decision system using Strands + AWS Bedrock (Anthropic Claude).

Summary
- Four independent agents: DataCollector (Haiku), RiskAssessor (Sonnet), DecisionMaker (Sonnet), Auditor (Sonnet).
- `CreditDecisionAgent_MultiAgent.py` contains the agent classes and the `OrchestratorAgent`.
- `CreditDecisionAgent.py` is a lightweight wrapper exposing `run_credit_decision(app_id)` as a Strands tool and a CLI entrypoint.
- UI: `credit_decision_ui.py` (Streamlit) — left sidebar form, center results, right dashboard.
- DB tools: `CreditDecisionStrandsDBTools.py` (insert/get/update/list functions).

Quick local run
1. Activate virtualenv:

```powershell
.\.venv\Scripts\Activate.ps1
```

2. Start Streamlit UI:

```powershell
python -m streamlit run credit_decision_ui.py --server.port=8501
# Open http://localhost:8501
```

3. Insert and test via CLI (useful for integration tests):

```powershell
# Ensure DB is reachable and has an application record
python CreditDecisionAgent.py --application_id <ID>
```

Notes for testing
- The orchestrator persists intermediate outputs to the `agent_output` JSON column so the UI can poll and display live progress.
- Use `insert_application` from `CreditDecisionStrandsDBTools.py` or the Streamlit form to create an application ID.
- Check DB `status` field to observe PROCESSING → APPROVED/DENIED/REFER/ERROR transitions.

Deployment
- The app is container-ready (`Dockerfile`) and has recommended App Runner / EC2 deployment instructions in `DEPLOYMENT_SUMMARY.md` and `AWS_DEPLOYMENT_GUIDE.md`.
- Ensure AWS credentials and Bedrock access are configured for production.

Troubleshooting
- If port 8501 is in use, stop other Python/Streamlit processes or change the port.
- If Bedrock models fail, verify AWS region and credentials and that the model IDs are authorized for your account.

Contact
- For changes to agents or pipeline flow, edit `CreditDecisionAgent_MultiAgent.py` and update `TECHNICAL_FLOW_DOCUMENTATION.md`.

---
Last updated: February 2026
