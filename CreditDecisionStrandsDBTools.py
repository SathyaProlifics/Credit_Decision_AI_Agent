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
from typing import List, Dict, Any, Optional

try:
    import pymysql
except Exception:
    pymysql = None

# Default host used previously in this workspace
DEFAULT_HOST = "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com"


def _get_db_conn():
    if pymysql is None:
        raise RuntimeError("PyMySQL is not installed in the environment")

    host = os.getenv("DB_HOST", DEFAULT_HOST)
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    db = os.getenv("DB_NAME", "dev")
    port = int(os.getenv("DB_PORT", "3306"))

    if not user or not password:
        raise RuntimeError("Database credentials not set. Please set DB_USER and DB_PASSWORD environment variables.")

    return pymysql.connect(host=host, user=user, password=password, database=db, port=port, cursorclass=pymysql.cursors.DictCursor)


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
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            fields = []
            placeholders = []
            values = []
            for k, v in app.items():
                # skip null/None values to let defaults apply
                if v is None:
                    continue
                fields.append(k)
                placeholders.append("%s")
                # serialize agent_output dict to JSON string
                if k == "agent_output" and isinstance(v, (dict, list)):
                    values.append(json.dumps(v))
                else:
                    values.append(v)

            sql = f"INSERT INTO credit_applications ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cur.execute(sql, tuple(values))
            conn.commit()
            inserted_id = cur.lastrowid
            return json.dumps({"inserted_id": inserted_id})
    except Exception as e:
        return json.dumps({"error": "insert_failed", "message": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@tool
def get_application(application_id: int) -> str:
    """Return a single application row by `application_id` as JSON."""
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM credit_applications WHERE id=%s LIMIT 1"
            cur.execute(sql, (application_id,))
            row = cur.fetchone()
            if not row:
                return json.dumps({"error": "not_found", "application_id": application_id})
            return json.dumps(row, default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@tool
def list_applications(limit: int = 10) -> str:
    """Return up to `limit` applications ordered by `created_at` desc."""
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM credit_applications ORDER BY created_at DESC LIMIT %s"
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            return _rows_to_json(rows)
    except Exception as e:
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@tool
def update_application_status(application_id: int, status: str, reason: Optional[str] = None, confidence: Optional[float] = None) -> str:
    """Update status, reason, and confidence for an application."""
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            parts = ["application_status=%s"]
            values = [status]
            if reason is not None:
                parts.append("decision_reason=%s")
                values.append(reason)
            if confidence is not None:
                parts.append("decision_confidence=%s")
                values.append(confidence)
            values.append(application_id)
            sql = f"UPDATE credit_applications SET {', '.join(parts)} WHERE id=%s"
            cur.execute(sql, tuple(values))
            conn.commit()
            return json.dumps({"updated_rows": cur.rowcount})
    except Exception as e:
        return json.dumps({"error": "update_failed", "message": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@tool
def find_latest_by_applicant(applicant_name: str) -> str:
    """Return the latest application row for a given applicant name (case-insensitive, trimmed)."""
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        # Strip whitespace and search case-insensitively
        search_name = applicant_name.strip()
        with conn.cursor() as cur:
            # Use LOWER for case-insensitive search
            sql = "SELECT * FROM credit_applications WHERE LOWER(applicant_name)=LOWER(%s) ORDER BY created_at DESC LIMIT 1"
            cur.execute(sql, (search_name,))
            row = cur.fetchone()
            if not row:
                return json.dumps({"error": "not_found", "applicant_name": search_name})
            return json.dumps(row, default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@tool
def update_application_agent_output(application_id: int, agent_output: Any) -> str:
    """Update the `agent_output` JSON column for an application.

    `agent_output` may be a dict/list; it will be serialized to JSON.
    Returns JSON with `updated_rows` or an error object.
    """
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            payload = json.dumps(agent_output)
            sql = "UPDATE credit_applications SET agent_output=%s WHERE id=%s"
            cur.execute(sql, (payload, application_id))
            conn.commit()
            return json.dumps({"updated_rows": cur.rowcount})
    except Exception as e:
        return json.dumps({"error": "update_failed", "message": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass
