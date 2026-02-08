"""Database tools for the Credit Decision UI (Strands tools).

Provides `@tool` wrappers that the Strands agent or UI can call to persist
and query credit application data.

Environment variables used:
- DB_HOST (optional)
- DB_USER (required)
- DB_PASSWORD (required)
- DB_NAME (optional, defaults to "dev")
- DB_PORT (optional, defaults to 3306)

Ensure `PyMySQL` is installed in the project's environment.
"""

from strands import tool
import os
import json
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger("credit_decision_db")

try:
    import pymysql
except Exception as e:
    logger.error(f"Failed to import pymysql: {e}")
    pymysql = None

# Default host used previously in this workspace
DEFAULT_HOST = "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com"


def _get_db_conn():
    if pymysql is None:
        logger.error("PyMySQL is not installed in the environment")
        raise RuntimeError("PyMySQL is not installed in the environment")

    host = os.getenv("DB_HOST", DEFAULT_HOST)
    user = os.getenv("DB_USER")
    password = "gAwcZC_[zNd[:1qTsV|HTTvFP>W2"
    db = os.getenv("DB_NAME", "dev")
    port = int(os.getenv("DB_PORT", "3306"))

    logger.debug(f"Attempting DB connection: host={host}, user={user}, db={db}, port={port}")

    if not user or not password:
        logger.error("Database credentials not set: DB_USER or DB_PASSWORD missing")
        raise RuntimeError("Database credentials not set. Please set DB_USER and DB_PASSWORD environment variables.")

    try:
        conn = pymysql.connect(host=host, user=user, password=password, database=db, port=port, cursorclass=pymysql.cursors.DictCursor)
        logger.debug(f"Successfully connected to database {db} at {host}:{port}")
        return conn
    except pymysql.MySQLError as e:
        logger.error(f"MySQL connection error: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected connection error: {e}", exc_info=True)
        raise


def _rows_to_json(rows: List[Dict[str, Any]]) -> str:
    def _clean(val):
        try:
            json.dumps(val)
            return val
        except Exception:
            return str(val)

    cleaned = []
    for r in rows:
        cleaned.append({k: _clean(v) for k, v in r.items()})
    return json.dumps(cleaned, indent=2, default=str)


@tool
def insert_application(app: Dict[str, Any]) -> str:
    """Insert a credit application record.

    Expects a dict with keys matching the credit_applications table (e.g.:
    applicant_name, applicant_dob, age, income, employment_status, credit_score,
    dti_ratio, existing_debts, requested_credit, source, agent_output)

    Returns JSON with inserted id or error.
    """
    logger.info(f"insert_application called with keys: {list(app.keys())}")
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"Failed to get DB connection in insert_application: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            fields = []
            placeholders = []
            values = []
            for k, v in app.items():
                # skip null/None values to let defaults apply
                if v is None:
                    logger.debug(f"Skipping None value for field: {k}")
                    continue
                fields.append(k)
                placeholders.append("%s")
                # serialize agent_output dict to JSON string
                if k == "agent_output" and isinstance(v, (dict, list)):
                    values.append(json.dumps(v))
                else:
                    values.append(v)

            sql = f"INSERT INTO credit_applications ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            logger.debug(f"Executing SQL: {sql}, values count: {len(values)}")
            cur.execute(sql, tuple(values))
            conn.commit()
            inserted_id = cur.lastrowid
            logger.info(f"Successfully inserted application with id={inserted_id}")
            return json.dumps({"inserted_id": inserted_id})
    except Exception as e:
        logger.error(f"insert_application failed: {e}", exc_info=True)
        return json.dumps({"error": "insert_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug("DB connection closed after insert_application")
        except Exception as e:
            logger.warning(f"Error closing connection in insert_application: {e}")


@tool
def get_application(application_id: int) -> str:
    """Return a single application row by `application_id` as JSON."""
    logger.info(f"get_application called with application_id={application_id}")
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"Failed to get DB connection in get_application (id={application_id}): {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM credit_applications WHERE id=%s LIMIT 1"
            logger.debug(f"Executing query: {sql} with id={application_id}")
            cur.execute(sql, (application_id,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"No application found for id={application_id}")
                return json.dumps({"error": "not_found", "application_id": application_id})
            logger.info(f"Found application {application_id}, returning {len(row)} fields")
            return json.dumps(row, default=str, indent=2)
    except Exception as e:
        logger.error(f"get_application query failed (id={application_id}): {e}", exc_info=True)
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"DB connection closed after get_application (id={application_id})")
        except Exception as e:
            logger.warning(f"Error closing connection in get_application (id={application_id}): {e}")


@tool
def list_applications(limit: int = 10) -> str:
    """Return up to `limit` applications ordered by `created_at` desc."""
    logger.info(f"list_applications called with limit={limit}")
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"Failed to get DB connection in list_applications: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM credit_applications ORDER BY created_at DESC LIMIT %s"
            logger.debug(f"Executing query: {sql} with limit={limit}")
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            logger.info(f"list_applications returning {len(rows)} rows")
            return _rows_to_json(rows)
    except Exception as e:
        logger.error(f"list_applications query failed: {e}", exc_info=True)
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug("DB connection closed after list_applications")
        except Exception as e:
            logger.warning(f"Error closing connection in list_applications: {e}")


@tool
def update_application_status(application_id: int, status: str, reason: Optional[str] = None, confidence: Optional[float] = None) -> str:
    """Update status, reason, and confidence for an application."""
    logger.info(f"update_application_status called: id={application_id}, status={status}, confidence={confidence}")
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"Failed to get DB connection in update_application_status (id={application_id}): {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            parts = ["application_status=%s"]
            values = [status]
            if reason is not None:
                parts.append("decision_reason=%s")
                values.append(reason)
                logger.debug(f"Adding reason to update for id={application_id}")
            if confidence is not None:
                parts.append("decision_confidence=%s")
                values.append(confidence)
                logger.debug(f"Adding confidence to update for id={application_id}")
            values.append(application_id)
            sql = f"UPDATE credit_applications SET {', '.join(parts)} WHERE id=%s"
            logger.debug(f"Executing update: {sql}")
            cur.execute(sql, tuple(values))
            conn.commit()
            logger.info(f"update_application_status: updated {cur.rowcount} rows for id={application_id}")
            return json.dumps({"updated_rows": cur.rowcount})
    except Exception as e:
        logger.error(f"update_application_status failed (id={application_id}): {e}", exc_info=True)
        return json.dumps({"error": "update_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"DB connection closed after update_application_status (id={application_id})")
        except Exception as e:
            logger.warning(f"Error closing connection in update_application_status (id={application_id}): {e}")


@tool
def find_latest_by_applicant(applicant_name: str) -> str:
    """Return the latest application row for a given applicant name (case-insensitive, trimmed)."""
    logger.info(f"find_latest_by_applicant called with name: {applicant_name}")
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"Failed to get DB connection in find_latest_by_applicant (name={applicant_name}): {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        # Strip whitespace and search case-insensitively
        search_name = applicant_name.strip()
        logger.debug(f"Searching for applicant: {search_name}")
        with conn.cursor() as cur:
            # Use LOWER for case-insensitive search
            sql = "SELECT * FROM credit_applications WHERE LOWER(applicant_name)=LOWER(%s) ORDER BY created_at DESC LIMIT 1"
            logger.debug(f"Executing query: {sql} with name={search_name}")
            cur.execute(sql, (search_name,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"No application found for applicant: {search_name}")
                return json.dumps({"error": "not_found", "applicant_name": search_name})
            logger.info(f"Found application for {search_name}")
            return json.dumps(row, default=str, indent=2)
    except Exception as e:
        logger.error(f"find_latest_by_applicant query failed (name={applicant_name}): {e}", exc_info=True)
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"DB connection closed after find_latest_by_applicant (name={applicant_name})")
        except Exception as e:
            logger.warning(f"Error closing connection in find_latest_by_applicant (name={applicant_name}): {e}")


@tool
def update_application_agent_output(application_id: int, agent_output: Any) -> str:
    """Update the `agent_output` JSON column for an application.

    `agent_output` may be a dict/list; it will be serialized to JSON.
    Returns JSON with `updated_rows` or an error object.
    """
    logger.info(f"update_application_agent_output called for id={application_id}")
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"Failed to get DB connection in update_application_agent_output (id={application_id}): {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            payload = json.dumps(agent_output)
            payload_size = len(payload)
            logger.debug(f"Updating agent_output for id={application_id}, payload size: {payload_size} bytes")
            sql = "UPDATE credit_applications SET agent_output=%s WHERE id=%s"
            cur.execute(sql, (payload, application_id))
            conn.commit()
            logger.info(f"update_application_agent_output: updated {cur.rowcount} rows for id={application_id}")
            return json.dumps({"updated_rows": cur.rowcount})
    except Exception as e:
        logger.error(f"update_application_agent_output failed (id={application_id}): {e}", exc_info=True)
        return json.dumps({"error": "update_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"DB connection closed after update_application_agent_output (id={application_id})")
        except Exception as e:
            logger.warning(f"Error closing connection in update_application_agent_output (id={application_id}): {e}")
