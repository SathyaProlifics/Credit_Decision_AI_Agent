"""
Banking Rules and Regulatory Framework
Loads credit decision criteria, compliance requirements, and industry-specific guidelines
from external YAML configuration file for easy maintenance and updates.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# ==================== FILE LOADER ====================
def load_banking_rules() -> Dict[str, Any]:
    """Load banking rules from YAML configuration file"""
    rules_file = Path(__file__).parent / "banking_rules.yaml"
    
    if not rules_file.exists():
        raise FileNotFoundError(f"Banking rules file not found: {rules_file}")
    
    try:
        with open(rules_file, 'r') as f:
            rules = yaml.safe_load(f)
        
        if not rules:
            raise ValueError("Banking rules file is empty")
        
        return rules
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing banking rules YAML: {e}")
    except Exception as e:
        raise Exception(f"Error loading banking rules: {e}")

# Load rules once at module initialization
try:
    BANKING_RULES = load_banking_rules()
except Exception as e:
    print(f"ERROR: Failed to load banking rules: {e}")
    print("Using fallback rules...")
    BANKING_RULES = {}

# ==================== CONTEXT BUILDERS ====================
def get_system_context() -> str:
    """Build comprehensive system context for LLM agents from loaded rules"""
    rules = BANKING_RULES
    
    regulatory = rules.get('regulatory_framework', {})
    credit_matrix = rules.get('credit_decision_matrix', {})
    risk_framework = rules.get('risk_assessment', {})
    compliance = rules.get('compliance_framework', {})
    special = rules.get('special_circumstances', {})

# ==================== CREDIT DECISION MATRIX ====================
CREDIT_DECISION_MATRIX = """
AUTOMATED DECISION MATRIX:

I. CREDIT SCORE TIERS:
   - 750+: Excellent (Primary approval indicator)
   - 700-749: Good (Requires DTI < 35%)
   - 650-699: Fair (Requires DTI < 30%, manual review recommended)
   - 600-649: Poor (High risk, requires manual review)
   - Below 600: Very High Risk (Recommend denial unless compensating factors)

II. DEBT-TO-INCOME (DTI) RATIO THRESHOLDS:
   - Below 30%: Excellent (Strong approval indicator)
   - 30-35%: Acceptable (Standard qualification)
   - 35-40%: Marginal (Requires compensating factors)
   - 40-45%: High Risk (Manual review required)
   - Above 45%: Typically unacceptable (Recommend denial)

III. INCOME QUALIFICATION:
   - Minimum Annual Income: $25,000 (Poverty line threshold)
   - Income Verification: Required (Pay stubs, tax returns, employment letter)
   - Employment Status Scoring:
     * Full-time (2+ years): Best (100 points)
     * Full-time (<2 years): Good (70 points)
     * Part-time (2+ years): Fair (60 points)
     * Self-employed (3+ years): Fair (65 points)
     * Part-time (<2 years): High Risk (40 points)
     * Unemployed: Typically declined (10 points)
     * Retired (with pension/retirement income): Good (75 points)

IV. LOAN AMOUNT CRITERIA:
   - Maximum Loan-to-Income Ratio: 3x annual income
   - Maximum Loan/Credit Score Ratio: Loan amount should not exceed 50x (loan/score)
   - Examples:
     * $75,000 income -> Max loan: $225,000
     * 720 credit score -> Max loan: $36,000
     * Use the more restrictive limit

V. EXISTING DEBT EVALUATION:
   - Maximum Existing Debt: 2x annual income
   - New Total Debt (existing + requested) should not exceed 3x annual income
   - Debt aging: Older debts (5+ years) weighted less negativity

VI. APPROVAL DECISION TRIGGERS:
   APPROVE when:
   - Credit Score ≥ 700 AND DTI < 30% AND Income ≥ $30,000 AND Employment stable
   - OR: Credit Score ≥ 720 AND DTI < 35% AND compensation factors present
   
   REFER (Manual Review) when:
   - Credit Score 650-699 OR DTI 30-40% OR Recent employment changes
   - OR: Score 700+ but DTI 35-40% (borderline cases)
   - OR: Score 600-649 with strong compensating factors
   
   DENY when:
   - Credit Score < 600 (unless exceptional circumstances)
   - OR: DTI > 45%
   - OR: Income < $25,000 (inadequate earning)
   - OR: Recent delinquencies (< 6 months)
   - OR: Active bankruptcy
   - OR: Multiple fraud indicators
"""

# ==================== RISK ASSESSMENT FRAMEWORK ====================
RISK_ASSESSMENT_FRAMEWORK = """
CREDIT RISK SCORING SYSTEM:

I. RISK SCORE CALCULATION (1-100):
   Components:
   - Payment History Impact (40%): On-time payments = 35-40, recent late payments = 10-25
   - Credit Utilization (20%): Low usage (10-30%) = 18-20, high usage (>80%) = 5-10
   - Credit Age (15%): Long history (10+ years) = 13-15, new credit (<2 years) = 5-8
   - Inquiries/New Accounts (15%): Few inquiries = 13-15, multiple recent = 5-10
   - Income Stability (10%): Stable employment = 8-10, employment changes = 3-6

II. RISK CATEGORIES:
   - Low Risk (Score 75-100): Approval probability 95%+
   - Medium Risk (Score 50-74): Approval probability 60-80%, may require conditions
   - High Risk (Score 25-49): Approval probability 20-50%, strong manual review required
   - Very High Risk (Score <25): Approval probability <10%, typically decline

III. KEY RISK FACTORS TO EVALUATE:
   Red Flags (Increase Risk):
   - Recent late payments (30/60/90 days past due)
   - Bankruptcy (recent within 7 years)
   - Collections or charge-offs
   - Multiple delinquencies
   - High credit utilization (>80%)
   - Recent inquiries (3+ in 6 months)
   - Short employment tenure (<6 months)
   - Very high DTI combined with low savings

   Green Flags (Decrease Risk):
   - Consistent on-time payment history
   - Long credit history (10+ years)
   - Low credit utilization
   - Stable long-term employment
   - Savings/emergency fund presence
   - Recent paycheck increase
   - Multiple credit accounts (shows credit diversity)

IV. CREDIT LIMIT RECOMMENDATIONS:
   Based on Risk Score:
   - Low Risk (75+): Up to 3x annual income
   - Medium Risk (50-74): Up to 2x annual income
   - High Risk (25-49): Up to 1x annual income
   - Very High Risk (<25): Up to 0.5x annual income

V. INTEREST RATE BANDS:
   Based on Risk Score:
   - Low Risk (75+): 6-8% APR
   - Medium Risk (50-74): 10-14% APR
   - High Risk (25-49): 16-22% APR
   - Very High Risk (<25): Recommend decline or 24%+ APR with manual approval
"""

# ==================== COMPLIANCE REQUIREMENTS ====================
COMPLIANCE_REQUIREMENTS = """
DECISION DOCUMENTATION & AUDIT REQUIREMENTS:

I. REQUIRED DOCUMENTATION FOR EVERY DECISION:
   - Applicant identification and contact information
   - Income verification (recent pay stubs or tax returns)
   - Employment verification
   - Credit report pull timestamp
   - Credit score used in decision
   - All quantitative metrics (DTI, debt ratios)
   - Decision reason codes

II. ADVERSE ACTION NOTIFICATION:
   If application is DENIED or referred REFER (pending):
   - Notify applicant within 30 days
   - Include: Specific reasons for decision, credit score range, applicant rights
   - Reference to Fair Credit Reporting Act and right to dispute

III. FAIR LENDING COMPLIANCE CHECKS:
   - Verify no disparate impact across protected classes
   - Ensure consistent application of lending criteria
   - Document compensating factors when applicable
   - Flag unusual patterns for review

IV. AUDIT TRAIL REQUIREMENTS:
   Every decision must include:
   - Timestamp of decision
   - Agent/system decision component versions
   - Input data snapshot (sanitized)
   - Decision rationale with specific factors cited
   - Manual reviewer notes (if applicable)
   - Policy version used for decision

V. DATA RETENTION:
   - Keep application records for minimum 3 years
   - Credit reports and verifications: 3 years
   - Adverse action notices: 3 years
   - All decision logs and audit trails: 7 years
"""

# ==================== COMPENSATING FACTORS ====================
COMPENSATING_FACTORS = """
COMPENSATING FACTORS (Can offset borderline credit metrics):

Acceptable Compensating Factors:
1. Significant Savings/Emergency Fund (>3 months living expenses)
2. Recent Income Increase (20%+ in last 12 months, documented)
3. Job Promotion or Degree Completion (recent, verifiable)
4. Long Employment Tenure (10+ years with same employer)
5. Additional Collateral or Co-signer (strong credit profile)
6. Low Recent Delinquencies that were quickly resolved
7. High Credit Limit (proves historical credit worthiness)
8. Explanation letter for negative factors (if reasonable)

Strength Assessment:
- 1-2 strong factors: Can offset 15-25 point credit decline
- 3+ strong factors: Can offset 25-50 point credit decline
- Very strong equity/collateral: Can offset more significant issues
"""

# ==================== SPECIAL CIRCUMSTANCES ====================
SPECIAL_CIRCUMSTANCES = """
SPECIAL SITUATIONS REQUIRING CAREFUL EVALUATION:

1. RECENT BANKRUPTCY (within 7 years):
   - Requires manual review
   - Consider: Reason for bankruptcy, time since discharge, recent rebuilding
   - May approve if strong recovery indicators present
   
2. RECENT DELINQUENCIES (within 12 months):
   - Recent (0-6 months): Strong negative signal, consider denial
   - 6-12 months: Evaluate reason and recency of resolution
   
3. THIN CREDIT FILE (fewer than 3 accounts):
   - Limited credit history = higher risk assessment
   - Consider alternative data sources for approval
   
4. FIRST-TIME HOMEBUYER or NEW CREDIT:
   - Less credit history expected
   - May have higher approval threshold
   
5. SELF-EMPLOYED APPLICANTS:
   - Require 3-year tax returns
   - Income averaging may be used
   - Greater volatility expected
   
6. CO-SIGNER RELATIONSHIPS:
   - Co-signer credit also evaluated
   - Both parties liable for debt
   - Co-signer income can support qualification
"""

# ==================== SYSTEM PROMPT FOR LLM AGENTS ====================
SYSTEM_CONTEXT_FOR_AGENTS = f"""
You are a professional credit decision system operating within a regulated financial institution.
All decisions MUST comply with federal lending laws and banking best practices.

{REGULATORY_CONTEXT}

{CREDIT_DECISION_MATRIX}

{RISK_ASSESSMENT_FRAMEWORK}

{COMPLIANCE_REQUIREMENTS}

{COMPENSATING_FACTORS}

{SPECIAL_CIRCUMSTANCES}

CRITICAL REQUIREMENTS:
1. ALL credit decisions must follow the decision matrix
2. Document ALL reasoning with specific policy references
3. Flag any fair lending concerns or unusual patterns
4. Include required compliance elements in every response
5. Use consistent risk scoring methodology
6. Provide clear, documented rationales for regulatory compliance

RESPONSE STRUCTURE:
Always include in your JSON responses:
- Primary decision factors (quantitative scores and thresholds met/not met)
- Risk indicators (both positive and negative)
- Compliance verification (fair lending check, required docs present)
- Documentation for audit trail
- If any factor is borderline, explain reasoning and decision logic
"""

# ==================== HELPER FUNCTIONS ====================
def get_system_context():
    """Return the complete banking rules context for LLM agents"""
    return SYSTEM_CONTEXT_FOR_AGENTS

def get_credit_decision_rules():
    """Return credit decision matrix"""
    return CREDIT_DECISION_MATRIX

def get_risk_framework():
    """Return risk assessment framework"""
    return RISK_ASSESSMENT_FRAMEWORK

def get_compliance_rules():
    """Return compliance requirements"""
    return COMPLIANCE_REQUIREMENTS

def calculate_dti_compliance(dti: float) -> dict:
    """Evaluate DTI against banking standards"""
    if dti < 0.30:
        return {"tier": "excellent", "status": "PASS", "risk": "low"}
    elif dti < 0.35:
        return {"tier": "acceptable", "status": "PASS", "risk": "low-medium"}
    elif dti < 0.40:
        return {"tier": "marginal", "status": "CAUTION", "risk": "medium"}
    elif dti < 0.45:
        return {"tier": "high", "status": "REVIEW_REQUIRED", "risk": "high"}
    else:
        return {"tier": "unacceptable", "status": "FAIL", "risk": "very-high"}

def calculate_credit_score_tier(score: int) -> dict:
    """Categorize credit score into banking tiers"""
    if score >= 750:
        return {"tier": "excellent", "category": "Prime", "approval_probability": 0.95}
    elif score >= 700:
        return {"tier": "good", "category": "Near-Prime", "approval_probability": 0.80}
    elif score >= 650:
        return {"tier": "fair", "category": "Non-Prime", "approval_probability": 0.50}
    elif score >= 600:
        return {"tier": "poor", "category": "Subprime", "approval_probability": 0.25}
    else:
        return {"tier": "very_poor", "category": "High-Risk", "approval_probability": 0.05}

def evaluate_employment_stability(employment_status: str, tenure_months: int = 12) -> dict:
    """Evaluate employment for lending purposes"""
    if employment_status == "Unemployed":
        return {"score": 10, "status": "unacceptable", "lending_weight": 0}
    elif employment_status == "Part-time" and tenure_months < 24:
        return {"score": 40, "status": "high_risk", "lending_weight": 0.4}
    elif employment_status == "Part-time":
        return {"score": 60, "status": "acceptable", "lending_weight": 0.6}
    elif employment_status == "Self-employed" and tenure_months < 36:
        return {"score": 50, "status": "caution", "lending_weight": 0.5}
    elif employment_status == "Self-employed":
        return {"score": 65, "status": "good", "lending_weight": 0.65}
    elif employment_status in ["Full-time", "Retired"]:
        return {"score": 80, "status": "excellent", "lending_weight": 0.80}
    else:
        return {"score": 70, "status": "good", "lending_weight": 0.70}

def validate_income_minimum(annual_income: float) -> dict:
    """Validate income meets minimum threshold"""
    minimum_income = 25000
    if annual_income >= minimum_income:
        return {"valid": True, "message": f"Income sufficient (>${minimum_income:,})"}
    else:
        return {"valid": False, "message": f"Income below minimum threshold of ${minimum_income:,}"}

def calculate_max_loan_amount(annual_income: float, credit_score: int) -> float:
    """Calculate maximum approvable loan amount based on banking standards"""
    # Rules: Max 3x income OR 50x credit score, whichever is MORE restrictive
    max_by_income = annual_income * 3
    max_by_score = credit_score * 50
    return min(max_by_income, max_by_score)
