# Databricks notebook source
# MAGIC %md
# MAGIC # Add embeddings to the UC Delta `cases` table
# MAGIC Pulls the exact `vector(1024)` embeddings from Lakebase (so they match the
# MAGIC search index) and writes them into `healthplan_appeals.appeals.cases` as an
# MAGIC `ARRAY<FLOAT>` column, governed in UC, in the existing catalog. Additive
# MAGIC (ALTER ADD COLUMN + MERGE); does not create a new catalog or table.

# COMMAND ----------

# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import json, psycopg
from databricks.sdk import WorkspaceClient
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, FloatType

PROJECT, BRANCH = "healthplan-appeals", "production"
TABLE = "healthplan_appeals.appeals.cases"

w = WorkspaceClient()
user_email = w.current_user.me().user_name
ep = w.api_client.do("GET", f"/api/2.0/postgres/projects/{PROJECT}/branches/{BRANCH}/endpoints")["endpoints"][0]
host = ep["status"]["hosts"]["host"]
token = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": ep["name"]})["token"]
conn = psycopg.connect(host=host, dbname="databricks_postgres", user=user_email,
                       password=token, sslmode="require", autocommit=True)

# COMMAND ----------

# Pull the stored embeddings as text pgvector literals and parse to float lists.
with conn.cursor() as cur:
    cur.execute("SELECT case_id, embedding::text FROM cases")
    rows = cur.fetchall()

def parse_vec(s):
    return [float(x) for x in s.strip()[1:-1].split(",")]

data = [(cid, parse_vec(vec)) for cid, vec in rows]
print(f"pulled {len(data)} embeddings; dim = {len(data[0][1])}")

emb_schema = StructType([
    StructField("case_id", StringType(), False),
    StructField("embedding", ArrayType(FloatType()), False),
])
emb_df = spark.createDataFrame(data, emb_schema)
emb_df.createOrReplaceTempView("emb")

# COMMAND ----------

# Add the column if missing, then MERGE the embeddings in (additive, keeps all other data).
cols = [f.name for f in spark.table(TABLE).schema.fields]
if "embedding" not in cols:
    spark.sql(f"ALTER TABLE {TABLE} ADD COLUMNS (embedding ARRAY<FLOAT>)")
    print("added embedding ARRAY<FLOAT> column")
else:
    print("embedding column already present")

spark.sql(f"""
    MERGE INTO {TABLE} t USING emb s ON t.case_id = s.case_id
    WHEN MATCHED THEN UPDATE SET t.embedding = s.embedding
""")

# COMMAND ----------

# Verify + document the column in UC.
n_total, n_emb = spark.sql(
    f"SELECT count(*), count(embedding) FROM {TABLE}").collect()[0]
spark.sql(f"COMMENT ON COLUMN {TABLE}.embedding IS "
          f"'gte-large-en 1024-dim embedding of narrative; mirrors the Lakebase search vector'")
result = {"table": TABLE, "rows": n_total, "rows_with_embedding": n_emb,
          "dim": len(data[0][1])}
print(result)
dbutils.notebook.exit(json.dumps(result))
