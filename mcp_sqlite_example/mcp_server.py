"""Local MCP server exposing a small SQLite database of sample data.

Run it with::

    python mcp_server.py

It serves a Streamable HTTP MCP endpoint at http://127.0.0.1:8000/mcp
and creates/seeds ``sample.db`` in the same folder on first launch.
"""

import json
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent / "sample.db"

mcp = FastMCP(
    "sqlite-sample",
    instructions=(
        "Read-only SQLite access to a small sample database. "
        "Use list_tables and table_schema to explore, then run_query to fetch data."
    ),
    host="127.0.0.1",
    port=8000,
)


def _connect(readonly: bool = True) -> sqlite3.Connection:
    if readonly:
        uri = f"file:{DB_PATH.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _seed() -> None:
    """Create the database and populate it with sample rows if it's missing."""
    if DB_PATH.exists():
        return

    conn = _connect(readonly=False)
    try:
        conn.executescript(
            """
            CREATE TABLE employees (
                id         INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                department TEXT NOT NULL,
                salary     REAL NOT NULL,
                hire_date  TEXT NOT NULL
            );

            CREATE TABLE products (
                id       INTEGER PRIMARY KEY,
                name     TEXT NOT NULL,
                category TEXT NOT NULL,
                price    REAL NOT NULL,
                stock    INTEGER NOT NULL
            );

            CREATE TABLE customers (
                id         INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                country    TEXT NOT NULL,
                total_orders INTEGER NOT NULL DEFAULT 0
            );

            INSERT INTO employees (name, department, salary, hire_date) VALUES
                ('Alice Johnson', 'Engineering', 95000, '2019-03-15'),
                ('Bob Smith',     'Engineering', 88000, '2020-07-01'),
                ('Carol Lee',     'Sales',        72000, '2018-11-20'),
                ('David Kim',     'Sales',        76000, '2021-01-10'),
                ('Eve Martinez',  'Marketing',    65000, '2022-05-30'),
                ('Frank Brown',   'Engineering', 101000, '2017-09-01'),
                ('Grace Hopper',  'Data',         99000, '2016-02-12'),
                ('Hank Wilson',   'Marketing',    61000, '2023-04-18');

            INSERT INTO products (name, category, price, stock) VALUES
                ('Laptop Pro 14',  'Electronics', 1299.99, 42),
                ('Wireless Mouse', 'Electronics',   24.99, 180),
                ('Desk Chair',     'Furniture',    149.00, 25),
                ('Standing Desk',  'Furniture',    399.00, 12),
                ('Coffee Mug',     'Office',         9.50, 300),
                ('Notebook 5-pack','Office',        12.75, 150),
                ('Monitor 27"',    'Electronics',  279.00, 36),
                ('Mechanical Keyboard', 'Electronics', 89.99, 74);

            INSERT INTO customers (name, country, total_orders) VALUES
                ('Acme Corp',      'USA',     25),
                ('Globex GmbH',    'Germany', 41),
                ('Initech Ltd',    'UK',      17),
                ('Hooli Inc',      'USA',     58),
                ('Stark Industries','USA',    33),
                ('Wayne Enterprises','USA',   12);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _rows_to_json(rows: list[sqlite3.Row]) -> str:
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


@mcp.tool()
def list_tables() -> str:
    """Return the names of all tables available in the sample database."""
    _seed()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return _rows_to_json(rows)


@mcp.tool()
def table_schema(table_name: str) -> str:
    """Return the columns (and their types) of a given table.

    Args:
        table_name: Name of the table to describe, e.g. "employees".
    """
    _seed()
    conn = _connect()
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    finally:
        conn.close()
    if not rows:
        return json.dumps({"error": f"table '{table_name}' not found"})
    columns = [{"name": r["name"], "type": r["type"], "notnull": bool(r["notnull"])} for r in rows]
    return json.dumps(columns, indent=2)


@mcp.tool()
def run_query(sql: str) -> str:
    """Execute a single read-only SELECT query and return the resulting rows as JSON.

    Args:
        sql: A SELECT statement, e.g. "SELECT * FROM employees WHERE salary > 90000".
    """
    _seed()

    stripped = sql.strip().rstrip(";").strip()
    keyword = stripped.split(maxsplit=1)[0].upper() if stripped else ""
    if keyword not in {"SELECT", "WITH", "PRAGMA"}:
        return json.dumps(
            {"error": f"Only read-only queries are allowed (got '{keyword or '<empty>'}')"}
        )

    conn = _connect()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(100)
    except Exception as exc:  # noqa: BLE001 - surface DB errors to the caller
        return json.dumps({"error": str(exc)})
    finally:
        conn.close()

    if not rows:
        return json.dumps([])
    return _rows_to_json(rows)


if __name__ == "__main__":
    _seed()
    print(f"Serving MCP over Streamable HTTP at http://127.0.0.1:8000/mcp")
    mcp.run(transport="streamable-http")
