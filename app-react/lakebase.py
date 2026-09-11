"""
Lakebase access layer for the mode-comparison app.

Runs as the app's service principal (WorkspaceClient() with no args). It resolves
the production branch endpoint at runtime, mints a short-lived Lakebase OAuth
credential via the Postgres REST API, and connects with psycopg as the SP's
Postgres role. Query embeddings come from a Foundation Model serving endpoint.

The three search queries are ported verbatim from streamlit_app.py (the validated
reference implementation) so results match the notebook / lecture exactly.
"""
import os
import threading
import psycopg
from databricks.sdk import WorkspaceClient

PROJECT = os.getenv("LAKEBASE_PROJECT", "healthplan-appeals")
BRANCH = os.getenv("LAKEBASE_BRANCH", "production")
PGUSER = os.getenv("PGUSER", "")  # SP client id == its Postgres role name
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "databricks-gte-large-en")
DBNAME = os.getenv("LAKEBASE_DB", "databricks_postgres")

# Concept words that vector/semantic search tends to surface. Highlighted blue
# in the UI. Kept in sync with streamlit_app.py.
CONCEPTS = [
    "denied", "denial", "medically necessary", "prior authorization", "authorization",
    "not covered", "out of network", "out-of-network", "coverage", "experimental",
    "formulary", "step therapy", "reconsideration", "appeal", "wheelchair", "oxygen",
    "mobility", "MRI", "biologic", "infusion", "relapse", "stable", "home",
]

_wc_lock = threading.Lock()
_wc = None
_endpoint_cache = None


def wc() -> WorkspaceClient:
    global _wc
    if _wc is None:
        with _wc_lock:
            if _wc is None:
                _wc = WorkspaceClient()
    return _wc


def endpoint():
    """Resolve the production branch endpoint (host is dynamic). Cached."""
    global _endpoint_cache
    if _endpoint_cache is None:
        eps = wc().api_client.do(
            "GET", f"/api/2.0/postgres/projects/{PROJECT}/branches/{BRANCH}/endpoints"
        )["endpoints"]
        _endpoint_cache = eps[0]
    return _endpoint_cache


def get_conn():
    """Fresh psycopg connection using an app-SP OAuth credential."""
    w = wc()
    ep = endpoint()
    host = ep["status"]["hosts"]["host"]
    token = w.api_client.do(
        "POST", "/api/2.0/postgres/credentials", body={"endpoint": ep["name"]}
    )["token"]
    user = PGUSER or w.current_user.me().user_name
    return psycopg.connect(
        host=host, dbname=DBNAME, user=user, password=token,
        sslmode="require", autocommit=True, connect_timeout=15,
    )


def embed(text: str) -> str:
    """Query embedding -> pgvector literal."""
    r = wc().api_client.do(
        "POST", f"/serving-endpoints/{EMBED_MODEL}/invocations", body={"input": [text]}
    )
    vec = r["data"][0]["embedding"]
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"


def _rows(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


# Columns returned by every query, in this exact order. Kept identical across the
# three modes so _fmt can map them positionally; the per-mode score is appended last.
_COLS = (
    "case_id, service_category, denial_reason_code, denial_reason_desc, "
    "cpt_hcpcs_code, icd10_code, disposition, plan_name, line_of_business, "
    "member_id, filed_date, narrative"
)


# ---- Queries (score expressions + ORDER BY unchanged from streamlit_app.py) ----
def q_vector(conn, qvec, limit):
    return _rows(conn, f"""
        SELECT {_COLS},
               round((embedding <=> '{qvec}')::numeric, 4) AS score
        FROM cases ORDER BY embedding <=> '{qvec}' LIMIT %s""", (limit,))


def q_bm25(conn, kw, limit):
    return _rows(conn, f"""
        SELECT {_COLS},
               round((search_tsv <@> to_bm25query(to_tsvector('english', %s), 'cases_search_bm25'))::numeric, 3) AS score
        FROM cases
        ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', %s), 'cases_search_bm25')
        LIMIT %s""", (kw, kw, limit))


def q_hybrid(conn, qvec, kw, limit):
    # vec CTE now carries all display columns; RRF fusion math and the
    # plainto_tsquery keyword filter are unchanged.
    vec_cols = ", ".join(f"v.{c.strip()}" for c in _COLS.split(","))
    return _rows(conn, f"""
        WITH vec AS (
            SELECT {_COLS},
                   row_number() OVER (ORDER BY embedding <=> '{qvec}') AS rank
            FROM cases ORDER BY embedding <=> '{qvec}' LIMIT 40
        ),
        kw AS (
            SELECT case_id,
                   row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', %s), 'cases_search_bm25')) AS rank
            FROM cases WHERE search_tsv @@ plainto_tsquery('english', %s) LIMIT 40
        )
        SELECT {vec_cols},
               round((coalesce(1.0/(60+v.rank),0) + coalesce(1.0/(60+k.rank),0))::numeric, 5) AS score
        FROM vec v LEFT JOIN kw k USING (case_id)
        ORDER BY score DESC LIMIT %s""", (kw, kw, limit))


def _fmt(rows, score_label):
    out = []
    for r in rows:
        out.append({
            "case_id": r[0],
            "service_category": r[1],
            "denial_reason_code": r[2],
            "denial_reason_desc": r[3],
            "cpt_hcpcs_code": r[4],
            "icd10_code": r[5],
            "disposition": r[6],
            "plan_name": r[7],
            "line_of_business": r[8],
            "member_id": r[9],
            "filed_date": str(r[10]) if r[10] is not None else None,
            "narrative": r[11],
            "score": float(r[12]) if r[12] is not None else None,
            "score_label": score_label,
        })
    return out


def search(q: str, kw: str, limit: int, mode: str = "all"):
    """Run the requested modes against live Lakebase and return JSON-ready dict."""
    q = (q or "").strip()
    kw = (kw or "").strip()
    limit = max(1, min(int(limit or 5), 25))
    out = {"vector": [], "bm25": [], "hybrid": [], "concepts": CONCEPTS}

    qvec = embed(q) if q else None
    conn = get_conn()
    try:
        if mode in ("all", "vector") and qvec:
            out["vector"] = _fmt(q_vector(conn, qvec, limit), "dist")
        if mode in ("all", "bm25") and kw:
            out["bm25"] = _fmt(q_bm25(conn, kw, limit), "bm25")
        if mode in ("all", "hybrid") and qvec and kw:
            out["hybrid"] = _fmt(q_hybrid(conn, qvec, kw, limit), "rrf")
    finally:
        conn.close()
    return out


def selftest():
    """Startup self-test: prove the SP can mint a credential, connect, and query.
    Logged at startup so `databricks apps logs` shows whether SP->Lakebase works."""
    result = {"ok": False}
    try:
        ep = endpoint()
        result["endpoint"] = ep["name"]
        result["host"] = ep["status"]["hosts"]["host"]
    except Exception as e:
        result["error"] = f"endpoint list failed: {type(e).__name__}: {e}"
        return result
    try:
        conn = get_conn()
        try:
            n = _rows(conn, "SELECT count(*) FROM cases")[0][0]
            result["cases_rows"] = int(n)
            result["ok"] = True
        finally:
            conn.close()
    except Exception as e:
        result["error"] = f"connect/query failed: {type(e).__name__}: {e}"
        return result

    # Full path: embedding endpoint + all three search modes (matches UI defaults).
    try:
        r = search("member needs a mobility device to get around their home safely",
                   "wheelchair", 5, "all")
        result["search_counts"] = {
            "vector": len(r["vector"]), "bm25": len(r["bm25"]), "hybrid": len(r["hybrid"]),
        }
        top = r["hybrid"][0] if r["hybrid"] else None
        if top:
            result["hybrid_top"] = f'{top["plan_name"]} (rrf {top["score"]})'
    except Exception as e:
        result["search_error"] = f"{type(e).__name__}: {e}"
    return result
