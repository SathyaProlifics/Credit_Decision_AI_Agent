import os
import json
import boto3
from datetime import datetime
from typing import Any, Dict
from bedrock_agentcore._utils import endpoints
import logging

from strands import tool, Agent
from strands.models import BedrockModel

# Import the new multi-agent orchestrator
from CreditDecisionAgent_MultiAgent import run_credit_decision, OrchestratorAgent

region = boto3.session.Session().region_name or "us-east-1"
logger = logging.getLogger("credit_decision_agent")

# Import DB tools
from CreditDecisionStrandsDBTools import (
    get_application,
    insert_application,
    update_application_status,
    update_application_agent_output,
)


def make_agent() -> Agent:
    """Construct a Strands Agent with multi-agent orchestration capability"""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    agent = Agent(
        model=BedrockModel(model_id=model_id),
        system_prompt="""You are an autonomous multi-agent credit decisioning system orchestrator.

You coordinate 4 independent AI agents to process credit applications:
1. DataCollector Agent - Analyzes applicant data completeness and quality
2. RiskAssessor Agent - Evaluates credit risk using advanced AI analysis
3. DecisionMaker Agent - Makes final approval/denial/refer decisions with reasoning
4. Auditor Agent - Ensures compliance and maintains decision audit trails

Each agent has specialized expertise and operates independently, providing their analysis which flows to the next agent in the pipeline.""",
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
        print("Usage: python CreditDecisionAgent.py --application_id <ID>")
        print("\n=== MULTI-AGENT CREDIT DECISIONING SYSTEM ===")
        print("\nArchitecture: 4 Independent AI Agents (Strands Framework)")
        print("\nAgent Pipeline:")
        print("  1️⃣  DataCollector → Analyzes data completeness (Claude 3 Haiku)")
        print("  2️⃣  RiskAssessor → Evaluates credit risk (Claude 3 Sonnet)")
        print("  3️⃣  DecisionMaker → Makes decisions with reasoning (Claude 3 Sonnet)")
        print("  4️⃣  Auditor → Verifies compliance & audit trail (Claude 3 Sonnet)")
        print("\nEach agent uses AWS Bedrock for LLM inference.")
        print("Orchestrated by OrchestratorAgent for coordinated workflow.")

