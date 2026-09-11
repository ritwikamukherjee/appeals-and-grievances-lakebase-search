# Databricks notebook source
# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import json
import psycopg
from databricks.sdk import WorkspaceClient

PROJECT_ID, BRANCH = "healthplan-appeals", "production"
w = WorkspaceClient()
user_email = w.current_user.me().user_name
eps = w.api_client.do("GET", f"/api/2.0/postgres/projects/{PROJECT_ID}/branches/{BRANCH}/endpoints")["endpoints"]
ep = eps[0]
host = ep["status"]["hosts"]["host"]
token = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": ep["name"]})["token"]
conn = psycopg.connect(host=host, dbname="databricks_postgres", user=user_email,
                       password=token, sslmode="require", autocommit=True)

report = {}
with conn.cursor() as cur:
    cur.execute("SELECT count(*), count(embedding) FROM cases")
    report["rows_total"], report["rows_with_embedding"] = cur.fetchone()

    # Which lakebase_* extensions are AVAILABLE to install on this project?
    cur.execute("SELECT name FROM pg_available_extensions WHERE name LIKE 'lakebase%' OR name LIKE '%bm25%' OR name='vector' ORDER BY name")
    report["available_search_exts"] = [r[0] for r in cur.fetchall()]

    # Try to create each Lakebase Search extension; capture the error verbatim.
    for ext in ("lakebase_vector", "lakebase_text", "lakebase_bm25"):
        try:
            cur.execute(f"CREATE EXTENSION IF NOT EXISTS {ext} CASCADE")
            report[f"create_{ext}"] = "OK"
        except Exception as e:
            report[f"create_{ext}"] = f"ERR: {str(e)[:160]}"

    # Already-installed extensions
    cur.execute("SELECT extname FROM pg_extension ORDER BY extname")
    report["installed_exts"] = [r[0] for r in cur.fetchall()]

dbutils.notebook.exit(json.dumps(report, indent=2))
