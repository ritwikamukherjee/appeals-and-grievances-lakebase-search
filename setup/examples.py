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

def snip(s,n=95): return (s or "").replace("\n"," ")[:n]

def run(q,kw,limit=3):
    qv=embed(q)
    vec=rows(f"SELECT plan_name, round((embedding <=> '{qv}')::numeric,4), narrative FROM cases ORDER BY embedding <=> '{qv}' LIMIT %s",(limit,))
    bm=rows(f"""SELECT plan_name, round((search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25'))::numeric,3), narrative
               FROM cases ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25') LIMIT %s""",(kw,kw,limit))
    hy=rows(f"""WITH vec AS (SELECT case_id,plan_name,narrative,row_number() OVER (ORDER BY embedding <=> '{qv}') rank FROM cases ORDER BY embedding <=> '{qv}' LIMIT 40),
                     kw AS (SELECT case_id,row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english',%s),'cases_search_bm25')) rank FROM cases WHERE search_tsv @@ plainto_tsquery('english',%s) LIMIT 40)
                SELECT v.plan_name, round((coalesce(1.0/(60+v.rank),0)+coalesce(1.0/(60+k.rank),0))::numeric,5), v.narrative
                FROM vec v LEFT JOIN kw k USING(case_id) ORDER BY 2 DESC LIMIT %s""",(kw,kw,limit))
    def fmt(rs):
        return [{"plan":r[0],"score":str(r[1]),"kw_in_text": kw.lower() in (r[2] or "").lower(),"narrative":snip(r[2])} for r in rs]
    return {"query":q,"keyword":kw,"vector":fmt(vec),"bm25":fmt(bm),"hybrid":fmt(hy)}

out=[
  run("an older adult keeps falling at home and cannot get around on their own","CO-197"),
  run("member cannot get their expensive arthritis biologic approved","J1745"),
]
dbutils.notebook.exit(json.dumps(out,indent=2))
