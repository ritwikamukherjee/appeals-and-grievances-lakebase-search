# Databricks notebook source
# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
# Compound relevance = needs BOTH signals: right category (semantic) AND right
# denial code (exact token). This is where hybrid should beat vector (misses the
# exact code) and BM25 (misses the category), because CARC codes are cross-category.
import json, psycopg
from databricks.sdk import WorkspaceClient
w = WorkspaceClient(); ue = w.current_user.me().user_name
ep = w.api_client.do("GET","/api/2.0/postgres/projects/healthplan-appeals/branches/production/endpoints")["endpoints"][0]
host=ep["status"]["hosts"]["host"]; tok=w.api_client.do("POST","/api/2.0/postgres/credentials",body={"endpoint":ep["name"]})["token"]
conn=psycopg.connect(host=host,dbname="databricks_postgres",user=ue,password=tok,sslmode="require",autocommit=True)
def embed(t):
    r=w.api_client.do("POST","/serving-endpoints/databricks-gte-large-en/invocations",body={"input":[t]}); return "["+",".join(f"{float(x):.6f}" for x in r["data"][0]["embedding"])+"]"
def rows(sql,p=None):
    with conn.cursor() as c: c.execute(sql,p or ()); return c.fetchall()
K=10
def vec(qv,k): return rows(f"SELECT service_category,denial_reason_code FROM cases ORDER BY embedding <=> '{qv}' LIMIT %s",(k,))
def bm(kw,k): return rows(f"SELECT service_category,denial_reason_code FROM cases ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25') LIMIT %s",(kw,k))
def hy(qv,kw,k): return rows(f"""WITH v AS (SELECT case_id,service_category,denial_reason_code,row_number() OVER (ORDER BY embedding <=> '{qv}') r FROM cases ORDER BY embedding <=> '{qv}' LIMIT 60),
      k AS (SELECT case_id,row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25')) r FROM cases WHERE search_tsv @@ plainto_tsquery('english',%s) LIMIT 60)
      SELECT v.service_category,v.denial_reason_code FROM v LEFT JOIN k USING(case_id) ORDER BY (coalesce(1.0/(60+v.r),0)+coalesce(1.0/(60+k.r),0)) DESC LIMIT %s""",(kw,kw,k))
def prec(res,cat,code,k):
    top=res[:k]; return round(sum(1 for c,cd in top if c==cat and cd==code)/len(top),3) if top else 0.0

TESTS=[
 ("the imaging my doctor ordered was denied because prior approval was missing","CO-197","Imaging / Radiology","CO-197"),
 ("the mobility equipment the member needs at home was denied as not necessary","CO-50","Durable Medical Equipment","CO-50"),
 ("member's specialty drug was denied until they try a cheaper option first","CO-198","Specialty Pharmacy (Rx)","CO-198"),
 ("the surgery the doctor recommended was refused as not medically necessary","CO-50","Surgery","CO-50"),
]
rep=[]; agg={"vector":[],"bm25":[],"hybrid":[]}
for q,kw,cat,code in TESTS:
    qv=embed(q); v,b,h=vec(qv,K),bm(kw,K),hy(qv,kw,K)
    row={"query":q[:44],"kw":kw,"target":f"{cat} & {code}","vector":prec(v,cat,code,5),"bm25":prec(b,cat,code,5),"hybrid":prec(h,cat,code,5)}
    rep.append(row)
    for m in agg: agg[m].append(row[m])
avg={m:round(sum(x)/len(x),3) for m,x in agg.items()}
dbutils.notebook.exit(json.dumps({"metric":"precision@5 on (right category AND right denial code)","per_query":rep,"average":avg},indent=2))
