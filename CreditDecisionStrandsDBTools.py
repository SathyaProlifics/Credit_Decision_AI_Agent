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
import time
from typing import List, Dict, Any, Optional

# Configure logging with more detailed format
logger = logging.getLogger("credit_decision_db")
logger.setLevel(logging.DEBUG)  # Ensure DEBUG level is set

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

    # Try loading DB settings from resource/properties file first, then fall back to environment
    logger.debug("Loading DB configuration...")
    props = _load_resource_properties()

    host = props.get("DB_HOST") or os.getenv("DB_HOST") or DEFAULT_HOST
    user = props.get("DB_USER") or os.getenv("DB_USER")
    password = props.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
    db = props.get("DB_NAME") or os.getenv("DB_NAME") or "dev"
    try:
        port = int(props.get("DB_PORT") or os.getenv("DB_PORT") or "3306")
    except ValueError:
        logger.warning("Invalid DB_PORT value, defaulting to 3306")
        port = 3306

    logger.debug(f"DB Config: host={host}, user={user}, database={db}, port={port}")

    if not user or not password:
        logger.error("Database credentials not set: DB_USER or DB_PASSWORD missing")
        logger.error(f"  user={user}, password_set={bool(password)}")
        raise RuntimeError("Database credentials not set. Please set DB_USER and DB_PASSWORD in resource/properties or environment variables.")

    try:
        logger.info(f"Attempting database connection to {db}@{host}:{port}")
        start_time = time.time()
        conn = pymysql.connect(host=host, user=user, password=password, database=db, port=port, cursorclass=pymysql.cursors.DictCursor)
        elapsed = time.time() - start_time
        logger.info(f"Successfully connected to database {db} at {host}:{port} (took {elapsed:.2f}s)")
        return conn
    except pymysql.MySQLError as e:
        logger.error(f"MySQL connection error: {type(e).__name__}: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected connection error: {type(e).__name__}: {e}", exc_info=True)
        raise


def _load_resource_properties() -> Dict[str, str]:
    """Load key=value pairs from resource/properties (if present).

    Returns a dict of properties. Keys and values are returned as strings.
    """
    props_path = os.path.join(os.path.dirname(__file__), "resource", "properties")
    result: Dict[str, str] = {}
    try:
        if os.path.exists(props_path):
            logger.debug(f"Loading DB properties from {props_path}")
            with open(props_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        result[k.strip()] = v.strip()
            logger.debug(f"Successfully loaded {len(result)} DB properties from resource/properties")
        else:
            logger.debug(f"resource/properties file not found at {props_path}, will use environment variables")
    except Exception as e:
        logger.warning(f"Failed to read {props_path}: {e}. Will fall back to environment variables.")
    return result


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
    logger.info(f"insert_application: Starting with keys={list(app.keys())}")
    start_time = time.time()
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"insert_application: Failed to get DB connection: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            fields = []
            placeholders = []
            values = []
            skipped_fields = []
            for k, v in app.items():
                # skip null/None values to let defaults apply
                if v is None:
                    skipped_fields.append(k)
                    continue
                fields.append(k)
                placeholders.append("%s")
                # serialize agent_output dict to JSON string
                if k == "agent_output" and isinstance(v, (dict, list)):
                    values.append(json.dumps(v))
                else:
                    values.append(v)

            if skipped_fields:
                logger.debug(f"insert_application: Skipped None values for fields: {skipped_fields}")
            
            sql = f"INSERT INTO credit_applications ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            logger.debug(f"insert_application: SQL={sql}")
            logger.debug(f"insert_application: Inserting {len(values)} values")
            
            query_start = time.time()
            cur.execute(sql, tuple(values))
            conn.commit()
            query_elapsed = time.time() - query_start
            
            inserted_id = cur.lastrowid
            total_elapsed = time.time() - start_time
            logger.info(f"insert_application: SUCCESS id={inserted_id} (query={query_elapsed:.3f}s, total={total_elapsed:.3f}s)")
            return json.dumps({"inserted_id": inserted_id})
    except Exception as e:
        logger.error(f"insert_application: FAILED after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": "insert_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug("insert_application: DB connection closed")
        except Exception as e:
            logger.warning(f"insert_application: Error closing connection: {e}")


@tool
def get_application(application_id: int) -> str:
    """Return a single application row by `application_id` as JSON."""
    logger.info(f"get_application: Looking up id={application_id}")
    start_time = time.time()
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"get_application: Failed to get DB connection for id={application_id}: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM credit_applications WHERE id=%s LIMIT 1"
            logger.debug(f"get_application: Executing query for id={application_id}")
            query_start = time.time()
            cur.execute(sql, (application_id,))
            row = cur.fetchone()
            query_elapsed = time.time() - query_start
            
            if not row:
                logger.warning(f"get_application: No record found for id={application_id}")
                return json.dumps({"error": "not_found", "application_id": application_id})
            
            fields_count = len(row) if row else 0
            total_elapsed = time.time() - start_time
            logger.info(f"get_application: SUCCESS id={application_id} fields={fields_count} (query={query_elapsed:.3f}s, total={total_elapsed:.3f}s)")
            return json.dumps(row, default=str, indent=2)
    except Exception as e:
        logger.error(f"get_application: FAILED for id={application_id} after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"get_application: Connection closed for id={application_id}")
        except Exception as e:
            logger.warning(f"get_application: Error closing connection for id={application_id}: {e}")


@tool
def list_applications(limit: int = 10) -> str:
    """Return up to `limit` applications ordered by `created_at` desc."""
    logger.info(f"list_applications: Starting with limit={limit}")
    start_time = time.time()
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"list_applications: Failed to get DB connection: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM credit_applications ORDER BY id DESC LIMIT %s"
            logger.debug(f"list_applications: Executing query with limit={limit}")
            query_start = time.time()
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            query_elapsed = time.time() - query_start
            
            total_elapsed = time.time() - start_time
            logger.info(f"list_applications: SUCCESS returned {len(rows)} rows (query={query_elapsed:.3f}s, total={total_elapsed:.3f}s)")
            return _rows_to_json(rows)
    except Exception as e:
        logger.error(f"list_applications: FAILED after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug("list_applications: Connection closed")
        except Exception as e:
            logger.warning(f"list_applications: Error closing connection: {e}")


@tool
def update_application_status(application_id: int, status: str, reason: Optional[str] = None, confidence: Optional[float] = None) -> str:
    """Update status, reason, and confidence for an application."""
    logger.info(f"update_application_status: START id={application_id}, status={status}, confidence={confidence}")
    start_time = time.time()
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"update_application_status: Failed to get DB connection for id={application_id}: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            parts = ["application_status=%s"]
            values = [status]
            additions = []
            
            if reason is not None:
                parts.append("decision_reason=%s")
                values.append(reason)
                additions.append("reason")
            
            if confidence is not None:
                parts.append("decision_confidence=%s")
                values.append(confidence)
                additions.append(f"confidence={confidence}")
            
            values.append(application_id)
            sql = f"UPDATE credit_applications SET {', '.join(parts)} WHERE id=%s"
            logger.debug(f"update_application_status: SQL={sql}")
            if additions:
                logger.debug(f"update_application_status: Additional fields={additions}")
            
            query_start = time.time()
            cur.execute(sql, tuple(values))
            conn.commit()
            query_elapsed = time.time() - query_start
            rows_updated = cur.rowcount
            
            total_elapsed = time.time() - start_time
            logger.info(f"update_application_status: SUCCESS id={application_id} updated_rows={rows_updated} (query={query_elapsed:.3f}s, total={total_elapsed:.3f}s)")
            return json.dumps({"updated_rows": rows_updated})
    except Exception as e:
        logger.error(f"update_application_status: FAILED for id={application_id} after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": "update_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"update_application_status: Connection closed for id={application_id}")
        except Exception as e:
            logger.warning(f"update_application_status: Error closing connection for id={application_id}: {e}")


@tool
def find_latest_by_applicant(applicant_name: str) -> str:
    """Return the latest application row for a given applicant name (case-insensitive, trimmed)."""
    logger.info(f"find_latest_by_applicant: Searching for name='{applicant_name}'")
    start_time = time.time()
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"find_latest_by_applicant: Failed to get DB connection for '{applicant_name}': {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        # Strip whitespace and search case-insensitively
        search_name = applicant_name.strip()
        logger.debug(f"find_latest_by_applicant: Normalized name='{search_name}'")
        with conn.cursor() as cur:
            # Use LOWER for case-insensitive search
            sql = "SELECT * FROM credit_applications WHERE LOWER(applicant_name)=LOWER(%s) ORDER BY created_at DESC LIMIT 1"
            logger.debug(f"find_latest_by_applicant: Executing case-insensitive search")
            query_start = time.time()
            cur.execute(sql, (search_name,))
            row = cur.fetchone()
            query_elapsed = time.time() - query_start
            
            if not row:
                total_elapsed = time.time() - start_time
                logger.warning(f"find_latest_by_applicant: No record found for '{search_name}' (query={query_elapsed:.3f}s, total={total_elapsed:.3f}s)")
                return json.dumps({"error": "not_found", "applicant_name": search_name})
            
            total_elapsed = time.time() - start_time
            logger.info(f"find_latest_by_applicant: SUCCESS found record for '{search_name}' (query={query_elapsed:.3f}s, total={total_elapsed:.3f}s)")
            return json.dumps(row, default=str, indent=2)
    except Exception as e:
        logger.error(f"find_latest_by_applicant: FAILED for '{applicant_name}' after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"find_latest_by_applicant: Connection closed")
        except Exception as e:
            logger.warning(f"find_latest_by_applicant: Error closing connection: {e}")


@tool
def update_application_agent_output(application_id: int, agent_output: Any) -> str:
    """Update the `agent_output` JSON column for an application.

    `agent_output` may be a dict/list; it will be serialized to JSON.
    Returns JSON with `updated_rows` or an error object.
    """
    logger.info(f"update_application_agent_output: START id={application_id}")
    start_time = time.time()
    try:
        conn = _get_db_conn()
    except Exception as e:
        logger.error(f"update_application_agent_output: Failed to get DB connection for id={application_id}: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            payload = json.dumps(agent_output)
            payload_size = len(payload)
            logger.debug(f"update_application_agent_output: Serialized agent_output to {payload_size} bytes")
            sql = "UPDATE credit_applications SET agent_output=%s WHERE id=%s"
            
            query_start = time.time()
            cur.execute(sql, (payload, application_id))
            conn.commit()
            query_elapsed = time.time() - query_start
            rows_updated = cur.rowcount
            
            total_elapsed = time.time() - start_time
            logger.info(f"update_application_agent_output: SUCCESS id={application_id} updated_rows={rows_updated} payload_size={payload_size}B (query={query_elapsed:.3f}s, total={total_elapsed:.3f}s)")
            return json.dumps({"updated_rows": rows_updated})
    except Exception as e:
        logger.error(f"update_application_agent_output: FAILED for id={application_id} after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"error": "update_failed", "message": str(e)})
    finally:
        try:
            conn.close()
            logger.debug(f"update_application_agent_output: Connection closed for id={application_id}")
        except Exception as e:
            logger.warning(f"update_application_agent_output: Error closing connection for id={application_id}")
