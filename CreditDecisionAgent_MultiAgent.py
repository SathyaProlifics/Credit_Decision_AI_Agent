import os
import json
import boto3
import logging
import time
from datetime import datetime
from typing import Any, Dict
from bedrock_agentcore._utils import endpoints

from strands import tool, Agent
from strands.models import BedrockModel

region = boto3.session.Session().region_name or "us-east-1"
logger = logging.getLogger("credit_decision_agent")
logger.setLevel(logging.DEBUG)  # Ensure DEBUG level is set

# Import DB tools (these are `@tool` wrappers but callable as functions)
from CreditDecisionStrandsDBTools import (
    get_application,
    insert_application,
    update_application_status,
    update_application_agent_output,
)


# ==================== INDEPENDENT AGENTS ====================

class DataCollectorAgent:
    """Independent Agent 1: Focuses on data collection and completeness"""
    
    def __init__(self):
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"  # Efficient for data collection
        self.name = "DataCollector"
        
    def analyze(self, applicant: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze applicant data completeness and quality"""
        
        # Helper to coerce numeric values
        def _to_float(val, percent_ok=False):
            try:
                if val is None:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).strip()
                if percent_ok and s.endswith('%'):
                    return float(s.rstrip('%').replace(',',''))/100.0
                return float(s.replace(',',''))
            except Exception:
                return 0.0

        income_f = _to_float(applicant.get("income", 0))
        dti_ratio_f = _to_float(applicant.get("dti_ratio", 0), percent_ok=True)
        existing_debts_f = _to_float(applicant.get("existing_debts", 0))
        requested_credit_f = _to_float(applicant.get("requested_credit", 0))

        prompt = f"""As a CREDIT DATA COLLECTION SPECIALIST, analyze this applicant's data:

Name: {applicant.get('applicant_name', 'Unknown')}
Age: {applicant.get('age', 'N/A')}
Income: ${income_f:,.2f}
Employment: {applicant.get('employment_status', 'Unknown')}
Credit Score: {applicant.get('credit_score', 'Unknown')}
DTI Ratio: {dti_ratio_f:.2%}
Existing Debts: ${existing_debts_f:,.2f}
Requested Credit: ${requested_credit_f:,.2f}

Provide analysis in JSON with: data_completeness_score, quality_assessment, key_risk_indicators, positive_factors, missing_data_recommendations, profile_summary."""

        return self._invoke_bedrock(prompt)
    
    def _invoke_bedrock(self, prompt: str) -> Dict[str, Any]:
        """Call Bedrock Claude model"""
        logger.debug(f"{self.name} agent: Invoking Bedrock with model {self.model_id}")
        try:
            client = boto3.client("bedrock-runtime", region_name=region)
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}]
            })
            logger.debug(f"{self.name} agent: Sending request to Bedrock")
            response = client.invoke_model(modelId=self.model_id, body=body)
            text = json.loads(response["body"].read()).get("content", [])[0].get("text", "")
            logger.debug(f"{self.name} agent: Received response from Bedrock (length: {len(text)})")
            try:
                result = json.loads(text)
                logger.info(f"{self.name} agent: Successfully parsed JSON response")
                return result
            except Exception as e:
                logger.warning(f"{self.name} agent: Failed to parse JSON response: {e}")
                return {"analysis": text, "format": "text"}
        except Exception as e:
            logger.exception(f"{self.name} agent failed during Bedrock invocation: {e}")
            return {"error": str(e), "agent": self.name}


class RiskAssessorAgent:
    """Independent Agent 2: Focuses on credit risk assessment"""
    
    def __init__(self):
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # More capable for analysis
        self.name = "RiskAssessor"
        
    def assess(self, applicant: Dict[str, Any], collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess credit risk"""
        
        prompt = f"""As a CREDIT RISK ASSESSMENT SPECIALIST, evaluate this application:

APPLICANT DATA:
{json.dumps(applicant, indent=2)}

COLLECTED DATA ANALYSIS:
{json.dumps(collected_data, indent=2)}

Provide risk assessment in JSON with: overall_risk_score (1-100), risk_category (Low/Medium/High/Very High), key_risk_factors, mitigating_factors, recommended_credit_limit, suggested_interest_rate_range."""

        return self._invoke_bedrock(prompt)
    
    def _invoke_bedrock(self, prompt: str) -> Dict[str, Any]:
        """Call Bedrock Claude model"""
        logger.info(f"{self.name} AGENT: Starting Bedrock invocation with model {self.model_id}")
        start_time = time.time()
        try:
            client = boto3.client("bedrock-runtime", region_name=region)
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500 if self.name != "DataCollector" else 1000,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}]
            })
            logger.debug(f"{self.name} AGENT: Request body prepared ({len(body)} bytes), invoking Bedrock")
            invoke_start = time.time()
            response = client.invoke_model(modelId=self.model_id, body=body)
            invoke_elapsed = time.time() - invoke_start
            
            text = json.loads(response["body"].read()).get("content", [])[0].get("text", "")
            logger.debug(f"{self.name} AGENT: Received Bedrock response ({len(text)} chars, API time={invoke_elapsed:.2f}s)")
            
            try:
                result = json.loads(text)
                total_elapsed = time.time() - start_time
                logger.info(f"{self.name} AGENT: Successfully parsed JSON (total time={total_elapsed:.2f}s)")
                return result
            except Exception as e:
                logger.warning(f"{self.name} AGENT: Failed to parse JSON response: {e}. Returning raw text.")
                return {"analysis": text, "format": "text", "agent": self.name}
        except Exception as e:
            total_elapsed = time.time() - start_time
            logger.error(f"{self.name} AGENT: FAILED after {total_elapsed:.2f}s: {type(e).__name__}: {e}", exc_info=True)
            return {"error": str(e), "agent": self.name}


class DecisionMakerAgent:
    """Independent Agent 3: Focuses on making approval/denial decisions"""
    
    def __init__(self):
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Advanced reasoning
        self.name = "DecisionMaker"
        
    def decide(self, applicant: Dict[str, Any], risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Make final credit decision"""
        logger.info(f"{self.name} agent: Starting decision process")
        
        prompt = f"""As a SENIOR CREDIT UNDERWRITER, make a decision on this application:

APPLICANT:
{json.dumps(applicant, indent=2)}

RISK ASSESSMENT:
{json.dumps(risk_assessment, indent=2)}

DECISION REQUIRED: Choose one of APPROVE, DENY, or REFER.

For APPROVE include: credit_limit, interest_rate, term_length_months, conditions.
For all decisions include: confidence (1-100), detailed_reasoning.

Respond with ONLY a JSON object with keys: decision, credit_limit, interest_rate, term_length_months, conditions, confidence, detailed_reasoning."""

        return self._invoke_bedrock(prompt)
    
    def _invoke_bedrock(self, prompt: str) -> Dict[str, Any]:
        """Call Bedrock Claude model"""
        logger.debug(f"{self.name} agent: Invoking Bedrock with model {self.model_id}")
        try:
            client = boto3.client("bedrock-runtime", region_name=region)
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}]
            })
            logger.debug(f"{self.name} agent: Sending request to Bedrock")
            response = client.invoke_model(modelId=self.model_id, body=body)
            text = json.loads(response["body"].read()).get("content", [])[0].get("text", "")
            logger.debug(f"{self.name} agent: Received response from Bedrock (length: {len(text)})")
            try:
                result = json.loads(text)
                logger.info(f"{self.name} agent: Successfully parsed decision response")
                return result
            except Exception as e:
                logger.warning(f"{self.name} agent: Failed to parse JSON response: {e}")
                return {"analysis": text, "format": "text"}
        except Exception as e:
            logger.exception(f"{self.name} agent failed during Bedrock invocation: {e}")
            return {"error": str(e), "agent": self.name}


class AuditAgent:
    """Independent Agent 4: Focuses on compliance and audit"""
    
    def __init__(self):
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Thorough analysis
        self.name = "Auditor"
        
    def audit(self, applicant: Dict[str, Any], collected_data: Dict[str, Any], 
              risk_assessment: Dict[str, Any], final_decision: Dict[str, Any]) -> Dict[str, Any]:
        """Audit the entire decision process"""
        logger.info(f"{self.name} agent: Starting audit process")
        
        prompt = f"""As a CREDIT AUDIT & COMPLIANCE SPECIALIST, review this complete decision audit:

APPLICANT:
{json.dumps(applicant, indent=2)}

COLLECTED DATA:
{json.dumps(collected_data, indent=2)}

RISK ASSESSMENT:
{json.dumps(risk_assessment, indent=2)}

FINAL DECISION:
{json.dumps(final_decision, indent=2)}

Provide comprehensive audit report in JSON with: audit_compliance_score (1-100), compliance_issues (list), regulatory_flags, recommendations, audit_trail_summary, decision_justification_strength."""

        return self._invoke_bedrock(prompt)
    
    def _invoke_bedrock(self, prompt: str) -> Dict[str, Any]:
        """Call Bedrock Claude model"""
        logger.debug(f"{self.name} agent: Invoking Bedrock with model {self.model_id}")
        try:
            client = boto3.client("bedrock-runtime", region_name=region)
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}]
            })
            logger.debug(f"{self.name} agent: Sending request to Bedrock")
            response = client.invoke_model(modelId=self.model_id, body=body)
            text = json.loads(response["body"].read()).get("content", [])[0].get("text", "")
            logger.debug(f"{self.name} agent: Received response from Bedrock (length: {len(text)})")
            try:
                result = json.loads(text)
                logger.info(f"{self.name} agent: Successfully parsed audit report")
                return result
            except Exception as e:
                logger.warning(f"{self.name} agent: Failed to parse JSON response: {e}")
                return {"analysis": text, "format": "text"}
        except Exception as e:
            logger.exception(f"{self.name} agent failed during Bedrock invocation: {e}")
            return {"error": str(e), "agent": self.name}


class OrchestratorAgent:
    """Coordinator Agent: Orchestrates the multi-agent workflow"""
    
    def __init__(self):
        self.name = "Orchestrator"
        self.data_collector = DataCollectorAgent()
        self.risk_assessor = RiskAssessorAgent()
        self.decision_maker = DecisionMakerAgent()
        self.auditor = AuditAgent()
    
    def process_application(self, application_id: int) -> Dict[str, Any]:
        """Coordinate multi-agent processing pipeline"""
        logger.info(f"Orchestrator: Starting process_application for id={application_id}")
        
        progress = []
        
        try:
            # Fetch application
            logger.debug(f"Orchestrator: Fetching application {application_id} from DB")
            raw = get_application(application_id)
            logger.debug(f"Orchestrator: Received raw response from get_application")
            app_row = json.loads(raw)
            if app_row.get("error"):
                logger.error(f"Orchestrator: get_application returned error for id={application_id}: {app_row.get('error')}")
                return {"error": "application_not_found"}
            logger.info(f"Orchestrator: Successfully fetched application {application_id}")
            
            # Normalize applicant data
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
            logger.debug(f"Orchestrator: Normalized applicant data")
            
            logger.debug(f"Orchestrator: Updating status to PROCESSING for id={application_id}")
            update_application_status(application_id, "PROCESSING")
            
            # ========== AGENT 1: DATA COLLECTION ==========
            logger.info(f"Orchestrator: Starting Agent 1 (DataCollector) for id={application_id}")
            progress.append(f"[{datetime.now().isoformat()}] Agent 1 (DataCollector) starting...")
            update_application_agent_output(application_id, {
                "processing_status": "step1_data_collection",
                "progress": progress
            })
            
            data_collection = self.data_collector.analyze(applicant)
            logger.info(f"Orchestrator: Agent 1 (DataCollector) completed for id={application_id}")
            progress.append(f"[{datetime.now().isoformat()}] Agent 1 (DataCollector) completed")
            logger.debug(f"Orchestrator: Updating agent_output with data_collection results")
            update_application_agent_output(application_id, {
                "processing_status": "step1_data_collection",
                "progress": progress,
                "data_collection": data_collection
            })
            
            # ========== AGENT 2: RISK ASSESSMENT ==========
            logger.info(f"Orchestrator: Starting Agent 2 (RiskAssessor) for id={application_id}")
            progress.append(f"[{datetime.now().isoformat()}] Agent 2 (RiskAssessor) starting...")
            update_application_agent_output(application_id, {
                "processing_status": "step2_risk_assessment",
                "progress": progress,
                "data_collection": data_collection
            })
            
            risk_assessment = self.risk_assessor.assess(applicant, data_collection)
            logger.info(f"Orchestrator: Agent 2 (RiskAssessor) completed for id={application_id}")
            progress.append(f"[{datetime.now().isoformat()}] Agent 2 (RiskAssessor) completed")
            logger.debug(f"Orchestrator: Updating agent_output with risk_assessment results")
            update_application_agent_output(application_id, {
                "processing_status": "step2_risk_assessment",
                "progress": progress,
                "data_collection": data_collection,
                "risk_assessment": risk_assessment
            })
            
            # ========== AGENT 3: DECISION MAKING ==========
            logger.info(f"Orchestrator: Starting Agent 3 (DecisionMaker) for id={application_id}")
            progress.append(f"[{datetime.now().isoformat()}] Agent 3 (DecisionMaker) starting...")
            update_application_agent_output(application_id, {
                "processing_status": "step3_decision",
                "progress": progress,
                "data_collection": data_collection,
                "risk_assessment": risk_assessment
            })
            
            final_decision = self.decision_maker.decide(applicant, risk_assessment)
            logger.info(f"Orchestrator: Agent 3 (DecisionMaker) completed for id={application_id}")
            progress.append(f"[{datetime.now().isoformat()}] Agent 3 (DecisionMaker) completed")
            logger.debug(f"Orchestrator: Updating agent_output with final_decision results")
            update_application_agent_output(application_id, {
                "processing_status": "step3_decision",
                "progress": progress,
                "data_collection": data_collection,
                "risk_assessment": risk_assessment,
                "final_decision": final_decision
            })
            
            # ========== AGENT 4: AUDIT ==========
            logger.info(f"Orchestrator: Starting Agent 4 (Auditor) for id={application_id}")
            progress.append(f"[{datetime.now().isoformat()}] Agent 4 (Auditor) starting...")
            update_application_agent_output(application_id, {
                "processing_status": "step4_audit",
                "progress": progress,
                "data_collection": data_collection,
                "risk_assessment": risk_assessment,
                "final_decision": final_decision
            })
            
            audit_report = self.auditor.audit(applicant, data_collection, risk_assessment, final_decision)
            logger.info(f"Orchestrator: Agent 4 (Auditor) completed for id={application_id}")
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
            }
            
            # Update database
            logger.debug(f"Orchestrator: Updating agent_output with final result for id={application_id}")
            update_application_agent_output(application_id, result)
            
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
            
            logger.info(f"Orchestrator: Setting final status for id={application_id}: {status} (confidence={confidence})")
            logger.debug(f"Orchestrator: Updating application_status to {status}")
            update_application_status(application_id, status, reason=reason, confidence=confidence)
            logger.info(f"Orchestrator: Successfully completed processing for id={application_id}")
            
            return {"result": result}
            
        except Exception as e:
            logger.exception(f"Orchestrator failed for id={application_id}: {e}")
            try:
                logger.debug(f"Orchestrator: Attempting to update status to ERROR for id={application_id}")
                update_application_status(application_id, "ERROR", reason=str(e))
            except Exception as update_err:
                logger.error(f"Orchestrator: Failed to update status to ERROR: {update_err}")
            return {"error": "orchestration_failed", "message": str(e)}


# ==================== TOOL WRAPPER FOR ORCHESTRATOR ====================

@tool
def run_credit_decision(application_id: int) -> str:
    """Multi-agent orchestrator: Coordinates 4 independent agents"""
    orchestrator = OrchestratorAgent()
    result = orchestrator.process_application(application_id)
    return json.dumps(result)


# ==================== LEGACY SINGLE-AGENT INTERFACE ====================

def make_agent() -> Agent:
    """Construct a Strands Agent (single-agent interface for backward compatibility)"""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    agent = Agent(
        model=BedrockModel(model_id=model_id),
        system_prompt="You are an autonomous multi-agent credit decisioning system orchestrator. Your sub-agents handle data collection, risk assessment, decision making, and auditing.",
        tools=[run_credit_decision],
    )
    return agent


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--application_id", type=int, help="Application ID to process")
    args = p.parse_args()

    if args.application_id:
        out = run_credit_decision(args.application_id)
        print(out)
    else:
        print("Usage: python CreditDecisionAgent_MultiAgent.py --application_id <ID>")
        print("\nThis system now uses a TRUE MULTI-AGENT architecture:")
        print("  - Agent 1: DataCollector (analyzes data completeness)")
        print("  - Agent 2: RiskAssessor (evaluates credit risk)")
        print("  - Agent 3: DecisionMaker (makes approval/denial decisions)")  
        print("  - Agent 4: Auditor (ensures compliance)")
