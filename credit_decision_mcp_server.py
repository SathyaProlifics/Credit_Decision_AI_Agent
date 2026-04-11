"""MCP Server for Credit Decision Database Operations.

Exposes credit application CRUD operations as MCP tools that any
MCP-compatible client (VS Code Copilot, Claude Desktop, Strands agents, etc.)
can discover and call.

Reuses the same DB connection logic (Lambda API → direct PyMySQL → AWS Secrets Manager)
as CreditDecisionStrandsDBTools.py so there is no credential duplication.

Usage:
    # stdio transport (VS Code, Claude Desktop)
    python credit_decision_mcp_server.py

    # SSE transport (remote / multi-client)
    python credit_decision_mcp_server.py --transport sse --port 8080
"""

import json
import logging
import os
import time
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

# ---------- logging ----------
logger = logging.getLogger("credit_decision_mcp")
logger.setLevel(logging.DEBUG)

# ---------- DB helpers (reused from existing codebase) ----------
# We import the private helpers and public tool *functions* from the existing
# module.  The @tool decorator in Strands wraps them but they are still callable.
try:
    import pymysql
except ImportError:
    pymysql = None

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

# Try Lambda client
try:
    from LambdaAPIClient import LambdaAPIClient
    LAMBDA_CLIENT_AVAILABLE = True
except ImportError:
    LAMBDA_CLIENT_AVAILABLE = False

DEFAULT_HOST = "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com"
AWS_SECRET_NAME = "rds!db-96bdf2a6-c157-4fca-b8e7-412b79d52086"

# --- Caches ---
_lambda_client = None
_aws_secrets_cache = None
_aws_secrets_failed = False
_resource_props_cache = None
_db_config_cache = None


def _get_lambda_client():
    global _lambda_client
    if not LAMBDA_CLIENT_AVAILABLE:
        return None
    if _lambda_client is None:
        try:
            _lambda_client = LambdaAPIClient()
        except Exception as e:
            logger.warning(f"Lambda client init failed: {e}")
            _lambda_client = False
    return _lambda_client if _lambda_client is not False else None


def _get_aws_secrets():
    global _aws_secrets_cache, _aws_secrets_failed
    if _aws_secrets_failed:
        return {}
    if _aws_secrets_cache is not None:
        return _aws_secrets_cache
    if not boto3:
        _aws_secrets_failed = True
        return {}
    try:
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=AWS_SECRET_NAME)
        if "SecretString" in response:
            secret = json.loads(response["SecretString"])
            _aws_secrets_cache = {"username": secret.get("username"), "password": secret.get("password")}
            return _aws_secrets_cache
    except Exception as e:
        logger.warning(f"AWS Secrets Manager fetch failed: {e}")
    _aws_secrets_failed = True
    return {}


def _load_resource_properties():
    global _resource_props_cache
    if _resource_props_cache is not None:
        return _resource_props_cache
    props_path = os.path.join(os.path.dirname(__file__), "resource", "properties")
    result = {}
    try:
        if os.path.exists(props_path):
            with open(props_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        result[k.strip()] = v.strip()
    except Exception as e:
        logger.warning(f"Failed to read {props_path}: {e}")
    _resource_props_cache = result
    return result


def _get_db_conn():
    if pymysql is None:
        raise RuntimeError("PyMySQL is not installed")
    global _db_config_cache
    if _db_config_cache is None:
        aws_creds = _get_aws_secrets()
        props = _load_resource_properties()
        user = aws_creds.get("username") or props.get("DB_USER") or os.getenv("DB_USER")
        password = aws_creds.get("password") or props.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
        host = props.get("DB_HOST") or os.getenv("DB_HOST") or DEFAULT_HOST
        db = props.get("DB_NAME") or os.getenv("DB_NAME") or "dev"
        try:
            port = int(props.get("DB_PORT") or os.getenv("DB_PORT") or "3306")
        except ValueError:
            port = 3306
        if not user or not password:
            raise RuntimeError("Database credentials not set (DB_USER / DB_PASSWORD)")
        _db_config_cache = {"host": host, "user": user, "password": password, "db": db, "port": port}

    cfg = _db_config_cache
    return pymysql.connect(
        host=cfg["host"], user=cfg["user"], password=cfg["password"],
        database=cfg["db"], port=cfg["port"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def _rows_to_json(rows):
    def _clean(val):
        try:
            json.dumps(val)
            return val
        except Exception:
            return str(val)
    return json.dumps([{k: _clean(v) for k, v in r.items()} for r in rows], indent=2, default=str)


# ==================== MCP Server ====================
mcp = FastMCP(
    name="CreditDecisionDB",
    instructions="MCP server for credit decision database operations. "
    "Provides tools to insert, query, and update credit applications in the MySQL database.",
)


@mcp.tool()
def get_application(application_id: int) -> str:
    """Return a single credit application by its ID as JSON.

    Args:
        application_id: The numeric ID of the application to retrieve.
    """
    logger.info(f"get_application: id={application_id}")
    lc = _get_lambda_client()
    if lc:
        try:
            return lc.get_application(application_id)
        except Exception as e:
            logger.warning(f"Lambda fallback: {e}")

    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM credit_applications WHERE id=%s LIMIT 1", (application_id,))
            row = cur.fetchone()
            if not row:
                return json.dumps({"error": "not_found", "application_id": application_id})
            return json.dumps(row, default=str, indent=2)
    finally:
        conn.close()


@mcp.tool()
def list_applications(limit: int = 10) -> str:
    """Return the most recent credit applications, ordered newest first.

    Args:
        limit: Maximum number of applications to return (default 10).
    """
    logger.info(f"list_applications: limit={limit}")
    lc = _get_lambda_client()
    if lc:
        try:
            return lc.list_applications(limit)
        except Exception as e:
            logger.warning(f"Lambda fallback: {e}")

    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM credit_applications ORDER BY id DESC LIMIT %s", (limit,))
            return _rows_to_json(cur.fetchall())
    finally:
        conn.close()


@mcp.tool()
def insert_application(
    applicant_name: str,
    age: int | None = None,
    email: str | None = None,
    income: float | None = None,
    employment_status: str | None = None,
    credit_score: int | None = None,
    dti_ratio: float | None = None,
    existing_debts: float | None = None,
    requested_credit: float | None = None,
    source: str | None = None,
    application_status: str = "PENDING",
) -> str:
    """Insert a new credit application into the database.

    Args:
        applicant_name: Full name of the applicant.
        age: Applicant's age in years.
        email: Applicant's email address.
        income: Annual income in dollars.
        employment_status: e.g. 'employed', 'self-employed', 'unemployed'.
        credit_score: FICO score (300-850).
        dti_ratio: Debt-to-income ratio as a decimal (e.g. 0.35).
        existing_debts: Total existing debts in dollars.
        requested_credit: Amount of credit requested in dollars.
        source: Application source ('web', 'api', etc.).
        application_status: Initial status (default 'PENDING').
    """
    app = {
        "applicant_name": applicant_name,
        "age": age,
        "email": email,
        "income": income,
        "employment_status": employment_status,
        "credit_score": credit_score,
        "dti_ratio": dti_ratio,
        "existing_debts": existing_debts,
        "requested_credit": requested_credit,
        "source": source,
        "application_status": application_status,
    }
    # Remove None values
    app = {k: v for k, v in app.items() if v is not None}
    logger.info(f"insert_application: keys={list(app.keys())}")

    lc = _get_lambda_client()
    if lc:
        try:
            return lc.insert_application(app)
        except Exception as e:
            logger.warning(f"Lambda fallback: {e}")

    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            fields = list(app.keys())
            placeholders = ["%s"] * len(fields)
            values = list(app.values())
            sql = f"INSERT INTO credit_applications ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cur.execute(sql, tuple(values))
            conn.commit()
            return json.dumps({"inserted_id": cur.lastrowid})
    finally:
        conn.close()


@mcp.tool()
def update_application_status(
    application_id: int,
    status: str,
    reason: str | None = None,
    confidence: float | None = None,
) -> str:
    """Update the status, reason, and confidence score for a credit application.

    Args:
        application_id: The application ID to update.
        status: New status (PENDING, PROCESSING, APPROVED, DENIED, REFER, ERROR).
        reason: Human-readable reason for the decision.
        confidence: Confidence score 0-100.
    """
    logger.info(f"update_application_status: id={application_id} status={status}")
    lc = _get_lambda_client()
    if lc:
        try:
            return lc.update_application_status(application_id, status, reason, confidence)
        except Exception as e:
            logger.warning(f"Lambda fallback: {e}")

    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            parts = ["application_status=%s"]
            values: list[Any] = [status]
            if reason is not None:
                parts.append("reason=%s")
                values.append(reason)
            if confidence is not None:
                parts.append("confidence=%s")
                values.append(confidence)
            values.append(application_id)
            sql = f"UPDATE credit_applications SET {', '.join(parts)} WHERE id=%s"
            cur.execute(sql, tuple(values))
            conn.commit()
            return json.dumps({"updated_rows": cur.rowcount})
    finally:
        conn.close()


@mcp.tool()
def find_latest_by_applicant(applicant_name: str) -> str:
    """Find the most recent credit application for a given applicant name (case-insensitive).

    Args:
        applicant_name: The applicant's name to search for.
    """
    logger.info(f"find_latest_by_applicant: name='{applicant_name}'")
    lc = _get_lambda_client()
    if lc:
        try:
            return lc.find_latest_by_applicant(applicant_name)
        except Exception as e:
            logger.warning(f"Lambda fallback: {e}")

    search_name = applicant_name.strip()
    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM credit_applications WHERE LOWER(applicant_name)=LOWER(%s) ORDER BY created_at DESC LIMIT 1",
                (search_name,),
            )
            row = cur.fetchone()
            if not row:
                return json.dumps({"error": "not_found", "applicant_name": search_name})
            return json.dumps(row, default=str, indent=2)
    finally:
        conn.close()


@mcp.tool()
def update_application_agent_output(application_id: int, agent_output: str) -> str:
    """Update the agent_output JSON column for a credit application.

    Use this to store the full AI agent pipeline output after processing.

    Args:
        application_id: The application ID to update.
        agent_output: JSON string containing the agent analysis output.
    """
    logger.info(f"update_application_agent_output: id={application_id}")

    # Parse to validate it's valid JSON, then re-serialize
    try:
        parsed = json.loads(agent_output) if isinstance(agent_output, str) else agent_output
        payload = json.dumps(parsed)
    except (json.JSONDecodeError, TypeError):
        payload = json.dumps({"raw_output": str(agent_output)})

    lc = _get_lambda_client()
    if lc:
        try:
            return lc.update_application_agent_output(application_id, parsed)
        except Exception as e:
            logger.warning(f"Lambda fallback: {e}")

    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE credit_applications SET agent_output=%s WHERE id=%s",
                (payload, application_id),
            )
            conn.commit()
            return json.dumps({"updated_rows": cur.rowcount})
    finally:
        conn.close()


# ==================== Entry point ====================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Credit Decision DB MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio",
                        help="MCP transport to use (default: stdio)")
    parser.add_argument("--port", type=int, default=8080, help="Port for SSE/HTTP transport (default: 8080)")
    args = parser.parse_args()

    mcp.settings.port = args.port
    mcp.run(transport=args.transport)
