#!/usr/bin/env python3
"""Minimal Databricks SQL runner for the demo build.

Runs one or more SQL statements against a warehouse via the Statement Execution
API, using the OAuth token from a CLI profile. Usage:

    python3 run_sql.py <<'SQL'
    SELECT 1;
    SELECT current_catalog();
    SQL

Env: PROFILE (default YOUR_PROFILE), WAREHOUSE_ID, CATALOG, SCHEMA.
Statements are split on ';\n' at top level (simple splitter; fine for our DDL).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

PROFILE = os.environ.get("PROFILE", "YOUR_PROFILE")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "YOUR_WAREHOUSE_ID")
CATALOG = os.environ.get("CATALOG")
SCHEMA = os.environ.get("SCHEMA")


def _cfg():
    host = subprocess.run(
        ["databricks", "auth", "env", "--profile", PROFILE],
        capture_output=True, text=True)
    # `auth env` prints export lines; grab host + token via `auth token`
    tok = subprocess.run(
        ["databricks", "auth", "token", "--profile", PROFILE],
        capture_output=True, text=True)
    token = json.loads(tok.stdout)["access_token"]
    # host from .databrickscfg
    host = None
    cfg = os.path.expanduser("~/.databrickscfg")
    cur = None
    for line in open(cfg):
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
        elif cur == PROFILE and line.startswith("host"):
            host = line.split("=", 1)[1].strip()
    return host, token


HOST, TOKEN = _cfg()


def run(stmt):
    body = {
        "warehouse_id": WAREHOUSE_ID,
        "statement": stmt,
        "wait_timeout": "50s",
        "on_wait_timeout": "CONTINUE",
        "format": "JSON_ARRAY",
        "disposition": "INLINE",
    }
    if CATALOG:
        body["catalog"] = CATALOG
    if SCHEMA:
        body["schema"] = SCHEMA
    req = urllib.request.Request(
        f"{HOST}/api/2.0/sql/statements",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req) as r:
        res = json.load(r)
    sid = res["statement_id"]
    while res["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(2)
        req = urllib.request.Request(
            f"{HOST}/api/2.0/sql/statements/{sid}",
            headers={"Authorization": f"Bearer {TOKEN}"})
        with urllib.request.urlopen(req) as r:
            res = json.load(r)
    st = res["status"]["state"]
    if st != "SUCCEEDED":
        err = res["status"].get("error", {})
        raise RuntimeError(f"[{st}] {err.get('message', res['status'])}")
    return res.get("result", {}).get("data_array")


def main():
    sql = sys.stdin.read()
    stmts = [s.strip() for s in sql.split(";\n") if s.strip()]
    # also handle a single trailing statement w/o ;\n
    for i, stmt in enumerate(stmts, 1):
        stmt = stmt.rstrip().rstrip(";")
        if not stmt:
            continue
        label = stmt.splitlines()[0][:70]
        try:
            rows = run(stmt)
            n = len(rows) if rows else 0
            print(f"[{i}/{len(stmts)}] OK  {label}" + (f"  -> {n} rows" if rows else ""))
            if rows and n <= 15:
                for row in rows:
                    print("      ", row)
        except Exception as e:
            print(f"[{i}/{len(stmts)}] FAIL {label}\n       {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
