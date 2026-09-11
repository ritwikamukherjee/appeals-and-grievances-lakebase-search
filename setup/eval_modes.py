# Databricks notebook source
# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
import json, psycopg
from databricks.sdk import WorkspaceClient
w = WorkspaceClient(); ue = w.current_user.me().user_name
ep = w.api_client.do("GET","/api/2.0/postgres/projects/healthplan-appeals/branches/production/endpoints")["endpoints"][0]
host = ep["status"]["hosts"]["host"]
tok = w.api_client.do("POST","/api/2.0/postgres/credentials",body={"endpoint":ep["name"]})["token"]
conn = psycopg.connect(host=host,dbname="databricks_postgres",user=ue,password=tok,sslmode="require",autocommit=True)

def embed(t):
    r=w.api_client.do("POST","/serving-endpoints/databricks-gte-large-en/invocations",body={"input":[t]})
    return "["+",".join(f"{float(x):.6f}" for x in r["data"][0]["embedding"])+"]"
def rows(sql,p=None):
    with conn.cursor() as c: c.execute(sql,p or ()); return c.fetchall()

K = 10
def vec_cats(qv,k):
    return [r[0] for r in rows(f"SELECT service_category FROM cases ORDER BY embedding <=> '{qv}' LIMIT %s",(k,))]
def bm_cats(kw,k):
    return [r[0] for r in rows(f"""SELECT service_category FROM cases
        ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25') LIMIT %s""",(kw,k))]
def hy_cats(qv,kw,k):
    return [r[0] for r in rows(f"""WITH vec AS (SELECT case_id,service_category,row_number() OVER (ORDER BY embedding <=> '{qv}') rank FROM cases ORDER BY embedding <=> '{qv}' LIMIT 60),
                 kw AS (SELECT case_id,row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25')) rank FROM cases WHERE search_tsv @@ plainto_tsquery('english',%s) LIMIT 60)
            SELECT v.service_category FROM vec v LEFT JOIN kw k USING(case_id)
            ORDER BY (coalesce(1.0/(60+v.rank),0)+coalesce(1.0/(60+k.rank),0)) DESC LIMIT %s""",(kw,kw,k))]

def prec(cats, target, k):
    top = cats[:k]
    return round(sum(1 for c in top if c == target)/len(top), 3) if top else 0.0

# (query, keyword, target category). Mix of paraphrase-heavy and code/term-heavy.
TESTS = [
 ("an older adult keeps falling at home and cannot get around on their own","wheelchair","Durable Medical Equipment"),
 ("the member's mental health treatment was stopped before they were ready","therapy","Behavioral Health"),
 ("the doctor ordered a scan of the head but the plan refused it","MRI","Imaging / Radiology"),
 ("member cannot get their expensive autoimmune biologic infusion approved","J1745","Specialty Pharmacy (Rx)"),
 ("the operation the surgeon recommended was turned down","knee replacement","Surgery"),
 ("member was billed for a trip to the emergency room","emergency","Emergency / ER"),
]

report=[]; agg={"vector":[],"bm25":[],"hybrid":[]}
for q,kw,tgt in TESTS:
    qv=embed(q)
    vc,bc,hc = vec_cats(qv,K), bm_cats(kw,K), hy_cats(qv,kw,K)
    row={"query":q[:48],"keyword":kw,"target":tgt,
         "vector_p5":prec(vc,tgt,5),"bm25_p5":prec(bc,tgt,5),"hybrid_p5":prec(hc,tgt,5)}
    report.append(row)
    agg["vector"].append(row["vector_p5"]); agg["bm25"].append(row["bm25_p5"]); agg["hybrid"].append(row["hybrid_p5"])

avg={m:round(sum(v)/len(v),3) for m,v in agg.items()}
wins={m:sum(1 for i in range(len(TESTS)) if agg[m][i]==max(agg["vector"][i],agg["bm25"][i],agg["hybrid"][i])) for m in agg}
dbutils.notebook.exit(json.dumps({"per_query":report,"avg_precision@5":avg,"top_or_tied_count":wins},indent=2))
