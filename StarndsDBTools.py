"""Database tools for Strands Agents.

Provides simple `@tool` wrappers to read employee details from a MySQL
database. Credentials are read from environment variables for safety.

Environment variables:
- DB_HOST (optional, defaults to the RDS host provided)
- DB_USER (required)
- DB_PASSWORD (required)
- DB_NAME (optional, defaults to "dev")
- DB_PORT (optional, defaults to 3306)

Tools:
- `get_employee(employee_id: int)` -> JSON string of the matching row
- `list_employees(limit: int = 10)` -> JSON list of rows

This module uses PyMySQL; ensure `PyMySQL` is installed in the project's
virtualenv (it's included in `requirements.txt` as `PyMySQL`).
"""

from strands import tool
import os
import json
from typing import List, Dict, Any

try:
    import pymysql
except Exception as e:
    pymysql = None

# Default host from your request
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
    # Ensure JSON serializable (convert bytes, decimals, etc. to str)
    def _clean(val):
        try:
            json.dumps(val)
            return val
        except Exception:
            return str(val)

    cleaned = []
    for r in rows:
        cleaned.append({k: _clean(v) for k, v in r.items()})
    return json.dumps(cleaned, indent=2)


@tool
def get_employee(employee_id: int) -> str:
    """Return details for a single employee by `employee_id`.

    Reads DB credentials from environment. Returns a JSON string.
    """
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM dev.employees WHERE id=%s LIMIT 1"
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
            if not row:
                return json.dumps({"error": "employee_not_found", "employee_id": employee_id})
            return json.dumps(row, default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": "query_failed", "message": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@tool
def list_employees(limit: int = 10) -> str:
    """Return up to `limit` employee rows from `dev.employees` as JSON."""
    try:
        conn = _get_db_conn()
    except Exception as e:
        return json.dumps({"error": str(e)})

    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM dev.employees LIMIT %s"
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
