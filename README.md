# 🤖 OrchestrateAI Credit Decision Agent

A multi-agent AI system powered by AWS Bedrock and Anthropic Claude for automated credit application processing and decision-making.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [UI Features](#ui-features)
- [Database Structure](#database-structure)
- [Configuration](#configuration)
- [API & Functions](#api--functions)
- [Troubleshooting](#troubleshooting)
- [Deployment](#deployment)

## 📖 Overview

This system automates credit decision-making by orchestrating four specialized AI agents:

1. **DataCollector** - Validates and analyzes applicant data completeness
2. **RiskAssessor** - Evaluates credit risk using financial metrics
3. **DecisionMaker** - Makes approval/denial/refer decisions with reasoning
4. **Auditor** - Ensures compliance and maintains audit trails

All agents are powered by AWS Bedrock with Anthropic Claude models.

## ✨ Features

### Core Features
- ✅ **Multi-Agent Orchestration** - Four independent agents working in sequence
- ✅ **Real-time Progress Display** - Live updates during processing
- ✅ **Database Persistence** - All applications and decisions stored with full audit trail
- ✅ **Comprehensive Reporting** - Detailed decision reasoning and compliance audit
- ✅ **Risk Assessment** - Multi-factor financial risk evaluation
- ✅ **Compliance Tracking** - Full audit trail with regulatory compliance scoring

### UI Features
- ✅ **Collapsible Sidebar** - Form hides after processing to maximize results view
- ✅ **Quick Stats Dashboard** - Real-time approval/denial/pending counts
- ✅ **Application Form** - Intuitive input for all credit metrics
- ✅ **Real-time Progress Monitoring** - Watch agents work with live updates
- ✅ **Tabbed Results Display** - Organized view of all decision components
- ✅ **Sample Data** - Pre-filled defaults for easy testing

## 🏗️ Architecture

### Components

```
CreditDecisionAgent_MultiAgent.py
├── Agent1: DataCollector (Haiku)
├── Agent2: RiskAssessor (Sonnet)
├── Agent3: DecisionMaker (Sonnet)
└── Agent4: Auditor (Sonnet)
    └── OrchestratorAgent

CreditDecisionAgent.py
└── Wrapper: run_credit_decision(app_id)

credit_decision_ui.py
└── Streamlit Interface

CreditDecisionStrandsDBTools.py
└── Database Operations
```

### Data Flow

```
Application Form → Database Insert → Agent Pipeline → Results Display
                                  ↓ (Progress polling)
                            Progress Update
```

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.11+
- AWS Account with Bedrock access
- MySQL/MariaDB database
- Virtual Environment (recommended)

### 1. Clone Repository

```bash
cd c:\Users\sjunku\Desktop\MyData\MyLearning\AIAgents\AIAgents
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
# or
source .venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create `.env` file in the project root:

```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Database Configuration
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=credit_decision_db

# Logging
CREDIT_DECISION_LOG=credit_decision.log
```

### 5. Initialize Database

```bash
python CreditDecisionStrandsDBTools.py
```

## 🚀 Running the Application

### Option 1: Streamlit UI (Recommended)

```bash
cd c:\Users\sjunku\Desktop\MyData\MyLearning\AIAgents\AIAgents
python -m streamlit run credit_decision_ui.py --server.port 8502
```

Then open: **http://localhost:8502**

### Option 2: CLI Mode

```bash
python CreditDecisionAgent.py --application_id <APP_ID>
```

### Option 3: As Lambda Function (AWS)

```bash
sam build
sam deploy --guided
```

## 🎨 UI Features & Components

### Left Sidebar - Application Form
- **Personal Info**: Full name, age
- **Financial Info**: Annual income, employment status
- **Credit Profile**: Credit score, DTI ratio, existing debts
- **Credit Request**: Requested credit amount
- **Process Button**: Submits application and triggers agent pipeline
- **Collapsible Design**: Form collapses automatically after processing to show results

### Right Sidebar - Quick Stats Dashboard
- **Total Apps**: Total count of all applications
- **✅ Approved**: Count of approved applications (status = APPROVE)
- **❌ Denied**: Count of denied applications (status = DENY)
- **⏳ Pending**: Count of referred applications (status = REFER)
- **Approval Rate**: Percentage of approved applications out of total

*Updates automatically from the database in real-time*

### Center - Results Display
- **Success Message**: "✅ Application processed successfully!"
- **Metrics Summary**: Decision, confidence score, audit compliance score
- **Tabbed Results**:
  - **🛰️ Progress**: Processing timeline and agent execution steps
  - **📊 Data**: Data collection completeness and quality assessment
  - **⚠️ Risk**: Risk category, risk factors, and mitigation strategies
  - **🤖 Decision**: Final approval/denial decision with conditions
  - **📋 Audit**: Compliance scoring and audit trail
  - **📄 Full**: Complete JSON response from all agents

### UI Behaviors

1. **Application Submission Process**:
   - User fills form with applicant details
   - Clicks "🚀 Process" button
   - Sidebar automatically collapses and hides
   - Spinner shows "🤖 Processing application through AI agents..."
   - Agent processes in background thread
   - Progress updates every 1 second from database

2. **Progress Display**:
   - Shows only "progress" element from agent JSON
   - Contains array of agent execution timestamps
   - Updates in real-time as each agent completes

3. **Results Display**:
   - Shows success message once all agents complete
   - Displays key decision metrics
   - Provides detailed analysis in tabs
   - Saves application ID for reference

4. **Show/Hide Form**:
   - Click "📝 Show Form" button to reopen sidebar
   - Previous form values are retained
   - Can process new applications

## 💾 Database Structure

### Applications Table

| Field | Type | Description |
|-------|------|-------------|
| id | INT | Primary key, auto-increment |
| applicant_name | VARCHAR(255) | Full name of applicant |
| age | INT | Age in years (18-100) |
| income | DECIMAL(12,2) | Annual income in dollars |
| employment_status | VARCHAR(50) | Full-time, Part-time, Self-employed, etc. |
| credit_score | INT | Credit score (300-850) |
| dti_ratio | DECIMAL(5,4) | Debt-to-income ratio (0.1-1.0) |
| existing_debts | DECIMAL(12,2) | Total existing debt balances |
| requested_credit | DECIMAL(12,2) | Amount of credit requested |
| application_status | VARCHAR(20) | PROCESSING / APPROVE / DENY / REFER |
| decision_reason | TEXT | Detailed explanation of decision |
| decision_confidence | DECIMAL(5,2) | Confidence level (0-100) |
| agent_output | JSON | Complete output from all agents |
| source | VARCHAR(20) | web / cli / lambda |
| created_at | TIMESTAMP | Application creation time |
| updated_at | TIMESTAMP | Last update time |

### Status Values
- `PROCESSING` - Application is being processed
- `APPROVE` - Credit approved
- `DENY` - Credit denied
- `REFER` - Referred for manual review

## ⚙️ Configuration

### Environment Variables (.env)

```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxxxx
AWS_SECRET_ACCESS_KEY=xxxxx

# Bedrock Models
HAIKU_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
SONNET_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v1:0

# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=password
DB_NAME=credit_decision

# Logging
LOG_LEVEL=INFO
CREDIT_DECISION_LOG=credit_decision.log

# Streamlit
STREAMLIT_SERVER_PORT=8502
STREAMLIT_SERVER_ADDRESS=127.0.0.1
```

### Streamlit Configuration (.streamlit/config.toml)

```toml
[server]
port = 8502
runOnSave = true
enableCORS = true

[logger]
level = "info"
```

## 🔧 API & Functions

### Database Functions (CreditDecisionStrandsDBTools.py)

```python
# Insert new application
result = insert_application({
    "applicant_name": "John Smith",
    "age": 35,
    "income": 75000,
    "employment_status": "Full-time",
    "credit_score": 720,
    "dti_ratio": 0.35,
    "existing_debts": 25000,
    "requested_credit": 15000,
    "source": "web"
})
# Returns: {"inserted_id": 123}

# Get single application
app = get_application(123)
# Returns: Complete application JSON

# Update application status
update_application_status(123, "APPROVE", 
    reason="Strong financial profile", 
    confidence=85)

# Get all applications
apps = list_applications()
# Returns: List of all applications

# Update agent output
update_application_agent_output(123, result_json)

# Find by applicant name
app = find_latest_by_applicant("John Smith")
```

### Agent Functions (CreditDecisionAgent.py)

```python
from CreditDecisionAgent import run_credit_decision, make_agent

# Run credit decision pipeline
run_credit_decision(app_id)

# Initialize agent
agent = make_agent()
```

## 🐛 Troubleshooting

### Port 8502 Already in Use

```powershell
# Kill process on port 8502
Get-NetTCPConnection -LocalPort 8502 -ErrorAction SilentlyContinue | 
  Select-Object -ExpandProperty OwningProcess | 
  ForEach-Object { Stop-Process -Id $_ -Force }
```

### Database Connection Issues

- Verify DB credentials in `.env` file
- Ensure MySQL/MariaDB server is running
- Test connection: `mysql -h localhost -u root -p credit_decision`
- Check network connectivity to database host

### AWS Bedrock Errors

```
Error: "Could not connect to bedrock"
```
- Verify AWS credentials are set correctly
- Check AWS region has Bedrock enabled (us-east-1 recommended)
- Confirm IAM user has `bedrock:*` permissions
- Verify model IDs exist in your region

### Application Stuck Processing

1. Check logs: `Get-Content credit_decision.log -Tail 100`
2. Verify AWS Bedrock is responsive
3. Check database connection
4. Clear browser cache and reload page
5. Restart Streamlit app if needed

### Approved Count Shows 0

**Issue**: Quick Stats shows 0 approved even though applications were processed

**Solution**:
1. Check database values: `SELECT application_status FROM applications LIMIT 5;`
2. Verify values are exactly "APPROVE" (not "APPROVED")
3. Check log for debug info: Search for "Decision counts" in `credit_decision.log`
4. Ensure database connection is working

## 📦 Deployment

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "-m", "streamlit", "run", "credit_decision_ui.py"]
```

```bash
docker build -t credit-decision .
docker run -p 8502:8502 \
  -e AWS_REGION=us-east-1 \
  -e DB_HOST=db.example.com \
  credit-decision
```

### AWS EC2

See `setup-ec2.sh` for automated EC2 deployment

### AWS Lambda

See `README_LAMBDA.md` for Lambda + API Gateway setup

### AWS App Runner

See `AWS_DEPLOYMENT_GUIDE.md` for App Runner deployment

## 📊 Monitoring & Logs

### Log File Location
- `credit_decision.log` - Main application log file

### View Logs
```powershell
# Last 100 lines
Get-Content credit_decision.log -Tail 100

# Real-time monitoring
Get-Content credit_decision.log -Wait
```

### Log Levels
- **DEBUG**: Detailed operational information
- **INFO**: General information messages
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical failures

## 📁 Project Structure

```
AIAgents/
├── credit_decision_ui.py           # Streamlit UI
├── CreditDecisionAgent.py           # Agent wrapper
├── CreditDecisionAgent_MultiAgent.py # Agent definitions
├── CreditDecisionStrandsDBTools.py   # Database functions
├── requirements.txt                 # Dependencies
├── .env                            # Environment config
├── credit_decision.log             # Log file
├── README.md                       # This file
├── TECHNICAL_FLOW_DOCUMENTATION.md # Technical details
├── README_LAMBDA.md                # Lambda setup
├── README_MULTI_AGENT.md           # Multi-agent details
└── setup-ec2.sh                    # EC2 setup script
```

## 📞 Support

- **Issues**: Check `credit_decision.log` for error messages
- **Configuration**: Update `.env` file
- **Agents**: Edit `CreditDecisionAgent_MultiAgent.py`
- **Database**: See `CreditDecisionStrandsDBTools.py`

---

**Last Updated**: February 8, 2026  
**Version**: 1.0.0  
**Status**: Production Ready  
**Powered by OrchestrateAI
