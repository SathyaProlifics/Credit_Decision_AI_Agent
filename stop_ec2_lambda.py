import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """AWS Lambda handler to stop one or more EC2 instances.

    Behavior:
    - If the invocation `event` contains `instance_id` (string) or `instance_ids` (list), use that.
    - Otherwise read the environment variable `TARGET_INSTANCE_ID` (comma-separated allowed).
    - Calls EC2 StopInstances API and returns the API response.
    """
    # Resolve instance IDs from event or env
    instance_ids = []

    if isinstance(event, dict):
        if "instance_ids" in event and isinstance(event["instance_ids"], (list, tuple)):
            instance_ids = list(event["instance_ids"])
        elif "instance_id" in event and isinstance(event["instance_id"], str):
            instance_ids = [event["instance_id"]]

    if not instance_ids:
        env_val = os.environ.get("TARGET_INSTANCE_ID", "")
        if env_val:
            instance_ids = [i.strip() for i in env_val.split(",") if i.strip()]

    if not instance_ids:
        logger.warning("No EC2 instance id provided via event or TARGET_INSTANCE_ID env var. Nothing to stop.")
        return {"stopped": [], "message": "no_instance_ids"}

    ec2 = boto3.client("ec2")
    try:
        logger.info("Stopping EC2 instances: %s", instance_ids)
        resp = ec2.stop_instances(InstanceIds=instance_ids)
        logger.info("StopInstances response: %s", resp)
        return {"stopped": instance_ids, "response": resp}
    except ClientError as e:
        logger.exception("Failed to stop EC2 instances: %s", e)
        raise
