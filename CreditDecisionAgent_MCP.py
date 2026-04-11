"""Credit Decision AI Agent backed by MCP Server for all DB operations.

Instead of calling the database directly, this agent connects to the
running MCP server (credit_decision_mcp_server.py) over SSE and uses
MCP tools for all CRUD operations.

The multi-agent pipeline (DataCollector → RiskAssessor → DecisionMaker → Auditor)
remains the same — only the DB layer is swapped to MCP.

Usage:
    # Ensure MCP server is running first:
    #   python credit_decision_mcp_server.py --transport sse --port 8080

    python CreditDecisionAgent_MCP.py --application_id 1
    python CreditDecisionAgent_MCP.py --application_id 1 --mcp-url http://127.0.0.1:8080/sse
"""

import json
import logging
import argparse
from datetime import datetime
from typing import Any, Dict

from strands.tools.mcp import MCPClient
from mcp.client.sse import sse_client

# Reuse the existing multi-agent classes (they don't touch DB directly)
from CreditDecisionAgent_MultiAgent import (
    DataCollectorAgent,
    RiskAssessorAgent,
    DecisionMakerAgent,
    AuditAgent,
)

logger = logging.getLogger("credit_decision_mcp_agent")
logger.setLevel(logging.DEBUG)

# Add console handler if none exists
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(ch)


# ==================== MCP DB Client ====================

class MCPDatabaseClient:
    """Wraps MCP tool calls to provide the same interface as the direct DB tools."""

    def __init__(self, mcp_url: str = "http://127.0.0.1:8080/sse"):
        self.mcp_url = mcp_url
        self.mcp_client = MCPClient(lambda: sse_client(self.mcp_url))
        self.mcp_client.start()
        tools = self.mcp_client.list_tools_sync()
        tool_names = [t.tool_name for t in tools]
        logger.info(f"MCP client connected to {mcp_url} — tools: {tool_names}")

    def stop(self):
        self.mcp_client.stop(None, None, None)

    _call_counter = 0

    def _call(self, tool_name: str, arguments: dict) -> str:
        """Call an MCP tool and return the text result."""
        MCPDatabaseClient._call_counter += 1
        tool_use_id = f"mcp-call-{MCPDatabaseClient._call_counter}"
        result = self.mcp_client.call_tool_sync(tool_use_id, tool_name, arguments)
        # Strands MCPClient returns a dict with 'content' list of blocks
        if isinstance(result, dict) and "content" in result:
            texts = [block.get("text", "") if isinstance(block, dict) else getattr(block, "text", str(block))
                     for block in result["content"]]
            return "\n".join(texts)
        return str(result)

    def get_application(self, application_id: int) -> str:
        return self._call("get_application", {"application_id": application_id})

    def insert_application(self, app: dict) -> str:
        return self._call("insert_application", app)

    def update_application_status(self, application_id: int, status: str,
                                   reason: str = None, confidence: float = None) -> str:
        args: Dict[str, Any] = {"application_id": application_id, "status": status}
        if reason is not None:
            args["reason"] = reason
        if confidence is not None:
            args["confidence"] = confidence
        return self._call("update_application_status", args)

    def update_application_agent_output(self, application_id: int, agent_output: Any) -> str:
        payload = json.dumps(agent_output) if not isinstance(agent_output, str) else agent_output
        return self._call("update_application_agent_output", {
            "application_id": application_id,
            "agent_output": payload,
        })

    def list_applications(self, limit: int = 10) -> str:
        return self._call("list_applications", {"limit": limit})

    def find_latest_by_applicant(self, applicant_name: str) -> str:
        return self._call("find_latest_by_applicant", {"applicant_name": applicant_name})


# ==================== MCP-Backed Orchestrator ====================

class MCPOrchestratorAgent:
    """Same pipeline as OrchestratorAgent but uses MCP server for all DB ops."""

    def __init__(self, db: MCPDatabaseClient):
        self.db = db
        self.data_collector = DataCollectorAgent()
        self.risk_assessor = RiskAssessorAgent()
        self.decision_maker = DecisionMakerAgent()
        self.auditor = AuditAgent()

    def process_application(self, application_id: int) -> Dict[str, Any]:
        logger.info(f"MCP Orchestrator: Processing application {application_id}")
        progress = []

        try:
            # Fetch application via MCP
            raw = self.db.get_application(application_id)
            app_row = json.loads(raw)
            if app_row.get("error"):
                logger.error(f"Application not found: {app_row}")
                return {"error": "application_not_found"}

            applicant = {
                "applicant_name": app_row.get("applicant_name"),
                "age": app_row.get("age"),
                "income": app_row.get("income"),
                "employment_status": app_row.get("employment_status"),
                "credit_score": app_row.get("credit_score"),
                "dti_ratio": app_row.get("dti_ratio"),
                "existing_debts": app_row.get("existing_debts"),
                "requested_credit": app_row.get("requested_credit"),
            }

            self.db.update_application_status(application_id, "PROCESSING")

            # ========== AGENT 1: DATA COLLECTION ==========
            logger.info("Starting Agent 1: DataCollector")
            progress.append(f"[{datetime.now().isoformat()}] Agent 1 (DataCollector) starting...")
            self.db.update_application_agent_output(application_id, {
                "processing_status": "step1_data_collection", "progress": progress
            })

            data_collection = self.data_collector.analyze(applicant)
            progress.append(f"[{datetime.now().isoformat()}] Agent 1 (DataCollector) completed")
            self.db.update_application_agent_output(application_id, {
                "processing_status": "step1_complete", "progress": progress,
                "data_collection": data_collection
            })

            # ========== AGENT 2: RISK ASSESSMENT ==========
            logger.info("Starting Agent 2: RiskAssessor")
            progress.append(f"[{datetime.now().isoformat()}] Agent 2 (RiskAssessor) starting...")
            self.db.update_application_agent_output(application_id, {
                "processing_status": "step2_risk_assessment", "progress": progress,
                "data_collection": data_collection
            })

            risk_assessment = self.risk_assessor.assess(applicant, data_collection)
            progress.append(f"[{datetime.now().isoformat()}] Agent 2 (RiskAssessor) completed")
            self.db.update_application_agent_output(application_id, {
                "processing_status": "step2_complete", "progress": progress,
                "data_collection": data_collection, "risk_assessment": risk_assessment
            })

            # ========== AGENT 3: DECISION MAKING ==========
            logger.info("Starting Agent 3: DecisionMaker")
            progress.append(f"[{datetime.now().isoformat()}] Agent 3 (DecisionMaker) starting...")
            self.db.update_application_agent_output(application_id, {
                "processing_status": "step3_decision", "progress": progress,
                "data_collection": data_collection, "risk_assessment": risk_assessment
            })

            final_decision = self.decision_maker.decide(applicant, risk_assessment)
            progress.append(f"[{datetime.now().isoformat()}] Agent 3 (DecisionMaker) completed")
            self.db.update_application_agent_output(application_id, {
                "processing_status": "step3_complete", "progress": progress,
                "data_collection": data_collection, "risk_assessment": risk_assessment,
                "final_decision": final_decision
            })

            # ========== AGENT 4: AUDIT ==========
            logger.info("Starting Agent 4: Auditor")
            progress.append(f"[{datetime.now().isoformat()}] Agent 4 (Auditor) starting...")
            self.db.update_application_agent_output(application_id, {
                "processing_status": "step4_audit", "progress": progress,
                "data_collection": data_collection, "risk_assessment": risk_assessment,
                "final_decision": final_decision
            })

            audit_report = self.auditor.audit(applicant, data_collection, risk_assessment, final_decision)
            progress.append(f"[{datetime.now().isoformat()}] Agent 4 (Auditor) completed")

            # Compile final result
            result = {
                "timestamp": datetime.now().isoformat(),
                "processing_status": "completed",
                "applicant": applicant,
                "data_collection": data_collection,
                "risk_assessment": risk_assessment,
                "final_decision": final_decision,
                "audit_report": audit_report,
                "progress": progress,
                "agents_used": ["DataCollector", "RiskAssessor", "DecisionMaker", "Auditor"],
                "db_backend": "MCP Server",
            }

            self.db.update_application_agent_output(application_id, result)

            # Set final status
            if isinstance(final_decision, dict):
                decision_str = str(final_decision.get("decision", "")).upper()
                if decision_str == "APPROVE":
                    status = "APPROVED"
                elif decision_str == "DENY":
                    status = "DENIED"
                else:
                    status = "REFER"
                confidence = final_decision.get("confidence")
                reason = final_decision.get("detailed_reasoning", "")
            else:
                status = "REFER"
                confidence = None
                reason = "Could not parse decision"

            self.db.update_application_status(application_id, status, reason=reason, confidence=confidence)
            logger.info(f"MCP Orchestrator: Completed — status={status}, confidence={confidence}")

            return {"result": result}

        except Exception as e:
            logger.exception(f"MCP Orchestrator failed for id={application_id}: {e}")
            try:
                self.db.update_application_status(application_id, "ERROR", reason=str(e))
            except Exception:
                pass
            return {"error": "orchestration_failed", "message": str(e)}


# ==================== Entry Point ====================

def main():
    parser = argparse.ArgumentParser(description="Credit Decision Agent (MCP-backed)")
    parser.add_argument("--application_id", type=int, required=True, help="Application ID to process")
    parser.add_argument("--mcp-url", default="http://127.0.0.1:8080/sse",
                        help="MCP server SSE endpoint (default: http://127.0.0.1:8080/sse)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  CREDIT DECISION AI AGENT (MCP Server Backend)")
    print(f"{'='*60}")
    print(f"  MCP Server:     {args.mcp_url}")
    print(f"  Application ID: {args.application_id}")
    print(f"  Pipeline:       DataCollector → RiskAssessor → DecisionMaker → Auditor")
    print(f"{'='*60}\n")

    db = MCPDatabaseClient(args.mcp_url)
    try:
        orchestrator = MCPOrchestratorAgent(db)
        result = orchestrator.process_application(args.application_id)
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.stop()


if __name__ == "__main__":
    main()
