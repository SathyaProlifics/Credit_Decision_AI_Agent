"""
Banking Rules Loader
Loads and manages banking rules from external YAML configuration file.
Provides context builders and utility functions for AI agents.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("banking_rules_loader")

# ==================== FILE LOADER ====================
def load_banking_rules() -> Dict[str, Any]:
    """Load banking rules from YAML configuration file"""
    rules_file = Path(__file__).parent / "banking_rules.yaml"
    
    if not rules_file.exists():
        logger.error(f"Banking rules file not found: {rules_file}")
        raise FileNotFoundError(f"Banking rules file not found: {rules_file}")
    
    try:
        with open(rules_file, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        
        if not rules:
            raise ValueError("Banking rules file is empty")
        
        logger.info(f"Successfully loaded banking rules from {rules_file}")
        return rules
    except yaml.YAMLError as e:
        logger.error(f"Error parsing banking rules YAML: {e}")
        raise ValueError(f"Error parsing banking rules YAML: {e}")
    except Exception as e:
        logger.error(f"Error loading banking rules: {e}")
        raise Exception(f"Error loading banking rules: {e}")

# Load rules once at module initialization
try:
    BANKING_RULES = load_banking_rules()
    RULES_LOADED = True
except Exception as e:
    logger.warning(f"Failed to load banking rules: {e}, using empty fallback")
    BANKING_RULES = {}
    RULES_LOADED = False

# ==================== CONTEXT BUILDERS ====================
def get_system_context() -> str:
    """Build comprehensive system context for LLM agents from loaded rules"""
    if not RULES_LOADED:
        return "ERROR: Banking rules not loaded - check banking_rules.yaml file"
    
    rules = BANKING_RULES
    
    context = """BANKING RULES AND REGULATORY COMPLIANCE FRAMEWORK

You are operating within a highly regulated financial institution.
All decisions MUST comply with federal lending laws and banking best practices.

REGULATORY REQUIREMENTS:
"""
    
    regulatory = rules.get('regulatory_framework', {})
    if regulatory:
        fair_lending = regulatory.get('fair_lending', {})
        if fair_lending:
            context += f"\n{fair_lending.get('description', '')}\n"
            for act in fair_lending.get('acts', []):
                context += f"  - {act['name']}: {act['requirements']}\n"
        
        tila = regulatory.get('truth_in_lending', {})
        if tila:
            context += f"\n{tila.get('description', '')}\n"
            for act in tila.get('acts', []):
                context += f"  - {act['name']}: {act['requirements']}\n"
    
    # Add credit decision matrix
    context += "\n\nCREDIT DECISION MATRIX:\n"
    credit_matrix = rules.get('credit_decision_matrix', {})
    
    context += "\nCREDIT SCORE TIERS:\n"
    for tier_name, tier_data in credit_matrix.get('credit_score_tiers', {}).items():
        context += f"  {tier_name.upper()}: {tier_data.get('range')} ({tier_data.get('category')})\n"
    
    context += "\nDEBT-TO-INCOME THRESHOLDS:\n"
    for tier_name, tier_data in credit_matrix.get('dti_thresholds', {}).items():
        context += f"  {tier_name.upper()}: {tier_data.get('range')} - {tier_data.get('status')}\n"
    
    # Add approval triggers
    context += "\n\nAPPROVAL DECISION RULES:\n"
    decisions = rules.get('approval_decisions', {})
    if decisions:
        context += "APPROVE when:\n"
        for trigger in decisions.get('approve_triggers', []):
            context += f"  - {trigger}\n"
        
        context += "\nREFER (Manual Review) when:\n"
        for trigger in decisions.get('refer_triggers', []):
            context += f"  - {trigger}\n"
        
        context += "\nDENY when:\n"
        for trigger in decisions.get('deny_triggers', []):
            context += f"  - {trigger}\n"
    
    # Add risk assessment framework
    context += "\n\nRISK ASSESSMENT FRAMEWORK:\n"
    risk_framework = rules.get('risk_assessment', {})
    if risk_framework:
        context += "Risk Score Categories:\n"
        for cat_name, cat_data in risk_framework.get('risk_categories', {}).items():
            context += f"  {cat_name.upper()}: Score {cat_data.get('score_range')} - Approval {cat_data.get('approval_probability', 0)*100:.0f}%\n"
    
    # Add compliance requirements
    context += "\n\nCOMPLIANCE REQUIREMENTS:\n"
    compliance = rules.get('compliance_framework', {})
    if compliance:
        context += "Required Documentation:\n"
        for doc in compliance.get('required_documentation', {}).get('every_decision', []):
            context += f"  - {doc}\n"
    
    context += "\n\nCRITICAL REQUIREMENTS:\n"
    context += """1. ALL credit decisions must follow the decision matrix
2. Document ALL reasoning with specific policy references
3. Flag any fair lending concerns or unusual patterns
4. Include required compliance elements in every response
5. Use consistent risk scoring methodology
6. Provide clear, documented rationales for regulatory compliance
7. Never consider protected characteristics in decisions
"""
    
    return context

def get_credit_decision_rules() -> str:
    """Get credit decision matrix rules"""
    if not RULES_LOADED:
        return "ERROR: Banking rules not loaded"
    
    rules = BANKING_RULES
    credit_matrix = rules.get('credit_decision_matrix', {})
    
    output = "CREDIT DECISION MATRIX:\n\n"
    
    output += "I. CREDIT SCORE TIERS:\n"
    for tier_name, tier_data in credit_matrix.get('credit_score_tiers', {}).items():
        output += f"  {tier_name.upper()}: {tier_data}\n"
    
    output += "\nII. DEBT-TO-INCOME RATIOS:\n"
    for tier_name, tier_data in credit_matrix.get('dti_thresholds', {}).items():
        output += f"  {tier_name.upper()}: {tier_data}\n"
    
    output += "\nIII. INCOME REQUIREMENTS:\n"
    output += json.dumps(credit_matrix.get('income_requirements', {}), indent=2)
    
    output += "\n\nAPPROVAL DECISION TRIGGERS:\n"
    decisions = rules.get('approval_decisions', {})
    output += json.dumps(decisions, indent=2)
    
    return output

def get_risk_framework() -> str:
    """Get risk assessment framework"""
    if not RULES_LOADED:
        return "ERROR: Banking rules not loaded"
    
    rules = BANKING_RULES
    risk_framework = rules.get('risk_assessment', {})
    
    output = "RISK ASSESSMENT FRAMEWORK:\n\n"
    output += "Risk Score Components:\n"
    output += json.dumps(risk_framework.get('risk_score_components', {}), indent=2)
    
    output += "\n\nRisk Categories:\n"
    output += json.dumps(risk_framework.get('risk_categories', {}), indent=2)
    
    output += "\n\nRed Flags:\n"
    for flag in risk_framework.get('red_flags', []):
        output += f"  - {flag}\n"
    
    output += "\nGreen Flags:\n"
    for flag in risk_framework.get('green_flags', []):
        output += f"  - {flag}\n"
    
    return output

def get_compliance_rules() -> str:
    """Get compliance requirements"""
    if not RULES_LOADED:
        return "ERROR: Banking rules not loaded"
    
    rules = BANKING_RULES
    compliance = rules.get('compliance_framework', {})
    
    output = "COMPLIANCE REQUIREMENTS:\n\n"
    output += json.dumps(compliance, indent=2)
    
    return output

# ==================== HELPER FUNCTIONS ====================
def calculate_dti_compliance(dti: float) -> dict:
    """Evaluate DTI against banking standards"""
    if not RULES_LOADED:
        return {"error": "Banking rules not loaded"}
    
    rules = BANKING_RULES
    dti_thresholds = rules.get('credit_decision_matrix', {}).get('dti_thresholds', {})
    
    for tier_name, tier_data in dti_thresholds.items():
        dti_range = tier_data.get('range', [])
        if len(dti_range) == 2 and dti_range[0] <= dti < dti_range[1]:
            return {
                "tier": tier_name,
                "status": tier_data.get('status', 'UNKNOWN'),
                "risk": tier_name,
                "range": dti_range
            }
    
    return {"tier": "unacceptable", "status": "OUT_OF_RANGE", "risk": "very-high"}

def calculate_credit_score_tier(score: int) -> dict:
    """Categorize credit score into banking tiers"""
    if not RULES_LOADED:
        return {"error": "Banking rules not loaded"}
    
    rules = BANKING_RULES
    score_tiers = rules.get('credit_decision_matrix', {}).get('credit_score_tiers', {})
    
    for tier_name, tier_data in score_tiers.items():
        score_range = tier_data.get('range', [])
        if len(score_range) == 2 and score_range[0] <= score <= score_range[1]:
            return {
                "tier": tier_name,
                "category": tier_data.get('category', 'UNKNOWN'),
                "approval_probability": tier_data.get('approval_probability', 0),
                "range": score_range
            }
    
    return {"tier": "very_poor", "category": "High-Risk", "approval_probability": 0.05}

def evaluate_employment_stability(employment_status: str, tenure_months: int = 12) -> dict:
    """Evaluate employment for lending purposes"""
    if not RULES_LOADED:
        return {"error": "Banking rules not loaded"}
    
    rules = BANKING_RULES
    employment_scoring = rules.get('credit_decision_matrix', {}).get('income_requirements', {}).get('employment_scoring', {})
    
    # Map employment status to key in YAML
    status_map = {
        "Full-time": "full_time_2plus_years" if tenure_months >= 24 else "full_time_less_2years",
        "Part-time": "part_time_2plus_years" if tenure_months >= 24 else "part_time_less_2years",
        "Self-employed": "self_employed_3plus_years" if tenure_months >= 36 else "self_employed_less_3years",
        "Retired": "retired_with_income",
        "Unemployed": "unemployed"
    }
    
    key = status_map.get(employment_status, "unemployed")
    if key in employment_scoring:
        data = employment_scoring[key]
        return {
            "score": data.get('score', 0),
            "status": data.get('status', 'UNKNOWN'),
            "employment_weight": data.get('employment_weight', 0)
        }
    
    return {"score": 10, "status": "unacceptable", "employment_weight": 0}

def validate_income_minimum(annual_income: float) -> dict:
    """Validate income meets minimum threshold"""
    if not RULES_LOADED:
        return {"error": "Banking rules not loaded"}
    
    rules = BANKING_RULES
    minimum_income = rules.get('credit_decision_matrix', {}).get('income_requirements', {}).get('minimum_annual', 25000)
    
    if annual_income >= minimum_income:
        return {"valid": True, "message": f"Income sufficient (>${minimum_income:,})"}
    else:
        return {"valid": False, "message": f"Income below minimum threshold of ${minimum_income:,}"}

def calculate_max_loan_amount(annual_income: float, credit_score: int) -> float:
    """Calculate maximum approvable loan amount based on banking standards"""
    if not RULES_LOADED:
        return 0.0
    
    rules = BANKING_RULES
    criteria = rules.get('credit_decision_matrix', {}).get('loan_amount_criteria', {})
    
    max_ratio = criteria.get('max_loan_to_income_ratio', 3.0)
    max_score_ratio = criteria.get('max_loan_to_credit_score_ratio', 50)
    
    max_by_income = annual_income * max_ratio
    max_by_score = credit_score * max_score_ratio
    
    return min(max_by_income, max_by_score)

def get_compensating_factors() -> Dict[str, Any]:
    """Get compensating factors that can offset borderline metrics"""
    if not RULES_LOADED:
        return {"error": "Banking rules not loaded"}
    
    rules = BANKING_RULES
    return rules.get('compensating_factors', {})

def get_special_circumstances() -> Dict[str, Any]:
    """Get special circumstances handling guidelines"""
    if not RULES_LOADED:
        return {"error": "Banking rules not loaded"}
    
    rules = BANKING_RULES
    return rules.get('special_circumstances', {})

def check_rules_loaded() -> bool:
    """Check if banking rules are loaded"""
    return RULES_LOADED

def reload_rules() -> bool:
    """Reload banking rules from file"""
    global BANKING_RULES, RULES_LOADED
    try:
        BANKING_RULES = load_banking_rules()
        RULES_LOADED = True
        logger.info("Banking rules reloaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to reload banking rules: {e}")
        RULES_LOADED = False
        return False
