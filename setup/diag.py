# Databricks notebook source
# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
import json, psycopg
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
ue = w.current_user.me().user_name
eps = w.api_client.do("GET", "/api/2.0/postgres/projects/healthplan-appeals/branches/production/endpoints")["endpoints"][0]
host = eps["status"]["hosts"]["host"]
tok = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": eps["name"]})["token"]
c = psycopg.connect(host=host, dbname="databricks_postgres", user=ue, password=tok, sslmode="require", autocommit=True)
out = {}
with c.cursor() as cur:
    for name in ("shared_preload_libraries",):
        cur.execute(f"SHOW {name}"); out[name] = cur.fetchone()[0]
    for gv in ("neon.allowed_extensions",):
        try:
            cur.execute(f"SHOW {gv}"); out[gv] = cur.fetchone()[0]
        except Exception as e:
            out[gv] = f"ERR: {str(e)[:100]}"
    cur.execute("SELECT current_setting('server_version')"); out["pg_version"] = cur.fetchone()[0]
    cur.execute("SELECT pg_postmaster_start_time()::text"); out["postmaster_start"] = cur.fetchone()[0]
dbutils.notebook.exit(json.dumps(out, indent=2))
