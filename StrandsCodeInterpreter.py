from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
import boto3
import json
from bedrock_agentcore._utils import endpoints
from botocore.exceptions import ClientError
from StrandsCutomTools import apiKey_For_OpenWeathermap
from StarndsDBTools import list_employees

# determine region and Nova model id
region = boto3.session.Session().region_name

NOVA_PRO_MODEL_ID = "us.amazon.nova-pro-v1:0"
if region.startswith("eu"):
    NOVA_PRO_MODEL_ID = "eu.amazon.nova-pro-v1:0"
elif region.startswith("ap"):
    NOVA_PRO_MODEL_ID = "apac.amazon.nova-pro-v1:0"


data_plane_endpoint = endpoints.get_data_plane_endpoint(region)
control_plane_endpoint = endpoints.get_control_plane_endpoint(region)

cp_client = boto3.client("bedrock-agentcore-control", 
                        region_name=region,
                        endpoint_url=control_plane_endpoint)

dp_client = boto3.client("bedrock-agentcore", 
                        region_name=region,
                        endpoint_url=data_plane_endpoint)

interpreter_name = "SampleCodeInterpreter"

# Create code interpreter
try:
    interpreter_response = cp_client.create_code_interpreter(
        name=interpreter_name,
        description="Environment for Code Interpreter sample test",
        #executionRoleArn=iam_role_arn, #Required only if the code interpreter need to access AWS resources
        networkConfiguration={
            'networkMode': 'PUBLIC'
        }
    )
    interpreter_id = interpreter_response["codeInterpreterId"]
    print(f"Created interpreter: {interpreter_id}")
except ClientError as e:
    print(f"ERROR: {e}")
    if "already exists" in str(e):
        # If code interpreter already exists, retrieve its ID
        for items in cp_client.list_code_interpreters()['codeInterpreterSummaries']:
            if items['name'] == interpreter_name:
                interpreter_id = items['codeInterpreterId']
                print(f"Code Interpreter ID: {interpreter_id}")
                break
except Exception as e:
    # Show any errors during code interpreter creation
    print(f"ERROR: {e}")

session_name = "SampleCodeInterpreterSession"

# Create code interpreter session
session_response = dp_client.start_code_interpreter_session(
    codeInterpreterIdentifier=interpreter_id,
    name=session_name,
    sessionTimeoutSeconds=900
)
session_id = session_response["sessionId"]
print(f"Created session: {session_id}")

#Reuse the Core Interpreter and Session created above
ci_client = CodeInterpreter(region=boto3.session.Session().region_name)
ci_client.start(identifier=interpreter_id) #initializes a new code interpreter session

@tool
def execute_python(code: str, description: str = "") -> str:
    """Execute Python code in the sandbox."""
    
    print(f"\n Generated Code: {code}")
    response = ci_client.invoke("executeCode", {
        "code": code,
        "language": "python",
        "clearContext": False
    })
        
    for event in response["stream"]:
        return json.dumps(event["result"])

@tool
def execute_command(command: str, description: str = "") -> str:
    """Execute command in the sandbox."""
    
    print(f"\n Generated Command: {command}")
    response = ci_client.invoke("executeCommand", {
        "command": command
    })
    
    for event in response["stream"]:
        return json.dumps(event["result"])
    


# Create a code gen agent
agent = Agent(
    model=BedrockModel(model_id=NOVA_PRO_MODEL_ID),
    system_prompt="""You are a helpful AI assistant that validates all answers through code execution.
                  If you has no available tools to perform the task, you must generate and execute code to continue. 
                  If required, execute pip install to download required packages.
                  """,
    tools=[execute_python, execute_command, apiKey_For_OpenWeathermap , list_employees],
)

agent("can you get employee details  for 'Michael Brown'?")

ci_client.stop() #stop the current code interpreter session