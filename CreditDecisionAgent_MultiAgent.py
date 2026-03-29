import os
import json
import re
import boto3
import logging
import time
from datetime import datetime
from typing import Any, Dict
from bedrock_agentcore._utils import endpoints

from strands import tool, Agent
from strands.models import BedrockModel

# Import LLM provider abstraction layer
from LLMProvider import ModelConfig, LLMFactory, ModelConfigManager

# Import banking rules loader from YAML configuration
from BankingRulesLoader import (
    get_system_context,
    get_credit_decision_rules,
    get_risk_framework,
    get_compliance_rules,
    check_rules_loaded
)

region = boto3.session.Session().region_name or "us-east-1"
logger = logging.getLogger("credit_decision_agent")
logger.setLevel(logging.DEBUG)  # Ensure DEBUG level is set

# Initialize model config manager
config_manager = ModelConfigManager()

# Check if banking rules loaded
if not check_rules_loaded():
    logger.warning("WARNING: Banking rules not loaded - credit decisions may lack regulatory context")

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
        self.name = "DATA_COLLECTOR"
        self.config = config_manager.get_config(self.name)
        logger.debug(f"{self.name} agent initialized with config: provider={self.config.provider}, model={self.config.model_id}")
        
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

        prompt = f"""{get_system_context()}

As a CREDIT DATA COLLECTION SPECIALIST, analyze this applicant's data:

Name: {applicant.get('applicant_name', 'Unknown')}
Age: {applicant.get('age', 'N/A')}
Income: ${income_f:,.2f}
Employment: {applicant.get('employment_status', 'Unknown')}
Credit Score: {applicant.get('credit_score', 'Unknown')}
DTI Ratio: {dti_ratio_f:.2%}
Existing Debts: ${existing_debts_f:,.2f}
Requested Credit: ${requested_credit_f:,.2f}

ANALYSIS REQUIREMENTS:
1. Validate data completeness using regulatory standards
2. Assess data quality against banking standards
3. Identify key risk indicators from the profile
4. Highlight positive factors that support credit decision
5. Recommend missing documentation per compliance requirements

Provide analysis in JSON with: data_completeness_score (1-100), quality_assessment, regulatory_requirements_met, key_risk_indicators, positive_factors, missing_data_recommendations, profile_summary."""

        return self._invoke_llm(prompt)
    
    def _invoke_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM using provider abstraction"""
        logger.debug(f"{self.name} agent: Invoking {self.config.provider}/{self.config.model_id}")
        response = LLMFactory.invoke(prompt, self.config)
        
        if "error" in response:
            logger.error(f"{self.name} agent failed: {response['error']}")
            return response
        
        # If response has parsed_json, extract it
        if "parsed_json" in response:
            logger.info(f"{self.name} agent: Successfully parsed JSON response")
            return response["parsed_json"]
        
        # Try to extract JSON from text response
        text = response.get("text", "")
        if text:
            # Remove markdown code blocks if present
            text_clean = re.sub(r'```json\s*', '', text)
            text_clean = re.sub(r'```\s*', '', text_clean)
            
            # Try to find JSON by matching braces (handles nested structures)
            for start_idx in range(len(text_clean)):
                if text_clean[start_idx] == '{':
                    brace_count = 0
                    for end_idx in range(start_idx, len(text_clean)):
                        if text_clean[end_idx] == '{':
                            brace_count += 1
                        elif text_clean[end_idx] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_candidate = text_clean[start_idx:end_idx + 1]
                                try:
                                    parsed = json.loads(json_candidate)
                                    if "data_completeness_score" in parsed or "quality_assessment" in parsed:
                                        logger.info(f"{self.name} agent: Extracted JSON with collection data from text")
                                        return parsed
                                except json.JSONDecodeError:
                                    pass
                                break
        
        logger.warning(f"{self.name} agent: Could not extract JSON, using fallback")
        return {
            "data_completeness_score": 0,
            "quality_assessment": "insufficient",
            "profile_summary": response.get("text", "No response"),
            "format": "text_fallback"
        }


class RiskAssessorAgent:
    """Independent Agent 2: Focuses on credit risk assessment"""
    
    def __init__(self):
        self.name = "RISK_ASSESSOR"
        self.config = config_manager.get_config(self.name)
        logger.debug(f"{self.name} agent initialized with config: provider={self.config.provider}, model={self.config.model_id}")
        
    def assess(self, applicant: Dict[str, Any], collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess credit risk"""
        
        prompt = f"""{get_system_context()}

{get_risk_framework()}

As a CREDIT RISK ASSESSMENT SPECIALIST, evaluate this application:

APPLICANT DATA:
{json.dumps(applicant, indent=2)}

COLLECTED DATA ANALYSIS:
{json.dumps(collected_data, indent=2)}

RISK ASSESSMENT TASK:
1. Calculate overall_risk_score (1-100) using the risk scoring system
2. Categorize risk (Low/Medium/High/Very High) per banking standards
3. Identify all key_risk_factors from applicant profile
4. Highlight mitigating_factors that reduce risk
5. Recommend credit_limit per risk tier guidelines
6. Suggest interest_rate_range based on risk category
7. Flag any fair lending concerns or patterns requiring escalation
8. Provide regulatory compliance assessment

Provide risk assessment in JSON with: overall_risk_score (1-100), risk_category (Low/Medium/High/Very High), credit_tier, key_risk_factors, mitigating_factors, recommended_credit_limit, suggested_interest_rate_range, regulatory_flags, compliance_notes."""

        return self._invoke_llm(prompt)
    
    def _invoke_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM using provider abstraction"""
        logger.info(f"{self.name} AGENT: Starting invocation with {self.config.provider}/{self.config.model_id}")
        start_time = time.time()
        response = LLMFactory.invoke(prompt, self.config)
        total_elapsed = time.time() - start_time
        
        if "error" in response:
            logger.error(f"{self.name} AGENT: FAILED after {total_elapsed:.2f}s: {response['error']}")
            return response
        
        # If response has parsed_json, extract it
        if "parsed_json" in response:
            logger.info(f"{self.name} AGENT: Successfully parsed JSON (total time={total_elapsed:.2f}s)")
            return response["parsed_json"]
        
        # Try to extract JSON from text response
        text = response.get("text", "")
        if text:
            # Remove markdown code blocks if present
            text_clean = re.sub(r'```json\s*', '', text)
            text_clean = re.sub(r'```\s*', '', text_clean)
            
            # Try to find JSON by matching braces (handles nested structures)
            for start_idx in range(len(text_clean)):
                if text_clean[start_idx] == '{':
                    brace_count = 0
                    for end_idx in range(start_idx, len(text_clean)):
                        if text_clean[end_idx] == '{':
                            brace_count += 1
                        elif text_clean[end_idx] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_candidate = text_clean[start_idx:end_idx + 1]
                                try:
                                    parsed = json.loads(json_candidate)
                                    if "overall_risk_score" in parsed or "risk_category" in parsed:
                                        logger.info(f"{self.name} AGENT: Extracted JSON with risk data from text (total time={total_elapsed:.2f}s)")
                                        return parsed
                                except json.JSONDecodeError:
                                    pass
                                break
        
        logger.warning(f"{self.name} AGENT: Could not extract JSON, using fallback (total time={total_elapsed:.2f}s)")
        return {
            "overall_risk_score": 50,
            "risk_category": "Medium",
            "key_risk_factors": [response.get("text", "No response")],
            "format": "text_fallback",
            "agent": self.name
        }


class DecisionMakerAgent:
    """Independent Agent 3: Focuses on making approval/denial decisions"""
    
    def __init__(self):
        self.name = "DECISION_MAKER"
        self.config = config_manager.get_config(self.name)
        logger.debug(f"{self.name} agent initialized with config: provider={self.config.provider}, model={self.config.model_id}")
        
    def decide(self, applicant: Dict[str, Any], risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Make final credit decision"""
        logger.info(f"{self.name} agent: Starting decision process")
        
        prompt = f"""{get_system_context()}

{get_credit_decision_rules()}

{get_compliance_rules()}

As a SENIOR CREDIT UNDERWRITER, make a COMPLIANT decision on this application:

APPLICANT:
{json.dumps(applicant, indent=2)}

RISK ASSESSMENT:
{json.dumps(risk_assessment, indent=2)}

DECISION REQUIREMENTS:
1. Use the Credit Decision Matrix to determine approval/denial/referral
2. Verify all compliance and fair lending requirements are met
3. Document decision reasoning with specific policy references
4. Include required audit trail elements

DECISION OPTIONS:
- APPROVE: Grant credit with specified terms and conditions
- DENY: Decline application with specific reason code
- REFER: Send to manual review with clear intervention triggers

For APPROVE include: credit_limit (per guidelines), interest_rate (apr string), term_length_months, conditions (list), compensating_factors_used (list).
For DENY include: denial_reason_code, regulatory_notice_required (bool).
For all decisions include: confidence (1-100), detailed_reasoning (2-3 sentences max, cite the key policy rule only).

CRITICAL: Respond with ONLY a compact JSON object. No prose outside the JSON. Keep all string values SHORT.
Required keys: decision, credit_limit, interest_rate, term_length_months, conditions, compensating_factors_used, denial_reason_code, confidence, detailed_reasoning, regulatory_compliance_verified."""

        return self._invoke_llm(prompt)
    
    def _invoke_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM using provider abstraction"""
        logger.debug(f"{self.name} agent: Invoking {self.config.provider}/{self.config.model_id}")
        response = LLMFactory.invoke(prompt, self.config)
        
        if "error" in response:
            logger.exception(f"{self.name} agent failed: {response['error']}")
            return response
        
        # If response has parsed_json, extract it
        if "parsed_json" in response:
            logger.info(f"{self.name} agent: Successfully parsed decision response")
            return response["parsed_json"]
        
        # Try to extract JSON from text response
        text = response.get("text", "")
        if text:
            # Debug: log what we're trying to parse
            logger.debug(f"{self.name} agent: Raw response length={len(text)}, first 400 chars: {text[:400]}")
            
            # Remove markdown code blocks if present
            text_clean = re.sub(r'```json\s*', '', text)
            text_clean = re.sub(r'```\s*', '', text_clean)
            text_clean = text_clean.strip()
            
            logger.debug(f"{self.name} agent: After cleanup length={len(text_clean)}, first 400 chars: {text_clean[:400]}")
            
            # Try to find JSON by matching braces (handles nested structures)
            # Collect ALL JSON objects and prioritize the most complete one
            found_candidates = []
            
            for start_idx in range(len(text_clean)):
                if text_clean[start_idx] == '{':
                    # Try to extract from this position
                    brace_count = 0
                    for end_idx in range(start_idx, len(text_clean)):
                        if text_clean[end_idx] == '{':
                            brace_count += 1
                        elif text_clean[end_idx] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                # Found matching closing brace
                                json_candidate = text_clean[start_idx:end_idx + 1]
                                try:
                                    parsed = json.loads(json_candidate)
                                    # Score this candidate - prefer ones with more decision-related fields
                                    score = 0
                                    if "decision" in parsed:
                                        score += 10
                                    if "credit_limit" in parsed:
                                        score += 5
                                    if "interest_rate" in parsed:
                                        score += 5
                                    if "confidence" in parsed:
                                        score += 3
                                    if "detailed_reasoning" in parsed:
                                        score += 2
                                    if "conditions" in parsed:
                                        score += 5
                                    if "compensating_factors_used" in parsed:
                                        score += 5
                                    
                                    found_candidates.append((start_idx, score, parsed))
                                    logger.debug(f"{self.name} agent: Found JSON at position {start_idx}, score={score}, keys: {list(parsed.keys())}")
                                except json.JSONDecodeError as e:
                                    logger.debug(f"{self.name} agent: JSON parse error at position {start_idx}: {str(e)[:100]}")
                                break
            
            # Sort by score (highest first) and return the best match
            if found_candidates:
                found_candidates.sort(key=lambda x: x[1], reverse=True)
                best_pos, best_score, best_parsed = found_candidates[0]
                
                logger.debug(f"{self.name} agent: Best candidate at position {best_pos} with score {best_score}")
                
                # FIRST CHECK: If this is a text_fallback wrapper, try to extract nested JSON from detailed_reasoning
                if best_parsed.get("format") == "text_fallback" and "detailed_reasoning" in best_parsed:
                    detailed_text = best_parsed["detailed_reasoning"]
                    if isinstance(detailed_text, str) and "{" in detailed_text:
                        logger.debug(f"{self.name} agent: Best candidate is text_fallback, attempting to extract nested JSON from detailed_reasoning")
                        
                        # Strip markdown code blocks from detailed_reasoning string
                        detail_clean = re.sub(r'```json\s*', '', detailed_text)
                        detail_clean = re.sub(r'```\s*', '', detail_clean).strip()
                        
                        # Try full JSON parse first
                        for nested_start in range(len(detail_clean)):
                            if detail_clean[nested_start] == '{':
                                brace_count = 0
                                for nested_end in range(nested_start, len(detail_clean)):
                                    if detail_clean[nested_end] == '{':
                                        brace_count += 1
                                    elif detail_clean[nested_end] == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            nested_json_str = detail_clean[nested_start:nested_end + 1]
                                            try:
                                                nested_parsed = json.loads(nested_json_str)
                                                if "decision" in nested_parsed:
                                                    logger.info(f"{self.name} agent: Extracted complete nested JSON with decision={nested_parsed.get('decision')}, confidence={nested_parsed.get('confidence')}")
                                                    return nested_parsed
                                            except json.JSONDecodeError:
                                                pass
                                            break
                        
                        # FALLBACK: JSON may be truncated - extract decision/confidence via regex
                        decision_match = re.search(r'"decision"\s*:\s*"([^"]+)"', detail_clean)
                        confidence_match = re.search(r'"confidence"\s*:\s*(\d+)', detail_clean)
                        credit_limit_match = re.search(r'"credit_limit"\s*:\s*([\d.]+)', detail_clean)
                        
                        if decision_match:
                            extracted = {
                                "decision": decision_match.group(1).upper(),
                                "confidence": int(confidence_match.group(1)) if confidence_match else 0,
                                "credit_limit": float(credit_limit_match.group(1)) if credit_limit_match else None,
                                "detailed_reasoning": detail_clean,
                                "format": "regex_extracted"
                            }
                            logger.info(f"{self.name} agent: Extracted decision via regex from truncated JSON: decision={extracted['decision']}, confidence={extracted['confidence']}")
                            return extracted
                
                # SECOND CHECK: If the best candidate has decision field, return it
                if "decision" in best_parsed and best_score >= 10:
                    logger.info(f"{self.name} agent: Successfully extracted JSON with decision={best_parsed.get('decision')}, confidence={best_parsed.get('confidence')} from text (position {best_pos}, score {best_score})")
                    return best_parsed
                
                logger.warning(f"{self.name} agent: Best JSON candidate at position {best_pos} has score {best_score} but missing required fields or is text_fallback. All candidates: {[(c[1], list(c[2].keys())) for c in found_candidates[:5]]}")
            else:
                logger.warning(f"{self.name} agent: No valid JSON objects found in response")
            
            # LAST RESORT: Try regex extraction directly on cleaned text (handles truncated JSON)
            decision_match = re.search(r'"decision"\s*:\s*"([^"]+)"', text_clean)
            confidence_match = re.search(r'"confidence"\s*:\s*(\d+)', text_clean)
            credit_limit_match = re.search(r'"credit_limit"\s*:\s*([\d.]+)', text_clean)
            if decision_match:
                extracted = {
                    "decision": decision_match.group(1).upper(),
                    "confidence": int(confidence_match.group(1)) if confidence_match else 0,
                    "credit_limit": float(credit_limit_match.group(1)) if credit_limit_match else None,
                    "detailed_reasoning": text_clean,
                    "format": "regex_extracted"
                }
                logger.info(f"{self.name} agent: Extracted decision via regex from raw text: decision={extracted['decision']}, confidence={extracted['confidence']}")
                return extracted
        
        logger.warning(f"{self.name} agent: Could not extract JSON properly, using fallback")
        return {
            "decision": "REFER",
            "confidence": 0,
            "detailed_reasoning": response.get("text", "No response"),
            "format": "text_fallback"
        }


class AuditAgent:
    """Independent Agent 4: Focuses on compliance and audit"""
    
    def __init__(self):
        self.name = "AUDITOR"
        self.config = config_manager.get_config(self.name)
        logger.debug(f"{self.name} agent initialized with config: provider={self.config.provider}, model={self.config.model_id}")
        
    def audit(self, applicant: Dict[str, Any], collected_data: Dict[str, Any], 
              risk_assessment: Dict[str, Any], final_decision: Dict[str, Any]) -> Dict[str, Any]:
        """Audit the entire decision process"""
        logger.info(f"{self.name} agent: Starting audit process")
        
        prompt = f"""{get_compliance_rules()}

As a CREDIT AUDIT & COMPLIANCE SPECIALIST, conduct a comprehensive compliance audit:

APPLICANT:
{json.dumps(applicant, indent=2)}

COLLECTED DATA:
{json.dumps(collected_data, indent=2)}

RISK ASSESSMENT:
{json.dumps(risk_assessment, indent=2)}

FINAL DECISION:
{json.dumps(final_decision, indent=2)}

AUDIT REQUIREMENTS:
1. Verify all documentation requirements were met per compliance framework
2. Check for fair lending compliance and disparate impact concerns
3. Assess decision justification against policy criteria
4. Verify regulatory notice requirements (if DENY or REFER)
5. Validate audit trail completeness
6. Confirm no prohibited factors influenced decision (protected characteristics)
7. Review for consistency with regulatory guidelines (ECOA, TILA, Reg Z, Dodd-Frank)
8. Identify strengths and gaps in documentation

Provide comprehensive audit report in JSON with: audit_compliance_score (1-100), fair_lending_check_result (PASS/FLAG/FAIL), documentation_completeness, regulatory_compliance (ECOA/TILA/Dodd-Frank/Reg-Z assessment), compliance_issues (list with severity), regulatory_flags (list), missing_documentation, recommendations, audit_trail_summary, decision_justification_strength (Strong/Adequate/Weak), adverse_action_notice_required."""

        return self._invoke_llm(prompt)
    
    def _invoke_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM using provider abstraction"""
        logger.debug(f"{self.name} agent: Invoking {self.config.provider}/{self.config.model_id}")
        response = LLMFactory.invoke(prompt, self.config)
        
        if "error" in response:
            logger.exception(f"{self.name} agent failed: {response['error']}")
            return response
        
        # If response has parsed_json, extract it
        if "parsed_json" in response:
            logger.info(f"{self.name} agent: Successfully parsed audit report")
            return response["parsed_json"]
        
        # Try to extract JSON from text response
        text = response.get("text", "")
        if text:
            # Remove markdown code blocks if present
            text_clean = re.sub(r'```json\s*', '', text)
            text_clean = re.sub(r'```\s*', '', text_clean)
            
            # Try to find JSON by matching braces (handles nested structures)
            for start_idx in range(len(text_clean)):
                if text_clean[start_idx] == '{':
                    brace_count = 0
                    for end_idx in range(start_idx, len(text_clean)):
                        if text_clean[end_idx] == '{':
                            brace_count += 1
                        elif text_clean[end_idx] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_candidate = text_clean[start_idx:end_idx + 1]
                                try:
                                    parsed = json.loads(json_candidate)
                                    if "audit_compliance_score" in parsed:
                                        logger.info(f"{self.name} agent: Extracted JSON with audit_compliance_score from text")
                                        return parsed
                                except json.JSONDecodeError:
                                    pass
                                break
        
        logger.warning(f"{self.name} agent: Could not extract JSON, using fallback")
        return {
            "audit_compliance_score": 0,
            "compliance_issues": [],
            "audit_trail_summary": response.get("text", "No response"),
            "format": "text_fallback"
        }


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
    model_id = "us.anthropic.claude-sonnet-4-6"
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
