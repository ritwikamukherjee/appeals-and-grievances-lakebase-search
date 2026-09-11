# Databricks notebook source
# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
import json, psycopg
from databricks.sdk import WorkspaceClient
w=WorkspaceClient(); ue=w.current_user.me().user_name
ep=w.api_client.do("GET","/api/2.0/postgres/projects/healthplan-appeals/branches/production/endpoints")["endpoints"][0]
host=ep["status"]["hosts"]["host"]; tok=w.api_client.do("POST","/api/2.0/postgres/credentials",body={"endpoint":ep["name"]})["token"]
conn=psycopg.connect(host=host,dbname="databricks_postgres",user=ue,password=tok,sslmode="require",autocommit=True)
def embed(t):
    r=w.api_client.do("POST","/serving-endpoints/databricks-gte-large-en/invocations",body={"input":[t]}); return "["+",".join(f"{float(x):.6f}" for x in r["data"][0]["embedding"])+"]"
def rows(sql,p=None):
    with conn.cursor() as c: c.execute(sql,p or ()); return c.fetchall()
K=5
def vec(qv): return rows(f"SELECT case_id,service_category,narrative FROM cases ORDER BY embedding <=> '{qv}' LIMIT {K}")
def bm(kw): return rows(f"SELECT case_id,service_category,narrative FROM cases ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25') LIMIT {K}",(kw,))
def hy(qv,kw): return rows(f"""WITH v AS (SELECT case_id,service_category,narrative,row_number() OVER (ORDER BY embedding <=> '{qv}') r FROM cases ORDER BY embedding <=> '{qv}' LIMIT 60),
     k AS (SELECT case_id,row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25')) r FROM cases WHERE search_tsv @@ plainto_tsquery('english',%s) LIMIT 60)
     SELECT v.case_id,v.service_category,v.narrative FROM v LEFT JOIN k USING(case_id) ORDER BY (coalesce(1.0/(60+v.r),0)+coalesce(1.0/(60+k.r),0)) DESC LIMIT {K}""",(kw,kw))

PAIRS=[
 ("a member with a serious autoimmune condition cannot get the medication they need","infusion"),
 ("the imaging my doctor ordered to check my head was refused","MRI"),
 ("the member needs help getting around their home safely","wheelchair"),
 ("the member's mental health care was stopped too early","residential"),
 ("the member cannot breathe well at night and needs their equipment","CPAP"),
 ("the operation the surgeon recommended to fix a joint was turned down","knee replacement"),
 ("the member was sent home from the hospital too soon after a fall","skilled nursing"),
]
out=[]
for q,kw in PAIRS:
    qv=embed(q); v,b,h=vec(qv),bm(kw),hy(qv,kw)
    vids=[r[0] for r in v]; hids=[r[0] for r in h]
    green = sum(1 for r in b if kw.lower() in (r[2] or "").lower())  # keyword literally in narrative?
    overlap = len(set(vids)&set(hids))
    out.append({"q":q[:46],"kw":kw,
        "bm25_greenable": f"{green}/{K}",           # >0 means BM25 will show green
        "vec_vs_hybrid_overlap": f"{overlap}/{K}",   # <5 means hybrid differs from vector
        "vector_cats":[r[1] for r in v],
        "hybrid_cats":[r[1] for r in h]})
dbutils.notebook.exit(json.dumps(out,indent=2))
