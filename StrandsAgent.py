import os
import boto3
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator
from StrandsCutomTools import weather


region = boto3.session.Session().region_name

NOVA_PRO_MODEL_ID = "us.amazon.nova-pro-v1:0"
if region.startswith("eu"):
    NOVA_PRO_MODEL_ID = "eu.amazon.nova-pro-v1:0"
elif region.startswith("ap"):
    NOVA_PRO_MODEL_ID = "apac.amazon.nova-pro-v1:0"

print(f"Nova Pro Model ID: {NOVA_PRO_MODEL_ID}")



# Create your first agent
agent = Agent(
    model=BedrockModel(model_id=NOVA_PRO_MODEL_ID),
    system_prompt="You are a helpful assistant that provides concise responses.",
    tools=[weather, calculator],
)

agent("How is the weather in HK? Return temperature in Fahrenheit")