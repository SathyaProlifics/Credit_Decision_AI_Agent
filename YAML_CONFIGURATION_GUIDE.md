# Banking Rules Configuration Guide

## Overview

The credit decision system now uses an **external YAML configuration file** (`banking_rules.yaml`) to manage all banking rules, regulatory requirements, and decision criteria. This approach provides:

- ✅ **Easy Updates**: Modify rules without changing code
- ✅ **Version Control**: Track changes to policies over time
- ✅ **Compliance Ready**: Centralized rules for audit trails
- ✅ **PDFs**: Export YAML to PDF for official documentation
- ✅ **Dynamic Loading**: Rules are loaded at runtime for instant updates

## File Structure

```
AIAgents/
├── BankingRulesLoader.py      # Python module that loads YAML rules
├── banking_rules.yaml          # External configuration file with all rules
├── CreditDecisionAgent_MultiAgent.py  # Agents that use the rules
├── credit_decision_ui.py        # Streamlit UI
└── requirements.txt             # Added PyYAML>=6.0
```

## How Rules Are Loaded

### 1. Module Initialization
When `CreditDecisionAgent_MultiAgent.py` starts:
```python
from BankingRulesLoader import get_system_context, get_credit_decision_rules, ...
```

### 2. Runtime Loading
The `BankingRulesLoader` dynamically reads `banking_rules.yaml`:
```python
def load_banking_rules() -> Dict[str, Any]:
    rules_file = Path(__file__).parent / "banking_rules.yaml"
    with open(rules_file, 'r') as f:
        rules = yaml.safe_load(f)
    return rules
```

### 3. Context Building
Agents receive formatted context from the YAML:
```python
prompt = f"""{get_system_context()}

[Agent-specific task]
"""
```

## Configuration File Structure

The `banking_rules.yaml` is organized into sections:

### Section 1: Regulatory Framework
```yaml
regulatory_framework:
  fair_lending:
    description: "..."
    acts:
      - name: "Equal Credit Opportunity Act (ECOA)"
        requirements: "..."
```

### Section 2: Credit Decision Matrix
Defines approval rules by credit score, DTI, income, etc.
```yaml
credit_decision_matrix:
  credit_score_tiers:
    excellent:
      range: [750, 850]
      category: "Prime"
      approval_probability: 0.95
```

### Section 3: Risk Assessment Framework
```yaml
risk_assessment:
  risk_score_components:
    payment_history:
      weight: 0.40
      excellent_score: 35
```

### Section 4: Compliance Requirements
```yaml
compliance_framework:
  required_documentation:
    every_decision:
      - "Applicant identification..."
```

### Section 5: Special Circumstances
```yaml
special_circumstances:
  recent_bankruptcy:
    requirement: "Requires manual review"
```

## Using the Banking Rules in Your Code

### Option 1: Get Full System Context (Recommended)
```python
from BankingRulesLoader import get_system_context

# Pass to your LLM agent
prompt = f"""{get_system_context()}

Your agent task here...
"""
```

### Option 2: Get Specific Rule Sections
```python
from BankingRulesLoader import (
    get_credit_decision_rules,
    get_risk_framework,
    get_compliance_rules
)

# Get specific rules
decision_rules = get_credit_decision_rules()
risk_rules = get_risk_framework()
compliance_rules = get_compliance_rules()
```

### Option 3: Use Helper Functions
```python
from BankingRulesLoader import (
    calculate_dti_compliance,
    calculate_credit_score_tier,
    calculate_max_loan_amount,
    validate_income_minimum
)

# Calculate DTI compliance
dti_result = calculate_dti_compliance(0.35)
# Returns: {"tier": "acceptable", "status": "PASS", "risk": "low-medium"}

# Calculate credit score tier
score_result = calculate_credit_score_tier(750)
# Returns: {"tier": "excellent", "category": "Prime", "approval_probability": 0.95}

# Calculate max loan
max_loan = calculate_max_loan_amount(75000, 720)
# Returns: 36000 (more restrictive of 3x income or 50x score)

# Validate income
income_check = validate_income_minimum(35000)
# Returns: {"valid": True, "message": "Income sufficient..."}
```

## Updating Banking Rules

### Step 1: Edit the YAML File
Open `banking_rules.yaml` and modify any section:

**Example: Update minimum income requirement**
```yaml
income_requirements:
  minimum_annual: 30000  # Changed from 25000
```

**Example: Update DTI thresholds**
```yaml
dti_thresholds:
  marginal:
    range: [0.35, 0.42]  # Changed upper limit
```

**Example: Add new compensating factor**
```yaml
compensating_factors:
  acceptable_factors:
    - name: "Letter of Employment"
      requirement: "Verifying future employment"
      strength: "medium"
```

### Step 2: Rules Load Automatically
The next time agents run, they automatically read the updated rules from the YAML file.

### Step 3: Reload During Runtime (Optional)
```python
from BankingRulesLoader import reload_rules

# Reload rules without restarting the app
success = reload_rules()
if success:
    print("Rules reloaded successfully")
```

## Converting YAML to PDF

To create official PDF documentation from the YAML rules:

### Option 1: Using Python
```python
import yaml
import subprocess

# Convert YAML to markdown first
with open('banking_rules.yaml', 'r') as f:
    rules = yaml.safe_load(f)

# Then convert to PDF using pandoc
# pandoc banking_rules.md -o banking_rules.pdf
```

### Option 2: Using Online Tools
1. Convert YAML to JSON/markdown at https://yaml-online-parser.appspot.com/
2. Use markdown to PDF converter at https://md2pdf.netlify.app/

### Option 3: Using Command Line (Pandoc)
```bash
# Install pandoc (Windows)
choco install pandoc

# Convert markdown to PDF
pandoc banking_rules.md -o banking_rules.pdf \
  --pdf-engine=xelatex \
  --toc \
  --toc-depth=2
```

## Example: How Agents Use the Rules

### DataCollectorAgent
```
Load System Context (includes regulatory framework)
         ↓
Agent receives: "Ensure compliance with ECOA, TILA, Reg-Z..."
         ↓
Agent analyzes applicant data
         ↓
Agent checks: regulatory_requirements_met
```

### RiskAssessorAgent
```
Load Risk Assessment Framework
         ↓
Agent reads: risk_score_components (payment_history: 40%, etc.)
         ↓
Agent reads: risk_categories (Low/Medium/High/Very High)
         ↓
Agent reads: red_flags and green_flags
         ↓
Agent calculates overall_risk_score using framework
```

### DecisionMakerAgent
```
Load Credit Decision Matrix
         ↓
Agent reads: approval_triggers, refer_triggers, deny_triggers
         ↓
Agent counts matching criteria
         ↓
Agent determines: APPROVE/REFER/DENY
         ↓
Agent cites: policy references and decision matrix
```

### AuditAgent
```
Load Compliance Framework
         ↓
Agent checks: regulatory_compliance (ECOA/TILA/Reg-Z/Dodd-Frank)
         ↓
Agent verifies: required_documentation present
         ↓
Agent assesses: audit_compliance_score
         ↓
Agent determines: adverse_action_notice_required
```

## Monitoring and Validation

### Check if Rules Are Loaded
```python
from BankingRulesLoader import check_rules_loaded

if check_rules_loaded():
    print("✓ Banking rules successfully loaded")
else:
    print("✗ ERROR: Banking rules failed to load")
```

### Verify Specific Rule
```python
from BankingRulesLoader import BANKING_RULES

# Check a specific rule
min_income = BANKING_RULES['credit_decision_matrix']['income_requirements']['minimum_annual']
print(f"Minimum annual income requirement: ${min_income:,}")
```

## Troubleshooting

### Issue: "Banking rules file not found"
**Solution**: Ensure `banking_rules.yaml` is in the same directory as `BankingRulesLoader.py`
```bash
# Verify file location
ls -la banking_rules.yaml
```

### Issue: "Error parsing banking rules YAML"
**Solution**: Validate YAML syntax at https://www.yamllint.com/
```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('banking_rules.yaml'))"
```

### Issue: "Banking rules not loaded - using empty fallback"
**Solution**: Check file permissions and PyYAML installation
```bash
# Reinstall PyYAML
pip install --upgrade pyyaml

# Check file permissions
chmod 644 banking_rules.yaml  # Linux/Mac
```

## Best Practices

1. **Version Control**: Track YAML changes in Git
   ```bash
   git add banking_rules.yaml
   git commit -m "Update: Increase minimum income to $30k"
   ```

2. **Documentation**: Add comments in YAML for policy changes
   ```yaml
   # Updated 2026-03-29: Increased from $25k to $30k per regulatory guidance
   minimum_annual: 30000
   ```

3. **Testing**: Test rule changes with sample applications before production
   ```python
   # Test with borderline applicant
   test_dti = 0.35
   result = calculate_dti_compliance(test_dti)
   ```

4. **Audit Trail**: Keep backup copies of historical YAML versions
   ```bash
   cp banking_rules.yaml banking_rules.v1.0.yaml
   ```

5. **Regular Reviews**: Audit rules quarterly to ensure compliance
   - Review against latest regulations
   - Update approval/denial rates
   - Adjust risk thresholds as needed

## Integration with Existing Systems

The YAML-based rules seamlessly integrate with:
- ✅ Multi-agent orchestration (Strands)
- ✅ LLM providers (Bedrock, OpenAI, etc.)
- ✅ Database (MySQL)
- ✅ Web UI (Streamlit)
- ✅ Compliance systems (audit trails)

## Next Steps

1. **Review** `banking_rules.yaml` to familiarize yourself with structure
2. **Test** by running the application with sample applications
3. **Customize** rules to match your institution's policies
4. **Document** any customizations in comments
5. **Export** to PDF for official policy documentation

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review `BANKING_RULES_GUIDE.md` for detailed policy information
3. Examine `BankingRulesLoader.py` for function documentation
4. Check application logs: `credit_decision.log`

---

**Last Updated**: March 29, 2026  
**Version**: 1.0 (YAML Configuration)  
**Status**: Ready for Production
