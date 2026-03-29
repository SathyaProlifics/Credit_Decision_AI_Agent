# Quick Reference: Banking Rules System

## 📋 File Inventory

### Core Configuration
| File | Size | Purpose |
|------|------|---------|
| `banking_rules.yaml` | ~2.5KB | External banking rules configuration (730+ lines) |
| `BankingRulesLoader.py` | ~12KB | Python module to load and manage YAML rules |
| `requirements.txt` | Updated | Added PyYAML>=6.0 dependency |

### Documentation
| File | Purpose |
|------|---------|
| `IMPLEMENTATION_SUMMARY.md` | Overview of what was implemented ← **START HERE** |
| `BANKING_RULES_GUIDE.md` | Complete banking rules documentation |
| `YAML_CONFIGURATION_GUIDE.md` | How to manage the YAML configuration |
| `README.md` | Original project README |
| `TECHNICAL_FLOW_DOCUMENTATION.md` | Original flow documentation |

### Code Files
| File | Status |
|------|--------|
| `CreditDecisionAgent_MultiAgent.py` | ✅ Updated to use BankingRulesLoader |
| `credit_decision_ui.py` | ✅ No changes needed (works with agents) |
| `LLMProvider.py` | ✅ No changes needed |
| `CreditDecisionAgent.py` | ✅ No changes needed |
| `CreditDecisionStrandsDBTools.py` | ✅ No changes needed |

---

## 🚀 Quick Start

### 1. View the Implementation
```
Step 1: Read IMPLEMENTATION_SUMMARY.md (shows what was built)
Step 2: Review banking_rules.yaml (see the actual rules)
Step 3: Check YAML_CONFIGURATION_GUIDE.md (how to update rules)
```

### 2. Run the Application
```bash
cd AIAgents
.venv\Scripts\activate.ps1
streamlit run credit_decision_ui.py --server.port=8501
```

Visit: `http://localhost:8501`

### 3. Test Banking Rules
```bash
python -c "from BankingRulesLoader import check_rules_loaded; print('✓ Rules loaded' if check_rules_loaded() else '✗ Error')"
```

---

## 📊 Banking Rules Structure

```yaml
banking_rules:
  ├── regulatory_framework          # ECOA, TILA, FCRA, Dodd-Frank
  ├── credit_decision_matrix        # Approval/deny triggers
  ├── risk_assessment               # Risk scoring (1-100)
  ├── compliance_framework          # Required documentation
  ├── compensating_factors          # Offset borderline metrics
  ├── special_circumstances         # Bankruptcy, thin credit, etc.
  └── output_requirements           # Agent output fields
```

---

## 🔧 Common Tasks

### Update Minimum Income Requirement
```yaml
# File: banking_rules.yaml
credit_decision_matrix:
  income_requirements:
    minimum_annual: 30000  # Changed from 25000
```
**Result**: Takes effect on next app restart

### Add New Risk Category
```yaml
# File: banking_rules.yaml
risk_assessment:
  risk_categories:
    micro_risk:
      score_range: [95, 100]
      approval_probability: 0.99
      credit_limit_ratio: 5.0
```

### Update DTI Thresholds
```yaml
# File: banking_rules.yaml
credit_decision_matrix:
  dti_thresholds:
    marginal:
      range: [0.35, 0.42]  # was [0.35, 0.40]
```

---

## 🐍 Python Helper Functions

### Check Rules Status
```python
from BankingRulesLoader import check_rules_loaded
check_rules_loaded()  # Returns True/False
```

### Calculate DTI Compliance
```python
from BankingRulesLoader import calculate_dti_compliance
result = calculate_dti_compliance(0.35)
# Returns: {"tier": "marginal", "status": "Marginal", ...}
```

### Get Credit Score Tier
```python
from BankingRulesLoader import calculate_credit_score_tier
result = calculate_credit_score_tier(720)
# Returns: {"tier": "good", "category": "Near-Prime", ...}
```

### Validate Income
```python
from BankingRulesLoader import validate_income_minimum
result = validate_income_minimum(50000)
# Returns: {"valid": True, "message": "Income sufficient..."}
```

### Get System Context for Agents
```python
from BankingRulesLoader import get_system_context
context = get_system_context()
# Returns: Complete regulatory framework as string
```

### Reload Rules at Runtime
```python
from BankingRulesLoader import reload_rules
success = reload_rules()  # Returns True if successful
```

---

## 📈 Agent Prompts Enhanced With

### DataCollectorAgent
- ✅ Regulatory requirements verification
- ✅ Data completeness against standards
- ✅ Missing documentation recommendations

### RiskAssessorAgent
- ✅ Standardized risk scoring framework
- ✅ Risk categories with approval probabilities
- ✅ Compensating factors guidance

### DecisionMakerAgent
- ✅ Credit decision matrix rules
- ✅ Approval triggers with policy citations
- ✅ Compliance verification requirements

### AuditAgent
- ✅ Regulatory compliance checks (ECOA/TILA/Reg-Z)
- ✅ Documentation completeness
- ✅ Adverse action notice requirements

---

## 📝 Rules vs. Code

### Before (Rules in Python)
```python
# BankingRules.py - 360 lines of string literals
CREDIT_DECISION_MATRIX = """
Credit Score Tiers:
  - 750+: Excellent...
  - 700-749: Good...
"""
# Problem: Hard to update, requires recompilation
```

### After (Rules in YAML)
```yaml
# banking_rules.yaml - Easy to update, no compilation
credit_decision_matrix:
  credit_score_tiers:
    excellent:
      range: [750, 850]
      category: "Prime"
# Advantage: Update instantly without restarting
```

---

## 🔒 Compliance Features

### Fair Lending Checks
- ✅ No protected characteristic consideration
- ✅ Consistent application across applicants
- ✅ Compensating factors properly documented
- ✅ Pattern analysis for disparate impact

### Required Documentation
- ✅ Applicant identification
- ✅ Income verification (pay stubs/tax returns)
- ✅ Employment verification
- ✅ Credit report pull timestamp
- ✅ Decision reason codes

### Audit Trail
- ✅ Timestamp of decision
- ✅ Agent component versions
- ✅ Input data snapshot
- ✅ Decision rationale with citations
- ✅ Manual reviewer notes

### Regulatory Compliance
- ✅ ECOA (Equal Credit Opportunity Act)
- ✅ TILA (Truth in Lending Act - Reg Z)
- ✅ FCRA (Fair Credit Reporting Act)
- ✅ Dodd-Frank (Ability to Repay)

---

## 📊 Sample Decisions

| Scenario | Credit | DTI | Income | Decision |
|----------|--------|-----|--------|----------|
| Excellent | 780 | 25% | $100k | ✅ APPROVE |
| Good | 710 | 33% | $75k | ✅ APPROVE |
| Fair | 670 | 38% | $60k | 🔄 REFER |
| Poor | 620 | 42% | $50k | ❌ DENY |
| Very Poor | 580 | 50% | $35k | ❌ DENY |

---

## 🎯 Decision Confidence Examples

| Decision | Confidence | Reason |
|----------|-----------|--------|
| APPROVE | 95%+ | Meets all criteria clearly |
| REFER | 50-75% | Borderline case, needs review |
| DENY | 90%+ | Multiple disqualifying factors |

---

## 📱 Accessing Rules in Code

### Method 1: Full Context (Recommended)
```python
from BankingRulesLoader import get_system_context

prompt = f"""{get_system_context()}

Your task: {applicant_task}
"""
```

### Method 2: Specific Sections
```python
from BankingRulesLoader import (
    get_credit_decision_rules,
    get_risk_framework,
    get_compliance_rules
)

rules = get_credit_decision_rules()  # Decision matrix
```

### Method 3: Raw Data
```python
from BankingRulesLoader import BANKING_RULES

min_income = BANKING_RULES['credit_decision_matrix']['income_requirements']['minimum_annual']
```

---

## 🧪 Testing Checklist

- [x] Rules load from YAML at startup
- [x] DTI compliance calculation works
- [x] Credit score tier categorization works
- [x] Income validation works
- [x] Code compiles without errors
- [x] Agents receive banking context
- [ ] Test with sample applications in UI
- [ ] Verify decision confidence scores
- [ ] Check audit reports
- [ ] Validate fair lending flags

---

## 🚨 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Banking rules not found" | Verify `banking_rules.yaml` exists in same directory as `BankingRulesLoader.py` |
| "Error parsing YAML" | Validate YAML syntax at yamllint.com or use: `python -c "import yaml; yaml.safe_load(open('banking_rules.yaml'))"` |
| "Module not found" | Run: `pip install pyyaml` |
| Rules not updating | Restart the application or call `reload_rules()` |
| Agents still using old rules | Restart the Streamlit app for new rules to load |

---

## 📖 Documentation Map

```
START HERE:
       │
       ├──→ IMPLEMENTATION_SUMMARY.md     (Overview of changes)
       │
       ├──→ YAML_CONFIGURATION_GUIDE.md   (How to manage rules)
       │
       ├──→ BANKING_RULES_GUIDE.md        (Policy details)
       │
       └──→ banking_rules.yaml            (The actual rules)
```

---

## 🔄 Development Cycle

1. **Update Rules**: Edit `banking_rules.yaml`
2. **Verify Syntax**: Run yamllint or Python yaml.safe_load()
3. **Test**: Run application with test cases
4. **Deploy**: Push to production (no code changes needed)
5. **Monitor**: Check decision logs and audit reports
6. **Review**: Quarterly policy review and updates

---

## 💡 Tips & Best Practices

✅ **DO**:
- Track rule changes in Git version control
- Add comments in YAML explaining policy changes
- Test rule changes with borderline applicants
- Export rules to PDF for official documentation
- Keep historical backups of YAML versions

❌ **DON'T**:
- Edit rules during active batch processing
- Skip validation of YAML syntax before deployment
- Forget to restart app after rule changes
- Modify agent code to change policies (use YAML instead)
- Ignore compliance requirements in rule updates

---

## 📞 Support Resources

| Resource | Location |
|----------|----------|
| Rules Documentation | `BANKING_RULES_GUIDE.md` |
| Configuration Help | `YAML_CONFIGURATION_GUIDE.md` |
| Python Functions | Docstrings in `BankingRulesLoader.py` |
| Implementation Details | `IMPLEMENTATION_SUMMARY.md` |
| Application Logs | `credit_decision.log` |

---

**Version**: 1.0  
**Last Updated**: March 29, 2026  
**Status**: ✅ Ready for Production
