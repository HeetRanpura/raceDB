"""
RaceDB — /api/query router (SQL Playground)
Accepts arbitrary SQL from the frontend and returns columnar results.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from db.connection import get_connection, close_resources

router = APIRouter(prefix="/api", tags=["Playground"])


class QueryRequest(BaseModel):
    sql: str = Field(..., description="Raw SQL query to execute")


class QueryResponse(BaseModel):
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    message: str = ""


@router.post("/query", response_model=QueryResponse)
async def run_query(req: QueryRequest):
    """Execute an arbitrary SQL statement and return the result set."""
    sql = req.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    conn = None
    cursor = None
    try:
        conn = get_connection(isolation_level="READ COMMITTED")
        cursor = conn.cursor()
        cursor.execute(sql)

        upper = sql.upper().lstrip()
        is_select = upper.startswith("SELECT") or upper.startswith("SHOW") or upper.startswith("DESCRIBE") or upper.startswith("EXPLAIN")

        if is_select:
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            raw_rows = cursor.fetchall()
            rows = [list(r) for r in raw_rows]
            return QueryResponse(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                message=f"{len(rows)} row(s) returned",
            )
        else:
            conn.commit()
            affected = cursor.rowcount
            return QueryResponse(
                columns=[],
                rows=[],
                row_count=affected,
                message=f"Query OK, {affected} row(s) affected",
            )

    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        close_resources(conn, cursor)


@router.get("/schema-info")
async def get_schema_info():
    """Return table and column metadata for the ER diagram."""
    conn = None
    cursor = None
    try:
        conn = get_connection(isolation_level="READ COMMITTED")
        cursor = conn.cursor()

        # Get all tables
        cursor.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME"
        )
        tables = [row[0] for row in cursor.fetchall()]

        schema = {}
        for table in tables:
            cursor.execute(
                "SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_KEY, IS_NULLABLE, COLUMN_DEFAULT, EXTRA "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                (table,),
            )
            schema[table] = [
                {
                    "name": row[0],
                    "type": row[1],
                    "key": row[2],       # PRI, MUL, UNI
                    "nullable": row[3],
                    "default": str(row[4]) if row[4] is not None else None,
                    "extra": row[5],
                }
                for row in cursor.fetchall()
            ]

        # Get foreign keys
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL"
        )
        foreign_keys = [
            {
                "table": row[0],
                "column": row[1],
                "ref_table": row[2],
                "ref_column": row[3],
            }
            for row in cursor.fetchall()
        ]

        return {"tables": schema, "foreign_keys": foreign_keys}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        close_resources(conn, cursor)
