# LLM Provider Configuration Guide

## Overview

The Credit Decision Agent now supports **multiple LLM providers**, allowing you to easily switch between models and providers without code changes. This guide explains how to configure and extend the system.

## Supported Providers

### 1. **AWS Bedrock** (Default)
- Models: Claude 3 (Haiku, Sonnet, Opus), Llama 2/3, Mistral
- **Best for**: Production AWS environments
- **Configuration**: Requires AWS credentials (`~/.aws/credentials`)

### 2. **OpenAI** 
- Models: GPT-4, GPT-4-Turbo, GPT-3.5-Turbo
- **Best for**: High-capability reasoning, cost-effective inference
- **Configuration**: Requires `OPENAI_API_KEY`

### 3. **Azure OpenAI**
- Models: Any OpenAI model deployed in Azure
- **Best for**: Enterprise environments using Azure
- **Configuration**: Requires `AZURE_OPENAI_KEY` and `AZURE_OPENAI_ENDPOINT`

## Quick Start

### Current Configuration (Default)
By default, all agents use AWS Bedrock with Claude models:

```
# In .env (already configured)
LLM_DATA_COLLECTOR_PROVIDER=bedrock
LLM_DATA_COLLECTOR_MODEL=anthropic.claude-3-haiku-20240307-v1:0
LLM_RISK_ASSESSOR_PROVIDER=bedrock
LLM_RISK_ASSESSOR_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
LLM_DECISION_MAKER_PROVIDER=bedrock
LLM_DECISION_MAKER_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
LLM_AUDITOR_PROVIDER=bedrock
LLM_AUDITOR_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
```

### Switch to OpenAI (Example)

**Step 1: Install OpenAI SDK**
```bash
pip install openai
```

**Step 2: Set OpenAI API Key**
```bash
# In .env
OPENAI_API_KEY=sk-your-api-key-here
```

**Step 3: Update Agent Configurations**
```bash
# In .env - Switch all agents to GPT-4
LLM_DATA_COLLECTOR_PROVIDER=openai
LLM_DATA_COLLECTOR_MODEL=gpt-3.5-turbo  # Fast model for data validation

LLM_RISK_ASSESSOR_PROVIDER=openai
LLM_RISK_ASSESSOR_MODEL=gpt-4-turbo     # Capable model for risk analysis

LLM_DECISION_MAKER_PROVIDER=openai
LLM_DECISION_MAKER_MODEL=gpt-4          # Top model for critical decisions

LLM_AUDITOR_PROVIDER=openai
LLM_AUDITOR_MODEL=gpt-4                 # Top model for compliance audit
```

### Mix Providers (Advanced)

You can use different providers for different agents:

```bash
# Data validation with fast, cheap model
LLM_DATA_COLLECTOR_PROVIDER=openai
LLM_DATA_COLLECTOR_MODEL=gpt-3.5-turbo

# Risk assessment with specialized model
LLM_RISK_ASSESSOR_PROVIDER=bedrock
LLM_RISK_ASSESSOR_MODEL=anthropic.claude-3-sonnet-20240229-v1:0

# Critical decisions with best model
LLM_DECISION_MAKER_PROVIDER=bedrock
LLM_DECISION_MAKER_MODEL=anthropic.claude-3-opus-20240229-v1:0

# Compliance audit
LLM_AUDITOR_PROVIDER=azure_openai
LLM_AUDITOR_MODEL=gpt-4-deployment-name
```

## Environment Variables Reference

### Common Across All Agents
```bash
AWS_REGION=us-east-1                    # For Bedrock
OPENAI_API_KEY=sk-...                   # For OpenAI
AZURE_OPENAI_KEY=...                    # For Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://...       # For Azure OpenAI
```

### Per-Agent Configuration Format
For each agent (DATA_COLLECTOR, RISK_ASSESSOR, DECISION_MAKER, AUDITOR):

```bash
LLM_{AGENT_NAME}_PROVIDER={provider}       # bedrock, openai, or azure_openai
LLM_{AGENT_NAME}_MODEL={model_id}          # Provider-specific model ID
LLM_{AGENT_NAME}_MAX_TOKENS={int}          # Default: 1000-2000
LLM_{AGENT_NAME}_TEMPERATURE={float}       # Default: 0.2-0.3
```

## Model IDs by Provider

### AWS Bedrock
```
# Claude 3 Family (Recommended)
anthropic.claude-3-opus-20240229-v1:0     # Most capable
anthropic.claude-3-sonnet-20240229-v1:0   # Balanced
anthropic.claude-3-haiku-20240307-v1:0    # Fast, cheap

# Other providers
meta.llama2-70b-chat-v1
mistral.mistral-7b-instruct-v0:2
```

### OpenAI
```
gpt-4                    # Most capable, slowest
gpt-4-turbo              # Fast, capable
gpt-3.5-turbo            # Fast, cheap (good for data validation)
```

### Azure OpenAI
Use the **deployment name** you created in Azure:
```
gpt-4-deployment
gpt-4-turbo-deployment
gpt-35-turbo-deployment
```

## Architecture

```
┌─────────────────────────────────────┐
│   Credit Decision Agents            │
│  (DataCollector, RiskAssessor, etc.)│
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   ModelConfigManager                │
│  (Reads from .env)                  │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   LLMFactory                        │
│  (Creates provider instances)       │
└────────────┬────────────────────────┘
             │
      ┌──────┴──────┬──────────┬──────────┐
      ▼             ▼          ▼          ▼
  BedrockProvider OpenAIProvider AzureOpenAIProvider ...
```

## Cost Optimization Tips

1. **Use Cheaper Models for Simple Tasks**
   - Data validation: Use GPT-3.5-Turbo or Claude 3 Haiku
   - Cost savings: ~10x cheaper than GPT-4

2. **Tiered Model Strategy**
   ```
   DataCollector: gpt-3.5-turbo (fast, cheap)
   RiskAssessor: gpt-4-turbo (balanced)
   DecisionMaker: gpt-4 (high stakes)
   Auditor: gpt-4 (compliance critical)
   ```

3. **Batch Processing**
   - Process multiple applications during off-peak hours

4. **Token Limits**
   - Adjust `MAX_TOKENS` per agent to reduce costs
   - Default settings already optimized

## Extending the System

### Add a New Provider (e.g., Google Gemini)

**Step 1: Create Provider Class in `LLMProvider.py`**
```python
class GeminiProvider(LLMProvider):
    """Google Gemini LLM Provider"""
    
    def __init__(self):
        self.provider_name = "gemini"
        self.api_key = os.getenv("GOOGLE_API_KEY")
    
    def invoke(self, prompt: str, config: ModelConfig) -> Dict[str, Any]:
        """Implement Gemini API calls"""
        # Implementation here
        pass
```

**Step 2: Register Provider**
```python
# In LLMProvider.py, update LLMFactory
LLMFactory.register_provider("gemini", GeminiProvider)
```

**Step 3: Use in Configuration**
```bash
# In .env
LLM_DATA_COLLECTOR_PROVIDER=gemini
LLM_DATA_COLLECTOR_MODEL=gemini-ultra
```

## Monitoring & Logging

The system logs all LLM invocations:

```python
# Check logs for:
# - Provider used
# - Model invoked
# - Response time
# - Estimated cost
# - Error details

# Example log output:
# INFO:llm_provider:RiskAssessor AGENT: Starting invocation with bedrock/claude-3-sonnet
# INFO:llm_provider:RiskAssessor AGENT: Successfully parsed JSON (total time=2.14s)
```

## Troubleshooting

### "OpenAI API key not configured"
**Solution**: Set `OPENAI_API_KEY` in .env
```bash
OPENAI_API_KEY=sk-your-key-here
```

### "openai package not installed"
**Solution**: Install the package
```bash
pip install openai
```

### "Unknown provider: custom_provider"
**Solution**: Register the provider first
```python
LLMFactory.register_provider("custom_provider", CustomProvider)
```

### Response takes too long
**Solution**: 
- Use a faster model
- Reduce `MAX_TOKENS`
- Check provider API status
- Enable parallel processing

## Performance Benchmarks

| Model | Speed | Quality | Cost |
|-------|-------|---------|------|
| Claude 3 Haiku | Very Fast | Good | $0.0003-$0.0012 |
| GPT-3.5-Turbo | Very Fast | Good | $0.0015-$0.002 |
| Claude 3 Sonnet | Fast | Excellent | $0.003-$0.015 |
| GPT-4-Turbo | Fast | Excellent | $0.01-$0.03 |
| GPT-4 | Moderate | Best | $0.03-$0.06 |
| Claude 3 Opus | Moderate | Best | $0.015-$0.075 |

## Best Practices

1. **Use Model Versioning**
   - Always specify full model version (e.g., `-v1:0`)
   - Avoid using `-latest` aliases

2. **Set Appropriate Temperatures**
   - Data collection (0.1-0.3): Lower for consistency
   - Decision making (0.1-0.2): Lower for reliability
   - Brainstorming (0.7-0.9): Higher for creativity

3. **Monitor Costs**
   - Review estimated costs in logs
   - Set provider usage limits

4. **Backup Models**
   - Keep Bedrock as fallback if using other providers
   - Implement retry logic (already in LLMProvider)

## Support

For issues or to add new provider support:
1. Check `LLMProvider.py` for existing implementations
2. Review logs in `credit_decision.log`
3. Test new configurations on small datasets first
