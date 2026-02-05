import os
import json
import boto3
from datetime import datetime
from typing import Any, Dict
from bedrock_agentcore._utils import endpoints
from botocore.exceptions import ClientError
import logging

from strands import tool, Agent
from strands.models import BedrockModel

region = boto3.session.Session().region_name or "us-east-1"
NOVA_PRO_MODEL_ID = "us.amazon.nova-pro-v1:0"
if region.startswith("eu"):
    NOVA_PRO_MODEL_ID = "eu.amazon.nova-pro-v1:0"
elif region.startswith("ap"):
    NOVA_PRO_MODEL_ID = "apac.amazon.nova-pro-v1:0"

    logger = logging.getLogger("credit_decision_agent")

# Import DB tools (these are `@tool` wrappers but callable as functions)
from CreditDecisionStrandsDBTools import (
    get_application,
    insert_application,
    update_application_status,
    update_application_agent_output,
)

# Basic Bedrock invocation helper (synchronous for simplicity)
def _invoke_bedrock(prompt: str, model_id: str = None, max_tokens: int = 1000) -> str:
    
    data_plane_endpoint = endpoints.get_data_plane_endpoint(region)
    # Prefer the Bedrock runtime client (provides `invoke_model`). If unavailable,
    # fall back to agentcore client so the error can be surfaced clearly.
    try:
        if data_plane_endpoint:
            client = boto3.client("bedrock-runtime", region_name=region, endpoint_url=data_plane_endpoint)
        else:
            client = boto3.client("bedrock-runtime", region_name=region)
    except Exception:
        # Fallback: create an agentcore client (will likely not have invoke_model)
        client = boto3.client("bedrock-agentcore", region_name=region, endpoint_url=data_plane_endpoint)
    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        response_body = json.loads(response["body"].read())
        return response_body.get("content", [])[0].get("text", "")
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def collect_data_tool(applicant: Dict[str, Any]) -> str:
    """Collect and analyze applicant data. Returns JSON string."""
    # Build a Bedrock-native request similar to bedrock_credit_analysis.py
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"

    # Map applicant fields to the prompt-friendly keys
    name = applicant.get("applicant_name") or applicant.get("name") or "Unknown"
    age = applicant.get("age", "Unknown")
    income = applicant.get("income", 0)
    employment_status = applicant.get("employment_status", "Unknown")
    credit_score = applicant.get("credit_score", "Unknown")
    dti_ratio = applicant.get("dti_ratio", 0)
    existing_debts = applicant.get("existing_debts", 0)
    requested_credit = applicant.get("requested_credit", 0)

    def _to_float(val, percent_ok=False):
        try:
            if val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip()
            # handle percentages like '35%'
            if percent_ok and s.endswith('%'):
                return float(s.rstrip('%').replace(',',''))/100.0
            # remove commas
            s2 = s.replace(',','')
            return float(s2)
        except Exception:
            return 0.0

    # Coerce numeric fields safely
    income_f = _to_float(income)
    dti_ratio_f = _to_float(dti_ratio, percent_ok=True)
    existing_debts_f = _to_float(existing_debts)
    requested_credit_f = _to_float(requested_credit)

    prompt = f"""As a credit data collection specialist, analyze the following applicant information and provide a comprehensive credit profile in JSON:\n\nApplicant Data:\n- Name: {name}\n- Age: {age}\n- Annual Income: ${income_f:,.2f}\n- Employment Status: {employment_status}\n- Credit Score: {credit_score}\n- Debt-to-Income Ratio: {dti_ratio_f:.2%}\n- Existing Debts: ${existing_debts_f:,.2f}\n- Requested Credit: ${requested_credit_f:,.2f}\n\nPlease provide your analysis in JSON format with fields: data_completeness_score, data_quality_assessment, key_risk_indicators, positive_factors, missing_data_recommendations, overall_profile_summary, recommended_next_steps."""

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "temperature": 0.3,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]
    }

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.invoke_model(modelId=model_id, body=json.dumps(native_request))
        model_response = json.loads(response["body"].read())
        analysis_text = model_response.get("content", [])[0].get("text", "")

        # Try to parse text as JSON; return JSON string either way
        try:
            parsed = json.loads(analysis_text)
            return json.dumps(parsed)
        except Exception:
            return json.dumps({"analysis": analysis_text, "format": "text"})
    except Exception as e:
        return json.dumps({"error": f"Bedrock data collection failed: {str(e)}"})


@tool
def assess_risk_tool(applicant: Dict[str, Any], collected_data: Dict[str, Any]) -> str:
    """Assess credit risk using Bedrock runtime. Returns JSON string."""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

    # Helper to coerce numeric values
    def _to_float_local(val, percent_ok=False):
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

    # Coerce key numeric fields from applicant and collected_data
    income = _to_float_local(applicant.get('income', 0))
    credit_score = applicant.get('credit_score')
    dti = _to_float_local(applicant.get('dti_ratio', 0), percent_ok=True)

    prompt = f"""As a credit risk assessment expert, evaluate the following credit application and collected data and return a JSON object with:
- overall_risk_score (1-100)
- risk_category (Low, Medium, High, Very High)
- key_risk_factors
- mitigating_factors
- recommended_credit_limit
- suggested_interest_rate_range

Applicant:\n{json.dumps(applicant, indent=2)}\n\nCollected Data:\n{json.dumps(collected_data, indent=2)}\n\nPlease respond in JSON."""

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "temperature": 0.3,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]
    }

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.invoke_model(modelId=model_id, body=json.dumps(native_request))
        model_response = json.loads(response["body"].read())
        analysis_text = model_response.get("content", [])[0].get("text", "")
        try:
            parsed = json.loads(analysis_text)
            return json.dumps(parsed)
        except Exception:
            return json.dumps({"analysis": analysis_text, "format": "text"})
    except Exception as e:
        return json.dumps({"error": f"Bedrock risk assessment failed: {str(e)}"})


@tool
def make_decision_tool(applicant: Dict[str, Any], risk_assessment: Dict[str, Any]) -> str:
    """Make final credit decision. Returns JSON string."""
    logger = logging.getLogger("credit_decision_agent")
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    logger.info("make_decision_tool invoked for applicant=%s", applicant.get("applicant_name"))
    prompt = f"""
    You are a senior credit underwriter. Given the applicant and risk assessment, choose one of: APPROVE, DENY, REFER.
    For APPROVE include credit_limit, interest_rate, term_length, conditions.
    Include confidence (1-100) and a concise reasoning field. Return a single JSON object with keys:
    decision, credit_limit, interest_rate, term_length, conditions, confidence, reason.

    Applicant:
    {json.dumps(applicant, indent=2)}

    Risk Assessment:
    {json.dumps(risk_assessment, indent=2)}
    Please respond only with the JSON object.
    """

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "temperature": 0.2,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]
    }

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        logger.debug("make_decision_tool invoking model_id=%s", model_id)
        logger.debug("make_decision_tool native_request (prefix): %s", json.dumps(native_request)[:1000])
        response = client.invoke_model(modelId=model_id, body=json.dumps(native_request))
        # read and log a prefix of the body for diagnostics
        try:
            body_bytes = response["body"].read()
            body_text = body_bytes.decode("utf-8", errors="replace")
            logger.debug("make_decision_tool response body size=%d prefix=%s", len(body_bytes), body_text[:1000])
            model_response = json.loads(body_text)
        except Exception:
            logger.exception("make_decision_tool failed to read/parse response body")
            model_response = response

        analysis_text = ""
        try:
            content = model_response.get("content") if isinstance(model_response, dict) else None
            if isinstance(content, list) and len(content) > 0:
                analysis_text = content[0].get("text", "")
            else:
                analysis_text = model_response.get("text", "") if isinstance(model_response, dict) else str(model_response)
        except Exception:
            logger.exception("make_decision_tool error extracting analysis_text")
            analysis_text = str(model_response)

        logger.info("make_decision_tool analysis_text length=%d", len(analysis_text) if isinstance(analysis_text, str) else 0)
        logger.debug("make_decision_tool analysis_text prefix: %s", (analysis_text[:1000] + '...') if isinstance(analysis_text, str) and len(analysis_text) > 1000 else analysis_text)

        try:
            parsed = json.loads(analysis_text)
            logger.debug("make_decision_tool parsed keys: %s", list(parsed.keys()) if isinstance(parsed, dict) else type(parsed))
            return json.dumps(parsed)
        except Exception:
            logger.warning("make_decision_tool response not JSON, returning raw analysis")
            return json.dumps({"analysis": analysis_text, "format": "text"})
    except Exception as e:
        logger.exception("make_decision_tool invoke_model failed")
        return json.dumps({"error": f"Bedrock decision failed: {str(e)}"})


@tool
def audit_decision_tool(applicant: Dict[str, Any], collected_data: Dict[str, Any], risk_assessment: Dict[str, Any], final_decision: Dict[str, Any]) -> str:
    """Audit the decision flow and return a JSON audit report."""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    prompt = f"""
    As an audit specialist, review the following and return a JSON report with:
    - audit_compliance_score (1-100)
    - compliance_issues (list)
    - recommendations
    - audit_trail_summary

    Applicant:
    {json.dumps(applicant, indent=2)}
    Collected Data:
    {json.dumps(collected_data, indent=2)}
    Risk Assessment:
    {json.dumps(risk_assessment, indent=2)}
    Final Decision:
    {json.dumps(final_decision, indent=2)}
    Please respond only with the JSON object.
    """

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "temperature": 0.2,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]
    }

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.invoke_model(modelId=model_id, body=json.dumps(native_request))
        model_response = json.loads(response["body"].read())
        analysis_text = model_response.get("content", [])[0].get("text", "")
        try:
            parsed = json.loads(analysis_text)
            return json.dumps(parsed)
        except Exception:
            return json.dumps({"analysis": analysis_text, "format": "text"})
    except Exception as e:
        return json.dumps({"error": f"Bedrock audit failed: {str(e)}"})


@tool
def run_credit_decision(application_id: int) -> str:
    """Orchestrator tool: fetch application, run steps, persist outputs, update status."""
    try:
        # Fetch application (DB tool returns JSON string)
        raw = get_application(application_id)
        app_row = json.loads(raw)
        if app_row.get("error"):
            return json.dumps({"error": "application_not_found", "detail": app_row})

        # Normalize applicant dict expected by tools
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

        update_application_status(application_id, "PROCESSING")
        # progress messages collected during orchestration; persisted to DB for UI polling
        progress_messages = []
        def _persist_partial(result_partial: dict):
            try:
                result_partial_copy = dict(result_partial)
                result_partial_copy["_progress_messages"] = list(progress_messages)
                result_partial_copy["processing_status"] = result_partial_copy.get("processing_status", "processing")
                update_application_agent_output(application_id, result_partial_copy)
            except Exception:
                # avoid crashing orchestration for persistence issues
                pass

        # Step 1: Data collection
        progress_messages.append("Starting data collection")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant})
        collected_raw = collect_data_tool(applicant)
        try:
            collected = json.loads(collected_raw)
            progress_messages.append("Data collection completed")
        except Exception:
            collected = {"raw": collected_raw}
            progress_messages.append("Data collection returned non-JSON response")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant, "data_collection": collected})

        # Step 2: Risk assessment
        progress_messages.append("Starting risk assessment")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant, "data_collection": collected})
        risk_raw = assess_risk_tool(applicant, collected)
        try:
            risk = json.loads(risk_raw)
            progress_messages.append("Risk assessment completed")
        except Exception:
            risk = {"raw": risk_raw}
            progress_messages.append("Risk assessment returned non-JSON response")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant, "data_collection": collected, "risk_assessment": risk})

        # Step 3: Decision
        progress_messages.append("Starting decision making")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant, "data_collection": collected, "risk_assessment": risk})
        decision_raw = make_decision_tool(applicant, risk)
        try:
            decision = json.loads(decision_raw)
            progress_messages.append("Decision completed")
        except Exception:
            decision = {"raw": decision_raw}
            progress_messages.append("Decision returned non-JSON response")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant, "data_collection": collected, "risk_assessment": risk, "final_decision": decision})

        # Step 4: Audit
        progress_messages.append("Starting audit")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant, "data_collection": collected, "risk_assessment": risk, "final_decision": decision})
        audit_raw = audit_decision_tool(applicant, collected, risk, decision)
        try:
            audit = json.loads(audit_raw)
            progress_messages.append("Audit completed")
        except Exception:
            audit = {"raw": audit_raw}
            progress_messages.append("Audit returned non-JSON response")
        _persist_partial({"timestamp": datetime.now().isoformat(), "applicant": applicant, "data_collection": collected, "risk_assessment": risk, "final_decision": decision, "audit_report": audit})

        # Compile result
        result = {
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected,
            "risk_assessment": risk,
            "final_decision": decision,
            "audit_report": audit,
            "processing_status": "completed",
            "_progress_messages": list(progress_messages),
        }

        # Persist agent_output and final status
        try:
            update_application_agent_output(application_id, result)
        except Exception:
            # Persist failure shouldn't crash orchestration; continue to set status
            pass

        # Normalize decision string matching (accept lowercase/uppercase)
        decided = None
        if isinstance(decision, dict):
            decided = str(decision.get("decision", "")).upper()
        # Map to application status
        if decided == "APPROVE":
            status = "APPROVED"
        elif decided == "DENY":
            status = "DENIED"
        else:
            status = "REFER"

        update_application_status(
            application_id,
            status,
            reason=(decision.get("reason") if isinstance(decision, dict) else None),
            confidence=(decision.get("confidence") if isinstance(decision, dict) else None),
        )

        return json.dumps({"result": result})

    except Exception as e:
        update_application_status(application_id, "ERROR", reason=str(e))
        return json.dumps({"error": "processing_failed", "message": str(e)})


def make_agent() -> Agent:
    """Construct and return a Strands Agent with the credit decision tools registered."""
    region = boto3.session.Session().region_name or "us-east-1"
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    agent = Agent(
        model=BedrockModel(model_id=model_id),
        system_prompt="You are an autonomous credit decision assistant. Use the provided tools to process credit applications.",
        tools=[
            collect_data_tool,
            assess_risk_tool,
            make_decision_tool,
            audit_decision_tool,
            get_application,
            insert_application,
            update_application_status,
            update_application_agent_output,
            run_credit_decision,
        ],
    )
    return agent


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--application_id", type=int, help="Application ID to process")
    args = p.parse_args()

    if args.application_id:
        # run as a script (synchronous call to the orchestration tool)
        out = run_credit_decision(args.application_id)
        print(out)
    else:
        print("No application_id provided. Create an agent with `make_agent()` and call tools interactively.")
