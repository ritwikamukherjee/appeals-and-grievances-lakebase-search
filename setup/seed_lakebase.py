# Databricks notebook source
# MAGIC %md
# MAGIC # Seed Lakebase, Health Plan Appeals & Grievances
# MAGIC Loads the `healthplan_appeals.appeals.cases` Delta table into the Lakebase
# MAGIC project `healthplan-appeals` (production branch), computes `VECTOR(1024)`
# MAGIC embeddings with `databricks-gte-large-en`, and builds a pgvector HNSW index.
# MAGIC
# MAGIC Vector-only v1 (mirrors the BakeReview course). Lakebase Search extensions
# MAGIC (`lakebase_vector`/`lakebase_ann`, `lakebase_bm25`, hybrid) are built live in
# MAGIC the lecture after the Beta toggle is enabled on the project.

# COMMAND ----------

# MAGIC %pip install --quiet "psycopg[binary]" pgvector
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

PROJECT_ID = "healthplan-appeals"
BRANCH = "production"
EMBEDDING_MODEL = "databricks-gte-large-en"   # 1024-dim
SOURCE_TABLE = "healthplan_appeals.appeals.cases"
PLANS_TABLE = "healthplan_appeals.appeals.plans"

# COMMAND ----------

# --- Connect to the Lakebase production branch endpoint ---
# Use the REST API via the SDK's api_client so this works regardless of the
# in-workspace databricks-sdk version (the `w.postgres` service is newer than
# the serverless default SDK).
import psycopg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user_email = w.current_user.me().user_name

eps_resp = w.api_client.do(
    "GET", f"/api/2.0/postgres/projects/{PROJECT_ID}/branches/{BRANCH}/endpoints")
endpoints = eps_resp.get("endpoints", [])
assert endpoints, "no endpoint on production branch"
ep = endpoints[0]
ep_name = ep["name"]
host = ep["status"]["hosts"]["host"]

cred = w.api_client.do(
    "POST", "/api/2.0/postgres/credentials", body={"endpoint": ep_name})
token = cred["token"]

conn = psycopg.connect(
    host=host, dbname="databricks_postgres", user=user_email,
    password=token, sslmode="require", autocommit=True)
print("connected to", host, "as", user_email)

# COMMAND ----------

# --- Read the denormalized cases (join plan attributes for app convenience) ---
df = spark.sql(f"""
    SELECT c.case_id, c.plan_id, p.plan_name, p.line_of_business,
           c.case_type, c.member_id, c.member_name, c.filed_date,
           c.service_category, c.denial_reason_code, c.denial_reason_desc,
           c.cpt_hcpcs_code, c.icd10_code, c.disposition, c.narrative
    FROM {SOURCE_TABLE} c JOIN {PLANS_TABLE} p USING (plan_id)
    ORDER BY c.case_id
""")
rows = df.collect()
print(f"{len(rows)} cases loaded from Delta")

# COMMAND ----------

# --- Embed narratives in batches via the Foundation Model endpoint ---
def embed_batch(texts):
    r = w.serving_endpoints.query(name=EMBEDDING_MODEL, input=list(texts))
    return [d.embedding for d in r.data]

narratives = [r["narrative"] for r in rows]
vectors = []
B = 96
for i in range(0, len(narratives), B):
    vectors.extend(embed_batch(narratives[i:i + B]))
    print(f"  embedded {min(i + B, len(narratives))}/{len(narratives)}")
assert len(vectors) == len(rows)
print("embedding dim:", len(vectors[0]))

# COMMAND ----------

# --- Build the Postgres table + pgvector HNSW index ---
DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
DROP TABLE IF EXISTS cases;
CREATE TABLE cases (
    case_id            text PRIMARY KEY,
    plan_id            text,
    plan_name          text,
    line_of_business   text,
    case_type          text,
    member_id          text,
    member_name        text,
    filed_date         date,
    service_category   text,
    denial_reason_code text,
    denial_reason_desc text,
    cpt_hcpcs_code     text,
    icd10_code         text,
    disposition        text,
    narrative          text,
    embedding          vector(1024)
);
"""
with conn.cursor() as cur:
    cur.execute(DDL)
print("table created")

# COMMAND ----------

# --- Insert rows (embedding passed as a vector literal, cast server-side) ---
insert_sql = """
INSERT INTO cases (case_id, plan_id, plan_name, line_of_business, case_type,
    member_id, member_name, filed_date, service_category, denial_reason_code,
    denial_reason_desc, cpt_hcpcs_code, icd10_code, disposition, narrative, embedding)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
"""
with conn.cursor() as cur:
    for r, vec in zip(rows, vectors):
        vec_lit = "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"
        cur.execute(insert_sql, (
            r["case_id"], r["plan_id"], r["plan_name"], r["line_of_business"],
            r["case_type"], r["member_id"], r["member_name"],
            str(r["filed_date"]), r["service_category"], r["denial_reason_code"],
            r["denial_reason_desc"], r["cpt_hcpcs_code"], r["icd10_code"],
            r["disposition"], r["narrative"], vec_lit))
    cur.execute("CREATE INDEX IF NOT EXISTS cases_embedding_hnsw ON cases "
                "USING hnsw (embedding vector_cosine_ops)")
    cur.execute("ANALYZE cases")
    cur.execute("SELECT count(*) FROM cases")
    n = cur.fetchone()[0]
print(f"inserted {n} rows + HNSW index")

# COMMAND ----------

# --- Validate: semantic (vector) search with a query that shares no keywords ---
q = "a member could not get their expensive arthritis biologic approved"
qvec = embed_batch([q])[0]
qlit = "[" + ",".join(f"{float(x):.6f}" for x in qvec) + "]"
with conn.cursor() as cur:
    cur.execute("""
        SELECT plan_name, service_category, denial_reason_code,
               round((embedding <=> %s::vector)::numeric, 4) AS dist,
               left(narrative, 140) AS snippet
        FROM cases ORDER BY embedding <=> %s::vector LIMIT 5
    """, (qlit, qlit))
    print(f"QUERY: {q}\n")
    for row in cur.fetchall():
        print(row[0], "|", row[1], "|", row[2], "| dist", row[3])
        print("   ", row[4], "...\n")

print("SEED COMPLETE")
