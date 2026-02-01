import os
import re
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


_TABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. Example: mysql+pymysql://user:pass@host:3306/dbname"
        )
    return url


def make_engine() -> Engine:
    url = get_database_url()
    return create_engine(url, future=True, pool_pre_ping=True)


def validate_table_name(name: str) -> bool:
    return bool(_TABLE_NAME_RE.match(name))


def fetch_records(engine: Engine, table: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not validate_table_name(table):
        raise ValueError("Invalid table name")

    stmt = text(f"SELECT * FROM {table} LIMIT :limit")
    with engine.connect() as conn:
        result = conn.execute(stmt, {"limit": limit})
        rows = result.mappings().all()
    return [dict(r) for r in rows]


app = FastAPI(title="FastMCP")
engine: Engine | None = None


@app.on_event("startup")
def _startup():
    global engine
    engine = make_engine()


@app.get("/mcp/health")
def health():
    return {"status": "ok"}


@app.get("/mcp/records")
def records(table: str = Query(None), limit: int = Query(100, ge=1, le=10000)):
    global engine
    if engine is None:
        engine = make_engine()

    table_name = table or os.environ.get("TABLE_NAME", "items")
    if not validate_table_name(table_name):
        raise HTTPException(status_code=400, detail="Invalid table name")

    try:
        data = fetch_records(engine, table_name, limit)
        return {"table": table_name, "count": len(data), "records": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("MCPServer:app", host="0.0.0.0", port=port, reload=False)
