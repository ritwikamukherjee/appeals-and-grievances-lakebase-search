# Databricks notebook source
# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import json, psycopg
from databricks.sdk import WorkspaceClient

PROJECT_ID, BRANCH = "healthplan-appeals", "production"
EMBEDDING_MODEL = "databricks-gte-large-en"
w = WorkspaceClient()
user_email = w.current_user.me().user_name
eps = w.api_client.do("GET", f"/api/2.0/postgres/projects/{PROJECT_ID}/branches/{BRANCH}/endpoints")["endpoints"]
ep = eps[0]; host = ep["status"]["hosts"]["host"]
token = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": ep["name"]})["token"]
conn = psycopg.connect(host=host, dbname="databricks_postgres", user=user_email,
                       password=token, sslmode="require", autocommit=True)

def embed(t):
    r = w.serving_endpoints.query(name=EMBEDDING_MODEL, input=[t])
    return "[" + ",".join(f"{float(x):.6f}" for x in r.data[0].embedding) + "]"

report = {"steps": []}
def step(label, fn):
    try:
        out = fn(); report["steps"].append({label: "OK", "sample": out}); return out
    except Exception as e:
        report["steps"].append({label: f"ERR: {str(e)[:200]}"}); return None

cur = conn.cursor()

# 1. Build Search objects (exact SQL from the lecture notebook)
def build():
    cur.execute("CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE")
    cur.execute("CREATE EXTENSION IF NOT EXISTS lakebase_text")
    cur.execute("""ALTER TABLE cases ADD COLUMN IF NOT EXISTS search_tsv tsvector
         GENERATED ALWAYS AS (to_tsvector('english',
           coalesce(narrative,'') || ' ' || coalesce(denial_reason_code,'') || ' ' ||
           coalesce(cpt_hcpcs_code,'') || ' ' || coalesce(icd10_code,'') || ' ' ||
           coalesce(service_category,''))) STORED""")
    cur.execute("CREATE INDEX IF NOT EXISTS cases_embedding_ann ON cases USING lakebase_ann (embedding vector_cosine_ops)")
    cur.execute("CREATE INDEX IF NOT EXISTS cases_search_bm25 ON cases USING lakebase_bm25 (search_tsv)")
    cur.execute("ANALYZE cases")
    cur.execute("SELECT extname FROM pg_extension ORDER BY extname")
    return [r[0] for r in cur.fetchall()]
step("build_indexes", build)

# 2. BM25 keyword query
def bm25():
    term = "CO-197"
    cur.execute(f"""
        SELECT plan_name,
               round((search_tsv <@> to_bm25query(to_tsvector('english', '{term}'), 'cases_search_bm25'))::numeric, 3) AS bm25,
               left(narrative, 80)
        FROM cases
        ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', '{term}'), 'cases_search_bm25')
        LIMIT 3""")
    return [list(r) for r in cur.fetchall()]
step("bm25_query", bm25)

# 3. Hybrid RRF query
def hybrid():
    qv = embed("member needs a mobility device to get around their home safely")
    kw = "wheelchair"
    cur.execute(f"""
        WITH vec AS (
            SELECT case_id, plan_name, narrative,
                   row_number() OVER (ORDER BY embedding <=> '{qv}') AS rank
            FROM cases ORDER BY embedding <=> '{qv}' LIMIT 30
        ),
        kw AS (
            SELECT case_id,
                   row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', '{kw}'), 'cases_search_bm25')) AS rank
            FROM cases WHERE search_tsv @@ plainto_tsquery('english', '{kw}') LIMIT 30
        )
        SELECT v.plan_name,
               round((coalesce(1.0/(60+v.rank),0) + coalesce(1.0/(60+k.rank),0))::numeric, 5) AS rrf,
               left(v.narrative, 80)
        FROM vec v LEFT JOIN kw k USING (case_id)
        ORDER BY rrf DESC LIMIT 3""")
    return [list(r) for r in cur.fetchall()]
step("hybrid_query", hybrid)

dbutils.notebook.exit(json.dumps(report, indent=2, default=str))
