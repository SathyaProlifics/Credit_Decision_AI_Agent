# Credit Decision Agent - Technical Flow Documentation

**Date**: February 8, 2026  
**Project**: AI Agent Credit Decision System  
**Framework**: Strands + AWS Bedrock + Anthropic Claude  
**Status**: Production Ready  
**Latest Updates**: UI Collapsible Sidebar, Quick Stats Dashboard, Real-time Progress Display

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Agent Framework & Components](#agent-framework--components)
4. [The 4-Step AI Decision Pipeline](#the-4-step-ai-decision-pipeline)
5. [Technical Implementation](#technical-implementation)
6. [Database Integration](#database-integration)
7. [UI Flow & User Interaction](#ui-flow--user-interaction)
8. [Models Used & Cost Analysis](#models-used--cost-analysis)
9. [Code References](#code-references)
10. [Deployment Architecture](#deployment-architecture)

---

## System Overview

Your application implements a **multi-agent AI credit decision system** that autonomously processes credit applications through 4 sequential AI-powered stages. The system uses Amazon Bedrock (AWS managed LLM service) with Anthropic Claude models orchestrated through the Strands framework.

### Key Features

✅ **Autonomous AI Decision Making**: Claude makes binding APPROVE/DENY/REFER decisions  
✅ **Multi-Stage Pipeline**: 4 sequential AI analysis steps with embedding  
✅ **Persistent Audit Trail**: All decisions logged to MySQL database  
✅ **Real-time Progress Tracking**: UI polls database for live updates  
✅ **Production-Grade**: Error handling, logging, background processing  
✅ **Compliant**: Audit tool reviews entire flow for consistency  

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      STREAMLIT WEB UI                           │
│              (credit_decision_ui.py)                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Sidebar Form:                                           │  │
│  │  - Full Name, Age, Employment Status                     │  │
│  │  - Annual Income, Credit Score, DTI Ratio               │  │
│  │  - Existing Debts, Requested Credit Amount              │  │
│  │  [🚀 Process Application Button]                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ Form Submission
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MySQL Database                               │
│            (sathya-database.cilmgugy4iud...)                    │
│                                                                 │
│  INSERT applicant record with status = PENDING               │
│  Returns: application_id (primary key)                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ Returns application_id
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│              BACKGROUND THREAD (run_credit_decision)             │
│                                                                 │
│  1️⃣ FETCH APPLICATION from DB                                 │
│     ├─ applicant_name, age, income, credit_score              │
│     ├─ dti_ratio, existing_debts, requested_credit            │
│     └─ status: PROCESSING                                      │
│                                                                 │
│  2️⃣ CALL AI TOOL #1: collect_data_tool                        │
│     ├─ Model: Claude-3-Haiku (cost-optimized)                 │
│     ├─ Input: Applicant demographics                           │
│     └─ Output: {data_completeness_score, risk_indicators}     │
│     └─ PERSIST: update agent_output with Step 1 result        │
│                                                                 │
│  3️⃣ CALL AI TOOL #2: assess_risk_tool                         │
│     ├─ Model: Claude-3-Sonnet (stronger model)                │
│     ├─ Input: Applicant + Step 1 output (CHAINED)            │
│     └─ Output: {risk_score (1-100), recommendations}          │
│     └─ PERSIST: update agent_output with Step 2 result        │
│                                                                 │
│  4️⃣ CALL AI TOOL #3: make_decision_tool                       │
│     ├─ Model: Claude-3-Sonnet                                 │
│     ├─ Input: Applicant + Step 2 output (CHAINED)            │
│     ├─ Decision: APPROVE / DENY / REFER                       │
│     └─ Output: {decision, credit_limit, interest_rate, ...}   │
│     └─ PERSIST: update agent_output with Step 3 result        │
│                                                                 │
│  5️⃣ CALL AI TOOL #4: audit_decision_tool                      │
│     ├─ Model: Claude-3-Sonnet                                 │
│     ├─ Input: ALL previous outputs (full review)              │
│     └─ Output: {audit_score, compliance_issues, ...}          │
│     └─ PERSIST: Complete agent_output + FINAL STATUS          │
│                                                                 │
│  6️⃣ UPDATE DATABASE                                            │
│     ├─ status: APPROVED / DENIED / REFER                      │
│     ├─ agent_output: Complete JSON from all steps            │
│     └─ confidence: Final decision confidence (1-100)          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ Database Updated
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    STREAMLIT UI POLLING                          │
│                                                                 │
│  - Polls every 2 seconds: get_application(app_id)             │
│  - When agent_output is populated, display results            │
│  - Shows 6 tabs:                                               │
│    1. Data Collection (Step 1 output)                          │
│    2. Risk Assessment (Step 2 output)                          │
│    3. Final Decision (Step 3 output)                           │
│    4. Audit Report (Step 4 output)                             │
│    5. Progress (live update messages)                          │
│    6. Full Report (complete JSON + timestamps)                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Agent Framework & Components

### Framework: Strands + AWS Bedrock

The system now implements a true multi-agent architecture. The core orchestration entrypoint lives in `CreditDecisionAgent.py`, but the agent implementations and orchestrator are contained in the new module `CreditDecisionAgent_MultiAgent.py`.

```python
# CreditDecisionAgent.py - Lightweight wrapper
from strands import Agent
from strands.models import BedrockModel
from CreditDecisionAgent_MultiAgent import run_credit_decision, OrchestratorAgent

def make_agent() -> Agent:
    """Return a Strands Agent that exposes the orchestrator tool only.

    The heavy lifting (DataCollector, RiskAssessor, DecisionMaker, Auditor,
    and the OrchestratorAgent) is implemented in
    `CreditDecisionAgent_MultiAgent.py` and invoked via `run_credit_decision`.
    """
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    agent = Agent(
        model=BedrockModel(model_id=model_id),
        system_prompt=(
            "Multi-agent orchestrator: coordinate DataCollector, RiskAssessor,"
            " DecisionMaker, and Auditor to process credit applications."),
        tools=[run_credit_decision],
    )
    return agent
```

### Independent Agents (new)

All tool implementations were moved into `CreditDecisionAgent_MultiAgent.py`. Key components:
- `DataCollectorAgent` — Claude-3-Haiku: analyzes completeness & data quality; returns structured JSON.
- `RiskAssessorAgent` — Claude-3-Sonnet: computes `overall_risk_score`, `risk_category`, and recommendations.
- `DecisionMakerAgent` — Claude-3-Sonnet: produces the final `decision` (APPROVE/DENY/REFER) with terms, confidence, and reasoning.
- `AuditAgent` — Claude-3-Sonnet: reviews the full flow and returns `audit_report` with compliance issues and recommendations.
- `OrchestratorAgent` — Coordinates the pipeline, persists step results to the DB, and exposes `run_credit_decision(app_id)` as a `@tool` for Strands.

Each agent class has an internal `_invoke_bedrock()` helper and returns JSON-serializable dicts. The `OrchestratorAgent` sequences the agents and updates the `agent_output` field in the database after each step for real-time UI polling.

### What is Strands?

**Strands** is Amazon's agent orchestration library for tool-calling LLMs:
- Watches for function calls in LLM responses
- Automatically executes matching `@tool` decorated functions
- Passes results back to LLM for next step
- Handles error recovery and retry logic
- Built specifically for AWS Bedrock

### What is BedrockModel?

**BedrockModel** wraps AWS Bedrock's inference API:
- Abstracts Claude model API calls
- Handles authentication via AWS credentials
- Supports multi-region routing
- Provides consistent interface across models (Claude 3 variants)

---

## The 4-Step AI Decision Pipeline

### **Step 1️⃣: Data Collection Tool**

**File**: [CreditDecisionAgent.py](CreditDecisionAgent.py#L52-L120)

```python
@tool
def collect_data_tool(applicant: Dict[str, Any]) -> str:
    """Collect and analyze applicant data. Returns JSON string."""
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"  # Cheaper model
    
    prompt = f"""As a credit data collection specialist, analyze the 
    following applicant information and provide a comprehensive credit 
    profile in JSON:
    
    Applicant Data:
    - Name: {name}
    - Age: {age}
    - Annual Income: ${income:,.2f}
    - Employment Status: {employment_status}
    - Credit Score: {credit_score}
    - Debt-to-Income Ratio: {dti_ratio:.2%}
    - Existing Debts: ${existing_debts:,.2f}
    - Requested Credit: ${requested_credit:,.2f}
    
    Please provide your analysis in JSON format with fields:
    - data_completeness_score
    - data_quality_assessment
    - key_risk_indicators
    - positive_factors
    - missing_data_recommendations
    - overall_profile_summary
    - recommended_next_steps
    """
    
    # Call Bedrock via native API
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.invoke_model(modelId=model_id, body=json.dumps(native_request))
    analysis_text = response["body"].read().decode("utf-8")
    
    # Parse and return JSON
    parsed = json.loads(analysis_text)
    return json.dumps(parsed)
```

**Input**: Applicant demographics (8 fields)  
**Model Used**: Claude-3-Haiku ($0.25/1M tokens - cheapest)  
**Output JSON**:
```json
{
  "data_completeness_score": 95,
  "data_quality_assessment": "High quality application",
  "key_risk_indicators": ["DTI ratio on higher side", "..."],
  "positive_factors": ["Good credit score", "Stable employment"],
  "missing_data_recommendations": [],
  "overall_profile_summary": "Well-qualified applicant with minor concerns",
  "recommended_next_steps": ["Proceed to risk assessment"]
}
```

**Purpose**: Quality-check applicant data before risk evaluation

---

### **Step 2️⃣: Risk Assessment Tool**

**File**: [CreditDecisionAgent.py](CreditDecisionAgent.py#L124-L200)

```python
@tool
def assess_risk_tool(applicant: Dict[str, Any], 
                     collected_data: Dict[str, Any]) -> str:
    """Assess credit risk using Bedrock runtime. Returns JSON string."""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Stronger model
    
    prompt = f"""As a credit risk assessment expert, evaluate the 
    following credit application and collected data and return a JSON 
    object with:
    
    - overall_risk_score (1-100)
    - risk_category (Low, Medium, High, Very High)
    - key_risk_factors
    - mitigating_factors
    - recommended_credit_limit
    - suggested_interest_rate_range
    
    Applicant:
    {json.dumps(applicant, indent=2)}
    
    Collected Data:
    {json.dumps(collected_data, indent=2)}
    
    Please respond in JSON.
    """
    
    # Call Bedrock
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.invoke_model(modelId=model_id, body=json.dumps(native_request))
    analysis_text = response["body"].read().decode("utf-8")
    
    parsed = json.loads(analysis_text)
    return json.dumps(parsed)
```

**Input**: 
- Applicant object (from form submission)
- Collected data (from Step 1 output) ← **CHAINED INPUT**

**Model Used**: Claude-3-Sonnet ($3/1M tokens - stronger reasoning)

**Output JSON**:
```json
{
  "overall_risk_score": 35,
  "risk_category": "Low",
  "key_risk_factors": [
    "DTI ratio at 35% (acceptable but monitored)",
    "Moderate existing debt"
  ],
  "mitigating_factors": [
    "Strong credit score (720+)",
    "Stable employment history",
    "Income supports requested amount"
  ],
  "recommended_credit_limit": 20000,
  "suggested_interest_rate_range": "4.5% - 6.5%"
}
```

**Purpose**: Calculate financial risk; recommend credit terms

---

### **Step 3️⃣: Final Decision Tool**

**File**: [CreditDecisionAgent.py](CreditDecisionAgent.py#L204-L270)

```python
@tool
def make_decision_tool(applicant: Dict[str, Any], 
                       risk_assessment: Dict[str, Any]) -> str:
    """Make final credit decision. Returns JSON string."""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    prompt = f"""You are a senior credit underwriter. Given the applicant 
    and risk assessment, choose one of: APPROVE, DENY, REFER.
    
    For APPROVE include: credit_limit, interest_rate, term_length, conditions
    Include confidence (1-100) and a concise reasoning field.
    
    Return a single JSON object with keys:
    decision, credit_limit, interest_rate, term_length, conditions, 
    confidence, reason
    
    Applicant:
    {json.dumps(applicant, indent=2)}
    
    Risk Assessment:
    {json.dumps(risk_assessment, indent=2)}
    
    Please respond only with the JSON object.
    """
    
    # Call Bedrock with lower temperature (more deterministic)
    native_request = {
        "temperature": 0.2,  # More consistent decisions
        "max_tokens": 2000,
        "messages": [...]
    }
    
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.invoke_model(modelId=model_id, body=...)
    analysis_text = response["body"].read().decode("utf-8")
    
    parsed = json.loads(analysis_text)
    return json.dumps(parsed)
```

**Input**: 
- Applicant object
- Risk assessment JSON (from Step 2) ← **CHAINED INPUT**

**Model Used**: Claude-3-Sonnet

**Output JSON** (Example APPROVE):
```json
{
  "decision": "APPROVE",
  "credit_limit": 15000,
  "interest_rate": 5.5,
  "term_length": 36,
  "conditions": [
    "Automatic payments required",
    "Annual income verification every 12 months",
    "Credit score must stay above 650"
  ],
  "confidence": 88,
  "reason": "Applicant demonstrates strong financial profile with stable income, solid credit history, and low risk indicators. Recommended credit terms are conservative and well-supported by risk assessment."
}
```

**⭐ THIS IS THE KEY AGENT DECISION** - AI autonomously approves or denies credit

---

### **Step 4️⃣: Audit Decision Tool**

**File**: [CreditDecisionAgent.py](CreditDecisionAgent.py#L274-L320)

```python
@tool
def audit_decision_tool(applicant: Dict[str, Any],
                        collected_data: Dict[str, Any],
                        risk_assessment: Dict[str, Any],
                        final_decision: Dict[str, Any]) -> str:
    """Audit the decision flow and return a JSON audit report."""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    prompt = f"""As an audit specialist, review the following and return 
    a JSON report with:
    
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
    
    # Call Bedrock
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.invoke_model(modelId=model_id, body=...)
    analysis_text = response["body"].read().decode("utf-8")
    
    parsed = json.loads(analysis_text)
    return json.dumps(parsed)
```

**Input**: ALL previous outputs (complete review)
- Step 1: Collected Data
- Step 2: Risk Assessment
- Step 3: Final Decision

**Model Used**: Claude-3-Sonnet

**Output JSON**:
```json
{
  "audit_compliance_score": 95,
  "compliance_issues": [],
  "recommendations": [
    "Documentation appears complete",
    "Decision reasoning is well-supported",
    "Risk assessment aligns with decision"
  ],
  "audit_trail_summary": "Complete decision flow with consistent reasoning across all stages. No compliance red flags detected."
}
```

**Purpose**: Quality-check entire decision pipeline for consistency & compliance

---

## Technical Implementation

### **The Orchestrator: `run_credit_decision()`**

**File**: [CreditDecisionAgent.py](CreditDecisionAgent.py#L324-L450)

This is the **master function** that coordinates all 4 AI tools in sequence:

```python
@tool
def run_credit_decision(application_id: int) -> str:
    """Orchestrator: fetch app, run steps, persist outputs, update status."""
    
    try:
        # STEP 0: Fetch application from database
        raw = get_application(application_id)
        app_row = json.loads(raw)
        
        if app_row.get("error"):
            return json.dumps({"error": "application_not_found"})
        
        # Normalize applicant dict
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
        
        # Update status to PROCESSING
        update_application_status(application_id, "PROCESSING")
        progress_messages = []
        
        # Helper: persist partial results
        def _persist_partial(result_partial: dict):
            try:
                result_partial_copy = dict(result_partial)
                result_partial_copy["_progress_messages"] = list(progress_messages)
                update_application_agent_output(application_id, result_partial_copy)
            except Exception:
                pass  # Don't crash if persistence fails
        
        # ═════════════════════════════════════════════════════════════
        # STEP 1: Data Collection
        # ═════════════════════════════════════════════════════════════
        progress_messages.append("Starting data collection")
        _persist_partial({"timestamp": datetime.now().isoformat(), 
                         "applicant": applicant})
        
        collected_raw = collect_data_tool(applicant)
        try:
            collected = json.loads(collected_raw)
            progress_messages.append("Data collection completed")
        except Exception:
            collected = {"raw": collected_raw}
            progress_messages.append("Data collection returned non-JSON")
        
        _persist_partial({
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected
        })
        
        # ═════════════════════════════════════════════════════════════
        # STEP 2: Risk Assessment (CHAINED from Step 1)
        # ═════════════════════════════════════════════════════════════
        progress_messages.append("Starting risk assessment")
        _persist_partial({
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected
        })
        
        # KEY: Pass Step 1 output as input to Step 2
        risk_raw = assess_risk_tool(applicant, collected)
        
        try:
            risk = json.loads(risk_raw)
            progress_messages.append("Risk assessment completed")
        except Exception:
            risk = {"raw": risk_raw}
            progress_messages.append("Risk assessment returned non-JSON")
        
        _persist_partial({
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected,
            "risk_assessment": risk
        })
        
        # ═════════════════════════════════════════════════════════════
        # STEP 3: Final Decision (CHAINED from Step 2)
        # ═════════════════════════════════════════════════════════════
        progress_messages.append("Starting decision making")
        _persist_partial({
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected,
            "risk_assessment": risk
        })
        
        # KEY: Pass Step 2 output as input to Step 3
        decision_raw = make_decision_tool(applicant, risk)
        
        try:
            decision = json.loads(decision_raw)
            progress_messages.append("Decision completed")
        except Exception:
            decision = {"raw": decision_raw}
            progress_messages.append("Decision returned non-JSON")
        
        _persist_partial({
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected,
            "risk_assessment": risk,
            "final_decision": decision
        })
        
        # ═════════════════════════════════════════════════════════════
        # STEP 4: Audit (REVIEWS ALL PREVIOUS STEPS)
        # ═════════════════════════════════════════════════════════════
        progress_messages.append("Starting audit")
        _persist_partial({
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected,
            "risk_assessment": risk,
            "final_decision": decision
        })
        
        # KEY: Pass ALL outputs for full review
        audit_raw = audit_decision_tool(applicant, collected, risk, decision)
        
        try:
            audit = json.loads(audit_raw)
            progress_messages.append("Audit completed")
        except Exception:
            audit = {"raw": audit_raw}
            progress_messages.append("Audit returned non-JSON")
        
        _persist_partial({
            "timestamp": datetime.now().isoformat(),
            "applicant": applicant,
            "data_collection": collected,
            "risk_assessment": risk,
            "final_decision": decision,
            "audit_report": audit
        })
        
        # ═════════════════════════════════════════════════════════════
        # COMPILE FINAL RESULT
        # ═════════════════════════════════════════════════════════════
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
        
        # Persist all outputs to database
        try:
            update_application_agent_output(application_id, result)
        except Exception:
            pass  # Continue even if persistence fails
        
        # ═════════════════════════════════════════════════════════════
        # UPDATE FINAL STATUS IN DATABASE
        # ═════════════════════════════════════════════════════════════
        
        # Extract decision from Step 3
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
        
        # Update with final decision details
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
```

**Key Design Pattern: Input Chaining**

```
Step 1 Input:  applicant
Step 1 Output: collected_data
       ↓
Step 2 Input:  applicant + collected_data ← CHAINED
Step 2 Output: risk_assessment
       ↓
Step 3 Input:  applicant + risk_assessment ← CHAINED
Step 3 Output: final_decision
       ↓
Step 4 Input:  applicant + collected_data + risk_assessment + final_decision
Step 4 Output: audit_report
```

This creates a **reasoning chain** where each step builds on previous AI analysis.

---

## Database Integration

### **Table Structure**

```sql
CREATE TABLE applications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    applicant_name VARCHAR(255),
    age INT,
    income DECIMAL(15,2),
    employment_status VARCHAR(50),
    credit_score INT,
    dti_ratio DECIMAL(5,4),
    existing_debts DECIMAL(15,2),
    requested_credit DECIMAL(15,2),
    
    status VARCHAR(50),  -- PENDING, PROCESSING, APPROVED, DENIED, REFER, ERROR
    reason TEXT,         -- Explanation from AI decision
    confidence INT,      -- 1-100 from make_decision_tool
    agent_output JSON,   -- Complete result from all 4 steps
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### **Key Functions (CreditDecisionStrandsDBTools.py)**

```python
def insert_application(app_dict: dict) -> str:
    """Insert new application, return JSON with inserted_id."""
    # Stores form submission
    # Returns: {"inserted_id": 123}

def get_application(id: int) -> str:
    """Fetch single application by ID."""
    # Returns: Complete application record as JSON

def update_application_status(id: int, status: str, 
                              reason: str = None, 
                              confidence: int = None) -> str:
    """Update status after AI decision."""
    # Called at end of run_credit_decision()

def update_application_agent_output(id: int, 
                                    agent_output: dict) -> str:
    """Persist agent output (called 5 times during processing)."""
    # Stores intermediate and final results as JSON

def list_applications(limit: int = 10) -> str:
    """Get recent applications for dashboard."""

def find_latest_by_applicant(name: str) -> str:
    """Find most recent application for given name."""
```

---

## UI Flow & User Interaction

### **Streamlit Application (credit_decision_ui.py) - Updated Features**

#### **NEW: Sidebar Collapsing Behavior**

The Streamlit UI now implements dynamic sidebar visibility using `st.session_state`:

```python
# Lines 106-110: Initialize sidebar state
if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = True

# Hide sidebar CSS when closed
if not st.session_state.sidebar_open:
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
    </style>
    """, unsafe_allow_html=True)
```

**Behavior Timeline**:
1. **Initial State**: Sidebar open showing application form
2. **User fills form** and clicks "🚀 Process" button
3. **On submission**: 
   - `st.session_state.sidebar_open = False` is set
   - Sidebar collapses and hides completely
   - CSS `display: none` removes the element from view
   - Form data saved to session state for retrieval if reopened
4. **After processing**:
   - Full width available for results display (6 tabs)
   - "📝 Show Form" button appears in main area
   - User can click to reopen sidebar and process new applications
5. **On reopening**: 
   - Previous form values are restored from session state
   - User can edit and submit new applications

#### **NEW: Quick Stats Dashboard**

The sidebar now displays live statistics pulled from the database:

```python
# Lines 135-165: Quick Stats Implementation
if st.session_state.sidebar_open:
    st.sidebar.divider()
    st.sidebar.subheader("📊 Quick Stats")
    try:
        all_apps = list_applications()
        if all_apps:
            apps_list = json.loads(all_apps) if isinstance(all_apps, str) else all_apps
            total = len(apps_list)
            
            # IMPORTANT: Use "application_status" field (not "decision")
            # Values: "APPROVE", "DENY", "REFER"
            approved = sum(1 for a in apps_list if a.get("application_status") == "APPROVE")
            denied = sum(1 for a in apps_list if a.get("application_status") == "DENY")
            pending = sum(1 for a in apps_list if a.get("application_status") == "REFER")
            
            st.sidebar.metric("Total Apps", total)
            st.sidebar.metric("✅ Approved", approved)
            st.sidebar.metric("❌ Denied", denied)
            st.sidebar.metric("⏳ Pending", pending)
            
            if total > 0:
                approval_rate = (approved / total) * 100
                st.sidebar.metric("Approval Rate", f"{approval_rate:.1f}%")
    except Exception as e:
        logger.exception(f"UI: Failed to load quick stats: {e}")
        st.sidebar.info("No data yet")
```

**Key Points**:
- Uses `application_status` field (NOT `decision` field)
- Status values: `"APPROVE"`, `"DENY"`, `"REFER"` (NOT `"APPROVED"`, `"DENIED"`)
- Updates in real-time as new applications are processed
- Automatically calculates approval rate percentage

#### **NEW: Form Data Persistence**

Form values are now persistent across sidebar open/close cycles:

```python
# Lines 112-118: Initialize form data in session state
if "form_data" not in st.session_state:
    st.session_state.form_data = {
        "name": "John Smith",
        "age": 35,
        "income": 75000,
        "employment": "Full-time",
        "credit_score": 720,
        "dti_ratio": 0.35,
        "existing_debts": 25000,
        "requested_credit": 15000,
    }

# Lines 119-165: Use session state values for form inputs
with st.sidebar.form("applicant_form"):
    name = st.text_input("Full Name", value=st.session_state.form_data["name"])
    age = st.number_input("Age", value=st.session_state.form_data["age"])
    # ... rest of inputs
    
    if submitted:
        # Save updated values back to session state
        st.session_state.form_data = {
            "name": name,
            "age": age,
            # ... all other fields
        }
```

#### **NEW: Real-time Progress Display**

During processing, the UI displays only the "progress" element from agent output:

```python
# Lines 254-265: Progress polling with selective display
placeholder = st.empty()

while True:
    raw_app = get_application(app_id)
    appobj = json.loads(raw_app)
    agent_out = appobj.get("agent_output")
    
    if agent_out:
        parsed = json.loads(agent_out) if isinstance(agent_out, str) else agent_out
        
        # Display ONLY the progress element (not entire JSON)
        progress_data = parsed.get("progress") if isinstance(parsed, dict) else None
        if progress_data:
            placeholder.json(progress_data)  # Array of progress messages
        else:
            placeholder.text("Processing... (waiting for progress data)")
```

**Progress Array Format**:
```json
{
  "progress": [
    "[2026-02-08T16:29:52.627598] Agent 1 (DataCollector) starting...",
    "[2026-02-08T16:29:57.100320] Agent 1 (DataCollector) completed",
    "[2026-02-08T16:29:57.492179] Agent 2 (RiskAssessor) starting...",
    "[2026-02-08T16:30:00.580632] Agent 2 (RiskAssessor) completed",
    "[2026-02-08T16:30:00.920012] Agent 3 (DecisionMaker) starting...",
    "[2026-02-08T16:30:05.105415] Agent 3 (DecisionMaker) completed",
    "[2026-02-08T16:30:05.422761] Agent 4 (Auditor) starting...",
    "[2026-02-08T16:30:10.710747] Agent 4 (Auditor) completed"
  ]
}
```

#### **1. Application Form (Left Sidebar - COLLAPSIBLE)**

```python
# Lines 119-135
if st.session_state.sidebar_open:
    st.sidebar.header("📝 Applicant Information")
    
    with st.sidebar.form("applicant_form"):
        st.subheader("Personal Info")
        name = st.text_input("Full Name", value=st.session_state.form_data["name"])
        age = st.number_input("Age", min_value=18, max_value=100, 
                             value=st.session_state.form_data["age"])

        st.subheader("Financial Info")
        income = st.number_input("Annual Income ($)", value=st.session_state.form_data["income"])
        employment = st.selectbox("Employment Status", 
                                ["Full-time", "Part-time", "Self-employed", "Unemployed", "Retired"],
                                index=["Full-time", "Part-time", "Self-employed", "Unemployed", "Retired"]
                                     .index(st.session_state.form_data["employment"]))

        st.subheader("Credit Profile")
        credit_score = st.number_input("Credit Score", value=st.session_state.form_data["credit_score"])
        dti_ratio = st.slider("DTI Ratio", value=st.session_state.form_data["dti_ratio"])
        existing_debts = st.number_input("Existing Debts ($)", value=st.session_state.form_data["existing_debts"])

        st.subheader("Credit Request")
        requested_credit = st.number_input("Requested Credit ($)", value=st.session_state.form_data["requested_credit"])

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted = st.form_submit_button("🚀 Process", type="primary")
        with col_btn2:
            st.form_submit_button("🔄 Clear", type="secondary")
else:
    submitted = False
    # Show reopening button
    if st.sidebar.button("📝 Show Form to Process New Application"):
        st.session_state.sidebar_open = True
        st.rerun()
```

#### **2. Background Processing Thread**

```python
# Lines 172-187
if submitted:
    # Prepare applicant data
    applicant_data = {
        "applicant_name": name,
        "age": age,
        # ... other fields
    }

    # Insert into database
    insert_resp = insert_application(applicant_data)
    insert_obj = json.loads(insert_resp)
    app_id = insert_obj.get("inserted_id")

    # Launch background thread to run agents
    def _agent_worker(aid: int):
        try:
            logger.info(f"Background agent worker started for app_id={aid}")
            run_credit_decision(aid)  # ← Runs the 4-agent pipeline
            logger.info(f"Background agent worker finished for app_id={aid}")
        except Exception:
            logger.exception(f"Background agent worker error for app_id={aid}")

    t = threading.Thread(target=_agent_worker, args=(app_id,), daemon=True)
    t.start()
    
    # Collapse sidebar immediately
    st.session_state.sidebar_open = False
    
    logger.debug(f"Background thread started for app_id={app_id}")
```

#### **3. Polling for Results (Every 1 Second)**

```python
# Lines 237-269
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
            except Exception as parse_err:
                logger.error(f"Failed to parse agent_output: {parse_err}")
                parsed = agent_out
            
            try:
                # Display ONLY the progress element (array of messages)
                progress_data = parsed.get("progress") if isinstance(parsed, dict) else None
                if progress_data:
                    placeholder.json(progress_data)
                else:
                    placeholder.text("Processing... (waiting for progress data)")
            except Exception as display_err:
                logger.error(f"Failed to display JSON: {display_err}")
                placeholder.text(str(parsed)[:2000])

            # Check if processing completed
            if isinstance(parsed, dict) and parsed.get("processing_status") == "completed":
                logger.info(f"Processing completed for app_id={app_id}")
                result = parsed
                break
    except Exception as poll_err:
        logger.warning(f"Polling error for app_id={app_id}: {poll_err}")
        placeholder.text("Waiting for agent to persist progress...")

    # Timeout after 5 minutes
    if time.time() - poll_start > 300:
        logger.error(f"Polling timeout after 300s for app_id={app_id}")
        placeholder.text("Timed out waiting for agent.")
        break
    
    time.sleep(1)  # Poll every 1 second
```

#### **4. Result Display with 6 Tabs**

```python
# Lines 290-380
st.success("✅ Application processed successfully!")

# Clear the status message that was shown during processing
if status_placeholder:
    status_placeholder.empty()

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
tab_progress, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🛰️ Progress", "📊 Data", "⚠️ Risk", "🤖 Decision", "📋 Audit", "📄 Full"
])

with tab1:  # Data Collection
    st.subheader("Data Collection")
    st.json(data_collection)

with tab2:  # Risk Assessment
    st.subheader("Risk Assessment")
    st.json(risk_assessment)

with tab3:  # Final Decision
    st.subheader("Final Decision")
    decision = final_decision.get('decision', 'UNKNOWN')
    if decision == 'APPROVE':
        st.success("✅ Application Approved!")
    elif decision == 'DENY':
        st.error("❌ Application Denied")
    elif decision == 'REFER':
        st.warning("⚠️ Referred for Manual Review")
    st.json(final_decision)

with tab4:  # Audit Report
    st.subheader("Audit Report")
    st.json(audit_report)

with tab5:  # Full Report
    st.subheader("Full Report")
    st.json(result)

with tab_progress:  # Progress Timeline
    st.subheader("Processing Timeline")
    proc_status = result.get("processing_status")
    st.markdown(f"**Status:** {proc_status or 'unknown'}")
```

---

## Models Used & Cost Analysis

### **Model Selection by Step**

| Step | Model | Purpose | Cost/1M tokens | Why? |
|------|-------|---------|--------|------|
| **1️⃣ Data Collection** | Claude-3-Haiku | Analyze data quality | $0.25 input | Fast, cheap, sufficient |
| **2️⃣ Risk Assessment** | Claude-3-Sonnet | Evaluate financial risk | $3 input | Better reasoning |
| **3️⃣ Final Decision** | Claude-3-Sonnet | APPROVE/DENY/REFER | $3 input | Critical decision |
| **4️⃣ Audit** | Claude-3-Sonnet | Review entire flow | $3 input | Comprehensive review |

### **Cost Breakdown (Per Application)**

Assuming average token usage:

- Step 1 (Haiku): ~300 tokens × $0.25/1M = $0.000075
- Step 2 (Sonnet): ~500 tokens × $3/1M = $0.0015
- Step 3 (Sonnet): ~600 tokens × $3/1M = $0.0018
- Step 4 (Sonnet): ~800 tokens × $3/1M = $0.0024

**Total per application: ~$0.0072 (less than 1 cent)**

### **Monthly Cost Estimation**

- 1,000 applications/month: $7.20 in Bedrock + AWS infrastructure
- 10,000 applications/month: $72 in Bedrock + AWS infrastructure

---

## Code References

### **Main Files**

1. **[credit_decision_ui.py](credit_decision_ui.py)** (589 lines)
   - Streamlit web interface
   - Form submission & display
   - Database polling for results
   - 6-tab results dashboard

2. **[CreditDecisionAgent.py](CreditDecisionAgent.py)** (462 lines)
   - 4 decorated `@tool` functions
   - `run_credit_decision()` orchestrator
   - `make_agent()` agent factory
   - Bedrock invocation layer

3. **[CreditDecisionStrandsDBTools.py](CreditDecisionStrandsDBTools.py)** (200+ lines)
   - `insert_application()` - Store form data
   - `get_application()` - Fetch by ID
   - `update_application_status()` - Update decision
   - `update_application_agent_output()` - Persist AI results
   - `list_applications()` - Recent applications
   - `find_latest_by_applicant()` - Find by name

4. **.env** (6 environment variables)
   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - `CREDIT_DECISION_LOG` - Log file path

### **Dependencies**

```
bedrock-agentcore >= 0.1.2    # AWS Bedrock utilities
strands-agents >= 1.6.0        # Agent orchestration framework
streamlit >= 1.28.0            # Web UI
boto3 >= 1.28.0                # AWS SDK
PyMySQL >= 1.0.2               # MySQL connector
python-dotenv >= 0.21.0        # Environment variable loading
anthropic >= 0.7.0             # Anthropic SDK
```

---

## Deployment Architecture

### **Local Development**
```
Windows PC
├── Streamlit UI (localhost:8501)
├── MySQL Database (AWS RDS)
└── Python virtual environment
```

### **Production - EC2 (Recommended)**
```
AWS EC2 Instance (t3.small)
├── 📦 Docker container
│   ├── Python 3.11
│   ├── Streamlit app
│   └── Virtual environment
├── 🌐 Nginx Reverse Proxy
│   ├── Port 80 → 8501
│   └── Port 443 → 8501 (HTTPS)
├── 🔄 Systemd Service
│   ├── Auto-restart on failure
│   └── Process management
└── 📊 CloudWatch Logs (monitoring)

Connected to:
├── AWS RDS (MySQL Database)
├── AWS Bedrock (Claude API)
├── AWS Secrets Manager (credentials)
└── CloudWatch (monitoring & logs)
```

### **Cost Breakdown (Monthly)**

| Service | Instance | Cost |
|---------|----------|------|
| **EC2** | t3.small | $20.74 |
| **RDS** | db.t3.micro | ~$50 |
| **Bedrock** | Per token | ~$5-20 |
| **Data Transfer** | Outbound | ~$2-5 |
| **Total** | | **~$75-95/month** |

*Alternative: App Runner (~$37-100+/mo), Beanstalk (same as EC2), ECS (complex but scales)*

---

## Summary: How AI Agents Work in Your System

### **The Agent Loop**

```
1. User submits form
   ↓
2. Application stored in database (PENDING status)
   ↓
3. Background thread launches run_credit_decision()
   ↓
4️⃣ AGENT STEP 1: AI analyzes data quality
   └─ Result persisted to database
   ↓
5️⃣ AGENT STEP 2: AI assesses financial risk
   └─ Result persisted to database
   ↓
6️⃣ AGENT STEP 3: AI MAKES CREDIT DECISION
   └─ Result persisted to database
   ↓
7️⃣ AGENT STEP 4: AI audits entire flow
   └─ Result persisted to database
   ↓
8. Application status updated (APPROVED/DENIED/REFER)
   ↓
9. UI polls database every 2 seconds
   ↓
10. Results displayed in 6 tabs
    └─ User sees AI decision analysis
```

### **What Makes This "AI Agents"**

✅ **Autonomous**: AI makes binding decisions without human approval  
✅ **Tool-Using**: `@tool` functions called by LLM via Strands  
✅ **Multi-Stage**: 4 sequential AI stages with input chaining  
✅ **Persistent**: All decisions logged for audit trail  
✅ **Production-Grade**: Error handling, logging, monitoring  
✅ **Cost-Optimized**: Haiku for cheap analysis, Sonnet for critical decisions  

---

## Glossary

| Term | Definition |
|------|-----------|
| **Strands** | Amazon's agent orchestration library for tool-calling LLMs |
| **BedrockModel** | AWS wrapper for invoking Claude models via Bedrock API |
| **Bedrock** | AWS managed service for LLM inference (behind the scenes) |
| **@tool** | Python decorator that registers a function as an LLM tool |
| **Tool Calling** | LLM detects function calls in its own response & executes them |
| **Prompt Engineering** | Crafting text prompts to get desired LLM outputs |
| **Input Chaining** | Passing Step N output as input to Step N+1 |
| **JSON Parsing** | Converting text responses from LLM into structured data |
| **Agent Factory** | `make_agent()` function that constructs the agent with all tools |
| **Audit Trail** | Complete record of all AI decisions for compliance |

---

**Document Version**: 1.0  
**Last Updated**: February 5, 2026  
**Status**: Ready for Production Deployment

---

## Quick Start Deployment

See: [EC2_WINDOWS_GUIDE.md](EC2_WINDOWS_GUIDE.md) for step-by-step Windows deployment instructions.

For AWS/Infrastructure: See [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md)

For cost comparison: See [DEPLOYMENT_OPTIONS_COMPARISON.md](DEPLOYMENT_OPTIONS_COMPARISON.md)
