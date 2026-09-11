"""
Lakebase Search, Mode Comparison (Appeals & Grievances)

A Databricks App that runs the SAME query against the live Lakebase `cases`
table in three modes side by side, Vector (semantic), BM25 (keyword), and
Hybrid (RRF), so you can see how the result sets differ per mode.

Auth: runs as the app's service principal. It generates a short-lived Lakebase
OAuth credential via the Postgres REST API and connects with psycopg as the
SP's Postgres role. Query embeddings come from a Foundation Model endpoint.
"""
import os
import re
import html
import psycopg
import streamlit as st
from databricks.sdk import WorkspaceClient

PROJECT = os.getenv("LAKEBASE_PROJECT", "healthplan-appeals")
BRANCH = os.getenv("LAKEBASE_BRANCH", "production")
PGUSER = os.getenv("PGUSER", "")  # SP client id == its Postgres role name
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "databricks-gte-large-en")

st.set_page_config(page_title="Lakebase Search, Mode Comparison", layout="wide")

CONCEPTS = ["denied", "denial", "medically necessary", "prior authorization", "authorization",
            "not covered", "out of network", "out-of-network", "coverage", "experimental",
            "formulary", "step therapy", "reconsideration", "appeal", "wheelchair", "oxygen",
            "mobility", "MRI", "biologic", "infusion", "relapse", "stable", "home"]


@st.cache_resource
def _wc():
    return WorkspaceClient()


def _endpoint():
    w = _wc()
    eps = w.api_client.do(
        "GET", f"/api/2.0/postgres/projects/{PROJECT}/branches/{BRANCH}/endpoints")["endpoints"]
    return eps[0]


def get_conn():
    """Fresh psycopg connection using an app-SP OAuth credential."""
    w = _wc()
    ep = _endpoint()
    host = ep["status"]["hosts"]["host"]
    token = w.api_client.do("POST", "/api/2.0/postgres/credentials",
                            body={"endpoint": ep["name"]})["token"]
    user = PGUSER or w.current_user.me().user_name
    return psycopg.connect(host=host, dbname="databricks_postgres", user=user,
                           password=token, sslmode="require", autocommit=True)


def run(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def embed(text):
    w = _wc()
    r = w.api_client.do("POST", f"/serving-endpoints/{EMBED_MODEL}/invocations",
                        body={"input": [text]})
    vec = r["data"][0]["embedding"]
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"


def highlight(text, terms):
    text = (text or "").replace("\n", " ").strip()
    esc = html.escape(text)
    if terms:
        pat = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)
        esc = pat.sub(lambda m: f"<mark>{html.escape(m.group(0))}</mark>", esc)
    return esc


def card(plan, score, score_label, narrative, terms):
    st.markdown(
        f"""<div style="background:#F9F7F4;border-left:5px solid #1B5162;border-radius:6px;
        padding:10px 14px;margin-bottom:10px">
        <div style="font-weight:700;color:#0b2026">{html.escape(plan)}
        <span style="float:right;font-family:monospace;color:#1B5162">{score_label}: {score}</span></div>
        <div style="font-size:14px;color:#0b2026;margin-top:4px;line-height:1.5">{highlight(narrative, terms)}</div>
        </div>""",
        unsafe_allow_html=True)


# ---- Queries -------------------------------------------------------------
def q_vector(conn, qvec, limit):
    return run(conn, f"""
        SELECT plan_name, round((embedding <=> '{qvec}')::numeric, 4), narrative
        FROM cases ORDER BY embedding <=> '{qvec}' LIMIT %s""", (limit,))


def q_bm25(conn, kw, limit):
    return run(conn, f"""
        SELECT plan_name,
               round((search_tsv <@> to_bm25query(to_tsvector('english', %s), 'cases_search_bm25'))::numeric, 3),
               narrative
        FROM cases
        ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', %s), 'cases_search_bm25')
        LIMIT %s""", (kw, kw, limit))


def q_hybrid(conn, qvec, kw, limit):
    return run(conn, f"""
        WITH vec AS (
            SELECT case_id, plan_name, narrative,
                   row_number() OVER (ORDER BY embedding <=> '{qvec}') AS rank
            FROM cases ORDER BY embedding <=> '{qvec}' LIMIT 40
        ),
        kw AS (
            SELECT case_id,
                   row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', %s), 'cases_search_bm25')) AS rank
            FROM cases WHERE search_tsv @@ plainto_tsquery('english', %s) LIMIT 40
        )
        SELECT v.plan_name,
               round((coalesce(1.0/(60+v.rank),0) + coalesce(1.0/(60+k.rank),0))::numeric, 5),
               v.narrative
        FROM vec v LEFT JOIN kw k USING (case_id)
        ORDER BY 2 DESC LIMIT %s""", (kw, kw, limit))


# ---- UI ------------------------------------------------------------------
st.title("🔎 Lakebase Search, Mode Comparison")
st.caption("Same query, three modes, side by side, on the live Lakebase `cases` table "
           "(health-plan appeals & grievances). See how semantic, keyword, and hybrid retrieval differ.")

with st.form("search"):
    c1, c2, c3 = st.columns([3, 2, 1])
    query = c1.text_input("Natural-language query (semantic + hybrid)",
                          "member needs a mobility device to get around their home safely")
    keyword = c2.text_input("Keyword / code (BM25 + hybrid)", "wheelchair")
    limit = c3.slider("Results", 3, 10, 5)
    go = st.form_submit_button("Search", type="primary", use_container_width=True)

if go:
    try:
        conn = get_conn()
    except Exception as e:
        st.error(f"Could not connect to Lakebase: {e}")
        st.stop()

    qvec = embed(query) if query.strip() else None
    kw = keyword.strip()
    col_v, col_b, col_h = st.columns(3)

    with col_v:
        st.subheader("Vector (semantic)")
        st.caption("`embedding <=> query` · pgvector/`lakebase_ann`. Matches meaning, not words.")
        if qvec:
            for plan, score, narr in q_vector(conn, qvec, limit):
                card(plan, score, "dist", narr, [w for w in CONCEPTS])
        else:
            st.info("Enter a natural-language query.")

    with col_b:
        st.subheader("BM25 (keyword)")
        st.caption("`search_tsv <@> to_bm25query(...)` · `lakebase_bm25`. Exact tokens & codes.")
        if kw:
            for plan, score, narr in q_bm25(conn, kw, limit):
                card(plan, score, "bm25", narr, [kw])
        else:
            st.info("Enter a keyword or code.")

    with col_h:
        st.subheader("Hybrid (RRF)")
        st.caption("Reciprocal rank fusion of vector + BM25. Recall **and** precision.")
        if qvec and kw:
            for plan, score, narr in q_hybrid(conn, qvec, kw, limit):
                card(plan, score, "rrf", narr, CONCEPTS + [kw])
        else:
            st.info("Needs both a query and a keyword.")

    conn.close()
else:
    st.info("Enter a query and press **Search**. Try query "
            "*“couldn’t get my breathing machine covered”* with keyword *CPAP*, "
            "or keyword *CO-197* to see BM25 find an exact denial code that vector search misses.")
