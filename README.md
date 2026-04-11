# 🤖 OrchestrateAI Credit Decision Agent

A multi-agent AI system powered by AWS Bedrock and Anthropic Claude for automated credit application processing and decision-making, with an MCP (Model Context Protocol) server for database operations.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [MCP Server](#mcp-server)
- [UI Features](#ui-features)
- [Banking Rules Engine](#banking-rules-engine)
- [Database Structure](#database-structure)
- [Configuration](#configuration)
- [API & Functions](#api--functions)
- [Postman Collection](#postman-collection)
- [Infrastructure (Terraform)](#infrastructure-terraform)
- [Troubleshooting](#troubleshooting)
- [Deployment](#deployment)

## 📖 Overview

This system automates credit decision-making by orchestrating four specialized AI agents:

1. **DataCollector** (Claude 3 Haiku) — Validates and analyzes applicant data completeness
2. **RiskAssessor** (Claude 3 Sonnet) — Evaluates credit risk using financial metrics
3. **DecisionMaker** (Claude 3 Sonnet) — Makes APPROVE/DENY/REFER decisions with reasoning
4. **Auditor** (Claude 3 Sonnet) — Ensures compliance and maintains audit trails

All database operations — including the Streamlit UI — go through an **MCP Server**, which can also be consumed by VS Code Copilot, Claude Desktop, or any MCP-compatible client.

## ✨ Features

### Core Features
- **Multi-Agent Orchestration** — Four independent agents working in sequence
- **MCP Server** — Database operations exposed as MCP tools (SSE, stdio, streamable-http)
- **MCP-Backed Agent** — Agent pipeline using MCP server for all DB operations
- **YAML-Driven Rule Engine** — Credit decision rules loaded from `banking_rules.yaml`
- **Multi-Provider LLM Support** — AWS Bedrock, OpenAI, Azure OpenAI via `LLMProvider`
- **Real-time Progress Display** — Live updates during processing
- **Database Persistence** — All applications and decisions stored with full audit trail
- **Comprehensive Reporting** — Detailed decision reasoning and compliance audit
- **Risk Assessment** — Multi-factor financial risk evaluation (weighted scoring)
- **Compliance Tracking** — ECOA, TILA, Dodd-Frank, Reg-Z compliance checks

### UI Features
- **Collapsible Sidebar** — Form hides after processing to maximize results view
- **Quick Stats Dashboard** — Real-time approval/denial/pending counts
- **Application Form** — Intuitive input for all credit metrics
- **Real-time Progress Monitoring** — Watch agents work with live updates
- **Tabbed Results Display** — Progress, Data, Risk, Decision, Audit, Full Report
- **Sample Data** — Pre-filled defaults for easy testing

## 🏗️ Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI (:8504)                      │
│                  credit_decision_ui.py                       │
│             (uses MCPDatabaseClient + MCPOrchestratorAgent)  │
└──────────────────────┬──────────────────────────────────────┘
                       │ SSE
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  MCP Server (:8080)                          │
│              credit_decision_mcp_server.py                   │
│                                                              │
│   @mcp.tool() functions (SSE / stdio / streamable-http)      │
│   get_application · list_applications · insert_application   │
│   update_application_status · update_application_agent_output│
│   find_latest_by_applicant                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ PyMySQL
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           MySQL (AWS RDS) — credit_applications              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Agent Pipeline (4 Agents)                       │
│              CreditDecisionAgent_MCP.py                      │
│              MCPOrchestratorAgent → MCPDatabaseClient         │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Data    │→│  Risk    │→│ Decision │→│  Audit   │       │
│  │Collector │ │ Assessor │ │  Maker   │ │  Agent   │       │
│  │ (Haiku)  │ │ (Sonnet) │ │ (Sonnet) │ │ (Sonnet) │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            LLMProvider.py (Multi-Provider)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐              │
│  │ Bedrock  │  │  OpenAI  │  │ Azure OpenAI │              │
│  └──────────┘  └──────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Streamlit UI
    │
    ├── MCPDatabaseClient.insert_application() ──→ MCP Server ──→ MySQL
    │
    ├── MCPOrchestratorAgent.process_application(app_id)
    │       │
    │       ├── DataCollector  (Agent 1) ──→ LLM
    │       ├── RiskAssessor   (Agent 2) ──→ LLM
    │       ├── DecisionMaker  (Agent 3) ──→ LLM
    │       └── Auditor        (Agent 4) ──→ LLM
    │       │
    │       └── update_status() + update_agent_output() ──→ MCP Server ──→ MySQL
    │
    └── UI polls MCPDatabaseClient.get_application() ──→ MCP Server ──→ MySQL
            │
            └── Displays results in real-time tabs
```

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.11+
- AWS Account with Bedrock access (Claude models enabled)
- MySQL database (RDS or local)

### 1. Create Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
# or
source .venv/bin/activate     # Linux/Mac
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Edit `resource/properties` with your database and AWS credentials:

```properties
DB_HOST=your-rds-host.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=your_password
DB_NAME=dev
AWS_BEARER_TOKEN_BEDROCK=your_bearer_token
```

These are auto-loaded into `os.environ` at import time by `LLMProvider._load_env_from_properties()`. Explicit environment variables take precedence over file values.

### 4. Initialize Database

```bash
python setup_database.py
```

Or provision infrastructure with Terraform (see [Infrastructure](#infrastructure-terraform)).

### 5. Provision Infrastructure (Optional)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars  # Edit with your values
terraform init
terraform apply
```

## 🚀 Running the Application

### Option 1: Streamlit UI (Recommended)

The UI requires the MCP server to be running first:

```bash
# Terminal 1: Start MCP server
python credit_decision_mcp_server.py --transport sse --port 8080

# Terminal 2: Start Streamlit UI
streamlit run credit_decision_ui.py --server.port 8504 --server.address localhost
```

Open: **http://localhost:8504**

The UI connects to the MCP server at `http://127.0.0.1:8080/sse` by default (configurable via `MCP_URL` env var).

### Option 2: CLI — Via MCP Server

```bash
# Terminal 1: Start MCP server (if not already running)
python credit_decision_mcp_server.py --transport sse --port 8080

# Terminal 2: Run agent via MCP
python CreditDecisionAgent_MCP.py --application_id <APP_ID> --mcp-url http://127.0.0.1:8080/sse
```

### Option 3: CLI — Direct DB Access (Legacy)

```bash
python CreditDecisionAgent.py --application_id <APP_ID>
```

> **Note:** This mode uses `CreditDecisionStrandsDBTools.py` for direct PyMySQL access and does not require the MCP server.

## 🔌 MCP Server

The MCP server (`credit_decision_mcp_server.py`) exposes all database operations as MCP tools consumable by any MCP-compatible client.

### Starting the Server

```bash
# SSE transport (for remote clients, Postman, MCP Inspector)
python credit_decision_mcp_server.py --transport sse --port 8080

# stdio transport (for VS Code Copilot, Claude Desktop)
python credit_decision_mcp_server.py --transport stdio

# Streamable HTTP transport
python credit_decision_mcp_server.py --transport streamable-http --port 8080
```

### MCP Tools (6)

| Tool | Description |
|------|-------------|
| `get_application(application_id)` | Fetch a single application by ID |
| `list_applications(limit=10)` | List recent applications (newest first) |
| `insert_application(...)` | Insert a new credit application |
| `update_application_status(application_id, status, reason, confidence)` | Update status/reason/confidence |
| `find_latest_by_applicant(applicant_name)` | Case-insensitive applicant lookup |
| `update_application_agent_output(application_id, agent_output)` | Store full AI pipeline output as JSON |

### VS Code MCP Inspector Configuration

The `.vscode/mcp.json` file provides two server configurations:

```json
{
  "servers": {
    "credit-decision-db": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": ["credit_decision_mcp_server.py"],
      "cwd": "${workspaceFolder}"
    },
    "credit-decision-db-sse": {
      "type": "sse",
      "url": "http://127.0.0.1:8080/sse"
    }
  }
}
```

- **stdio**: Used by VS Code Copilot and Claude Desktop (auto-starts the server)
- **SSE**: For MCP Inspector and remote clients (requires the server to be running)

### MCP-Backed Agent

`CreditDecisionAgent_MCP.py` provides the classes used by both the Streamlit UI and CLI:

- **MCPDatabaseClient** — Wraps MCP tool calls via `strands.tools.mcp.MCPClient` + SSE transport. The Streamlit UI caches this in `st.session_state` for the session lifetime.
- **MCPOrchestratorAgent** — Runs the 4-agent pipeline, persisting progress to DB via MCP after each agent completes.

CLI usage:
```bash
python CreditDecisionAgent_MCP.py --application_id 26 --mcp-url http://127.0.0.1:8080/sse
```

## 🎨 UI Features & Components

### Sidebar — Application Form
- **Personal Info**: Full name (default "John Smith"), age (18-100), email
- **Financial Info**: Annual income, employment status dropdown, existing debts
- **Credit Profile**: Credit score (300-850), DTI ratio (0-1 slider)
- **Credit Request**: Requested credit amount
- **Buttons**: "🚀 Process" (submit) and "🔄 Clear" (reset)
- **Collapsible Design**: Form collapses after processing to maximize results view

### Quick Stats Dashboard
- **Total Apps** | **Approved** | **Denied** | **Pending** | **Approval Rate**
- Fetched from MCP server in real-time

### Results Display (6 Tabs)
| Tab | Content |
|-----|---------|
| 🛰️ Progress | Real-time processing timeline with agent execution timestamps |
| 📊 Data | Data completeness score, quality assessment, risk indicators |
| ⚠️ Risk | Overall risk score, risk category, risk factors, mitigating factors |
| 🤖 Decision | APPROVE/DENY/REFER with confidence, conditions, reasoning |
| 📋 Audit | Compliance score, fair lending check (PASS/FLAG/FAIL), regulatory compliance |
| 📄 Full | Complete JSON response from all agents |

### Processing Flow
1. User fills form → clicks "🚀 Process"
2. Application inserted via MCP server (`MCPDatabaseClient.insert_application()`)
3. Background thread runs `MCPOrchestratorAgent.process_application(app_id)` — all 4 agents execute sequentially, persisting progress to DB via MCP after each step
4. UI polls MCP server every 1 second (`MCPDatabaseClient.get_application()`) for `agent_output` updates
5. Tabs unlock progressively as each agent completes
6. Summary metrics displayed: Decision, Confidence, Audit Score

## 📏 Banking Rules Engine

Credit decision rules are defined in `banking_rules.yaml` and loaded by `BankingRulesLoader.py`.

### Rule Categories

| Category | Key Rules |
|----------|-----------|
| **Credit Score Tiers** | Excellent (750-850): 95% approval · Good (700-749): 80% · Fair (650-699): 50% · Poor (600-649): 25% · Very Poor (<600): 5% |
| **DTI Thresholds** | Excellent (0-30%) · Acceptable (30-35%) · Marginal (35-40%): needs compensating factors · High Risk (40-45%): manual review · Unacceptable (>45%): decline |
| **Income** | Minimum annual: $25,000 · Employment scoring: Full-time (100), Part-time 2yr+ (60), Self-employed 3yr+ (65), Retired (75) |
| **Loan Limits** | Max loan-to-income: 3.0x · Max loan-to-credit-score: 50x (use more restrictive) |
| **Decision Triggers** | APPROVE: score ≥700 + DTI <30% + income ≥$30k · REFER: score 650-699 or DTI 30-40% · DENY: score <600 or DTI >45% or income <$25k |
| **Risk Score** | Payment History (40%) + Credit Utilization (20%) + Credit Age (15%) + Inquiries (15%) + Income Stability (10%) |
| **Compliance** | ECOA, TILA, Dodd-Frank, Reg-Z · Adverse action notice within 30 days · Data retention: apps 3 yrs, audit logs 7 yrs |

### Utility Functions

```python
from BankingRulesLoader import (
    get_system_context,          # System prompt for agents
    get_credit_decision_rules,   # Decision triggers
    get_risk_framework,          # Risk scoring methodology
    get_compliance_rules,        # Regulatory requirements
    calculate_dti_compliance,    # DTI tier check
    calculate_credit_score_tier, # Score tier check
    evaluate_employment_stability,
    validate_income_minimum,
    calculate_max_loan_amount,
    get_compensating_factors,
    get_special_circumstances,
    reload_rules,                # Hot-reload from YAML
)
```

## 💾 Database Structure

### credit_applications Table

| Field | Type | Description |
|-------|------|-------------|
| id | INT AUTO_INCREMENT | Primary key |
| applicant_name | VARCHAR(255) | Full name |
| applicant_dob | DATE | Date of birth |
| age | INT | Age in years |
| email | VARCHAR(255) | Email address |
| income | DECIMAL(15,2) | Annual income (USD) |
| employment_status | VARCHAR(50) | Full-time / Part-time / Self-employed / Retired / Unemployed |
| credit_score | INT | FICO score (300-850) |
| dti_ratio | DECIMAL(5,4) | Debt-to-income ratio |
| existing_debts | DECIMAL(15,2) | Total existing debts (USD) |
| requested_credit | DECIMAL(15,2) | Requested credit amount (USD) |
| source | VARCHAR(50) | Application source (web / cli / api / postman) |
| application_status | VARCHAR(50) | PENDING / PROCESSING / APPROVED / DENIED / REFER / ERROR |
| reason | TEXT | Decision explanation |
| confidence | INT | Confidence score (1-100) |
| agent_output | JSON | Complete result from all 4 agents |
| created_at | TIMESTAMP | Auto-set on creation |
| updated_at | TIMESTAMP | Auto-updated on modification |

**Indexes**: `idx_status`, `idx_applicant`, `idx_created`, `idx_email`

### DB Connection Strategy

All clients (UI, CLI, VS Code Copilot) connect to the **MCP Server**, which handles DB access:

```
Clients (UI / CLI / Copilot)
        │ SSE / stdio
        ▼
MCP Server (credit_decision_mcp_server.py)
        │ PyMySQL
        ▼
MySQL (AWS RDS)
        │ credentials from:
        ├── AWS Secrets Manager
        ├── resource/properties
        └── Environment variables
```

## ⚙️ Configuration

### resource/properties

Primary configuration file, auto-loaded into `os.environ` at startup:

```properties
DB_HOST=your-rds-host.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=your_password
DB_NAME=dev
AWS_BEARER_TOKEN_BEDROCK=your_bearer_token
```

### Environment Variables

Environment variables override `resource/properties` values:

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_URL` | MCP server SSE endpoint (used by UI) | `http://127.0.0.1:8080/sse` |
| `DB_HOST` | MySQL host | (from properties) |
| `DB_PORT` | MySQL port | 3306 |
| `DB_USER` | DB username | admin |
| `DB_PASSWORD` | DB password | (from properties) |
| `DB_NAME` | Database name | dev |
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock bearer token | (from properties) |
| `AWS_REGION` | AWS region | us-east-1 |
| `CREDIT_DECISION_LOG` | Log file path | credit_decision.log |
| `LLM_{AGENT}_PROVIDER` | LLM provider per agent | bedrock |
| `LLM_{AGENT}_MODEL` | Model ID per agent | us.anthropic.claude-sonnet-4-6 |
| `LLM_{AGENT}_MAX_TOKENS` | Max tokens per agent | 1000 |
| `LLM_{AGENT}_TEMPERATURE` | Temperature per agent | 0.3 |

### LLM Provider Configuration

`LLMProvider.py` supports multiple providers via `ModelConfig`:

```python
@dataclass
class ModelConfig:
    provider: str       # "bedrock", "openai", "azure_openai"
    model_id: str
    max_tokens: int = 1000
    temperature: float = 0.3
    region: str = None  # Bedrock
    api_key: str = None # OpenAI / Azure
```

Per-agent model configuration via env vars:
- `LLM_DATA_COLLECTOR_MODEL`, `LLM_RISK_ASSESSOR_MODEL`, `LLM_DECISION_MAKER_MODEL`, `LLM_AUDITOR_MODEL`

## 🔧 API & Functions

### Database Functions (CreditDecisionStrandsDBTools.py)

```python
# Insert new application
insert_application({
    "applicant_name": "John Smith", "age": 35,
    "income": 75000, "employment_status": "Full-time",
    "credit_score": 720, "dti_ratio": 0.35,
    "existing_debts": 25000, "requested_credit": 15000,
    "source": "web"
})  # → {"inserted_id": 123}

# Get single application
get_application(123)  # → Application JSON

# List recent applications
list_applications(limit=10)  # → JSON array

# Update status
update_application_status(123, "APPROVE",
    reason="Strong financial profile", confidence=85)

# Store agent output
update_application_agent_output(123, result_json)

# Find by name
find_latest_by_applicant("John Smith")
```

### Agent Functions

```python
# Direct DB mode
from CreditDecisionAgent_MultiAgent import OrchestratorAgent
agent = OrchestratorAgent()
result = agent.process_application(app_id)

# MCP mode
from CreditDecisionAgent_MCP import MCPDatabaseClient, MCPOrchestratorAgent
db = MCPDatabaseClient("http://127.0.0.1:8080/sse")
agent = MCPOrchestratorAgent(db)
result = agent.process_application(app_id)

# Single-agent wrapper
from CreditDecisionAgent import run_credit_decision
run_credit_decision(app_id)
```

## 📬 Postman Collection

A ready-to-use Postman collection is available at `postman/Credit_Decision_MCP_Server.postman_collection.json`.

### Import
1. Open Postman → **Import** → Select the JSON file
2. Set collection variable `session_id` after connecting to SSE

### Included Requests (8)

| Folder | Request | Description |
|--------|---------|-------------|
| 1. Connect SSE | Open SSE Connection | `GET /sse` — Get session_id |
| 2. Discovery | Initialize | MCP handshake (`initialize` method) |
| 2. Discovery | List Tools | Discover available tools (`tools/list`) |
| 3. Read Operations | Get Application by ID | `tools/call` → `get_application` |
| 3. Read Operations | List Applications | `tools/call` → `list_applications` |
| 3. Read Operations | Find Latest by Applicant | `tools/call` → `find_latest_by_applicant` |
| 4. Write Operations | Insert Application | `tools/call` → `insert_application` |
| 4. Write Operations | Update Application Status | `tools/call` → `update_application_status` |

### Workflow
1. **GET /sse** → Copy `session_id` from response
2. **POST /messages/?session_id=...** → `initialize` (handshake)
3. **POST /messages/?session_id=...** → `tools/list` (discover tools)
4. **POST /messages/?session_id=...** → `tools/call` with tool name + arguments

## 🏗️ Infrastructure (Terraform)

The `terraform/` directory provisions AWS infrastructure:

| Resource | Details |
|----------|---------|
| **RDS MySQL** | MySQL 8.0, `db.t3.micro` (free tier), 20GB gp2, public access |
| **Security Group** | Port 3306 open (dev only) |
| **DB Initialization** | Runs `setup_database.py` after RDS creation |

```bash
cd terraform
terraform init
terraform apply -var="db_password=your_password"
```

**Variables**: `aws_region` (us-east-1), `environment` (dev), `project_name` (orchestrateai), `db_name` (dev), `db_username` (admin), `db_password`, `db_instance_class` (db.t3.micro)

**Outputs**: `db_host`, `db_port`, `db_name`, `db_endpoint_full`, `security_group_id`

## 🐛 Troubleshooting

### Port Already in Use

```powershell
# Kill process on a specific port (e.g., 8504 or 8080)
Get-NetTCPConnection -LocalPort 8504 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

### Database Connection Issues

- Verify credentials in `resource/properties`
- Ensure RDS security group allows your IP on port 3306
- Test: `python setup_database.py`

### AWS Bedrock Errors

```
UnrecognizedClientException: The security token included in the request is invalid
```
- Set `AWS_BEARER_TOKEN_BEDROCK` in `resource/properties` or as env var
- Verify the token hasn't expired
- Check AWS region has Bedrock enabled (us-east-1 recommended)

### MCP Server Issues

```bash
# Check if MCP server is running
curl http://127.0.0.1:8080/sse

# Restart with verbose output
python credit_decision_mcp_server.py --transport sse --port 8080
```

### Application Stuck Processing

1. Check logs: `Get-Content credit_decision.log -Tail 100`
2. Verify AWS Bedrock is responsive
3. Check database connection
4. Restart Streamlit app if needed

## 📊 Monitoring & Logs

### Log Configuration
- **File**: `credit_decision.log` (rotating: 10MB per file, 5 backups)
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

```powershell
# Last 100 lines
Get-Content credit_decision.log -Tail 100

# Real-time monitoring
Get-Content credit_decision.log -Wait
```

## 📁 Project Structure

```
AIAgents/
├── credit_decision_ui.py              # Streamlit web interface (:8504, uses MCP)
├── credit_decision_mcp_server.py      # MCP server for DB operations (:8080)
├── CreditDecisionAgent.py             # Single-agent entry point
├── CreditDecisionAgent_MultiAgent.py  # 4-agent pipeline (direct DB)
├── CreditDecisionAgent_MCP.py         # 4-agent pipeline via MCP (used by UI)
├── CreditDecisionStrandsDBTools.py    # @tool DB functions — direct PyMySQL (legacy)
├── LLMProvider.py                     # Multi-provider LLM abstraction
├── BankingRulesLoader.py              # YAML rule engine loader
├── BankingRules.py                    # Legacy embedded rules
├── banking_rules.yaml                 # Credit decision rules configuration
├── setup_database.py                  # DB schema initialization
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Project metadata
├── template.yaml                      # SAM template (EC2 stop utility)
├── Procfile                           # Process manager config
├── resource/
│   └── properties                     # DB + AWS credentials (auto-loaded)
├── .vscode/
│   └── mcp.json                       # MCP server config (stdio + SSE)
├── postman/
│   └── Credit_Decision_MCP_Server.postman_collection.json
├── terraform/
│   ├── main.tf                        # RDS + security group + DB init
│   ├── variables.tf                   # Input variables
│   ├── outputs.tf                     # Output values
│   └── init_db.sql                    # CREATE TABLE DDL
├── python/
│   └── pymysql/                       # Bundled PyMySQL library
└── log/                               # Log directory
```

## 📞 Support

- **Logs**: `credit_decision.log`
- **Configuration**: `resource/properties`
- **Agent Pipeline**: `CreditDecisionAgent_MultiAgent.py`
- **MCP Server**: `credit_decision_mcp_server.py`
- **Database Tools**: `CreditDecisionStrandsDBTools.py`
- **Banking Rules**: `banking_rules.yaml`

---

**Last Updated**: April 11, 2026
**Version**: 2.0.0
**Status**: Production Ready
**OrchestrateAI**
