#!/usr/bin/env python3
"""Assemble the reskinned lecture notebook as a Databricks source .py file.

Authoring the rich %md-sandbox HTML slides with correct `# MAGIC ` prefixes by
hand is error-prone, so we define clean cells here and emit the prefixed source.
Slides follow the html-slide-notebook-generator design system (ds-banner /
ds-card / ds-callout classes, approved palette, 14pt floor).

Run:  python3 build_notebook.py   ->  Lakebase-Search-Appeals.py
"""
import os

CELLS = []


def md(html):
    CELLS.append(("md", html.strip("\n")))


def code(src):
    CELLS.append(("code", src.strip("\n")))


# ===========================================================================
# TITLE
# ===========================================================================
md(r"""
%md-sandbox
<div class="bnr-wrap">
<style>
.bnr-wrap { font-family: sans-serif; max-width: 1100px; margin: 0 auto; display:flex; flex-direction:column; gap:20px; }
.bnr-wrap * { box-sizing: border-box; }
.ds-banner { display:flex; align-items:center; gap:20px; width:100%; border-radius:10px; padding:28px 32px; background:var(--bnr-bg); border-left:8px solid var(--bnr-accent); box-shadow:0 2px 10px rgba(27,49,57,0.08); }
.ds-banner.info { --bnr-bg:#1B5162; --bnr-accent:#4299E0; }
.ds-banner-icon { width:64px; height:64px; border-radius:50%; flex-shrink:0; background:#4299E0; color:#fff; font-size:30pt; font-weight:700; display:flex; align-items:center; justify-content:center; }
.ds-banner-title { font-size:24pt; font-weight:700; color:#fff; line-height:1.2; margin-bottom:6px; }
.ds-banner-tagline { font-size:15pt; color:#F9F7F4; line-height:1.45; }
</style>
<div class="ds-banner info">
  <div class="ds-banner-icon">&#9906;</div>
  <div>
    <div class="ds-banner-title">Lakebase Search: Contextual Lookup for Appeals &amp; Grievances</div>
    <div class="ds-banner-tagline">Semantic + keyword + hybrid retrieval inside the operational Postgres that already powers your app. No separate search cluster, no ETL out of your system of record.</div>
  </div>
</div>
</div>
""")

# ===========================================================================
# THE PROBLEM
# ===========================================================================
md(r"""
%md-sandbox
<div class="cw">
<style>
.cw { font-family: sans-serif; max-width: 1100px; margin: 0 auto; color:#0b2026; }
.cw * { box-sizing: border-box; }
.ds-row { display:flex; gap:24px; align-items:stretch; flex-wrap:wrap; margin-top:6px; }
.ds-row > * { flex:1; min-width:240px; }
.ds-card { background:#F9F7F4; border-radius:8px; box-shadow:0 2px 8px rgba(27,49,57,0.06); padding:22px; border-top:8px solid var(--accent,#4299E0); }
.blue{--accent:#4299E0;} .green{--accent:#00A972;} .coral{--accent:#FF5F46;} .amber{--accent:#FFAB00;}
.ds-card-label { font-size:14pt; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:var(--accent); margin-bottom:4px; }
.ds-card-title { font-size:18pt; font-weight:700; line-height:1.25; margin:0 0 8px; }
.ds-card-para { font-size:14pt; color:#0b2026; line-height:1.55; margin:0; }
.h { font-size:20pt; font-weight:700; margin:0 0 4px; }
.sub { font-size:14pt; color:#5A6F77; margin:0 0 6px; }
</style>
<div class="h">A member-services rep needs the right prior case, fast</div>
<div class="sub">"Find past appeals like this one" is the everyday query. The narrative is free text; the codes are structured. Each search style alone leaves cases on the table.</div>
<div class="ds-row">
  <div class="ds-card coral">
    <div class="ds-card-label">Keyword only</div>
    <div class="ds-card-title">Misses paraphrases</div>
    <div class="ds-card-para">A rep searches for the word <b>infusion</b>, but the matching case says "IV biologic." Same meaning, different words, so keyword search misses it.</div>
  </div>
  <div class="ds-card blue">
    <div class="ds-card-label">Vector only</div>
    <div class="ds-card-title">Misses exact terms</div>
    <div class="ds-card-para">Semantic search blends everything with a similar meaning and does not lock onto the exact term the rep typed, so precise matches get diluted.</div>
  </div>
  <div class="ds-card green">
    <div class="ds-card-label">Hybrid</div>
    <div class="ds-card-title">Best of both</div>
    <div class="ds-card-para">Reciprocal rank fusion blends semantic recall with exact-token precision. The member's language <i>and</i> the codes, in one ranked list.</div>
  </div>
</div>
</div>
""")

# ===========================================================================
# PIPELINE AT A GLANCE (step-flow)
# ===========================================================================
md(r"""
%md-sandbox
<div class="cw">
<style>
.cw { font-family: sans-serif; max-width: 1150px; margin: 0 auto; color:#0b2026; }
.cw * { box-sizing: border-box; }
.h { font-size:20pt; font-weight:700; margin:0 0 14px; }
.flow-grid { display:grid; grid-template-columns:1fr auto 1fr auto 1fr auto 1fr auto 1fr; gap:0; align-items:stretch; }
.flow-step { background:#F9F7F4; border:3px solid var(--accent,#4299E0); border-radius:10px; padding:16px 12px; box-shadow:0 2px 8px rgba(27,49,57,0.08); text-align:center; min-width:0; }
.flow-num { font-size:26pt; font-weight:800; color:var(--accent,#4299E0); line-height:1; margin-bottom:8px; }
.flow-label { font-size:14pt; font-weight:600; color:#0b2026; line-height:1.35; }
.flow-arrow { display:flex; align-items:center; justify-content:center; color:#618794; font-size:22pt; line-height:1; }
</style>
<div class="h">The pipeline at a glance</div>
<div class="flow-grid">
  <div class="flow-step" style="--accent:#4299E0;"><div class="flow-num">1</div><div class="flow-label">Load appeals<br>into Lakebase</div></div>
  <div class="flow-arrow">&rarr;</div>
  <div class="flow-step" style="--accent:#00A972;"><div class="flow-num">2</div><div class="flow-label">Embed narratives<br>(gte-large-en)</div></div>
  <div class="flow-arrow">&rarr;</div>
  <div class="flow-step" style="--accent:#FFAB00;"><div class="flow-num">3</div><div class="flow-label">Build vector +<br>BM25 indexes</div></div>
  <div class="flow-arrow">&rarr;</div>
  <div class="flow-step" style="--accent:#FF5F46;"><div class="flow-num">4</div><div class="flow-label">Search three ways<br>in one query</div></div>
  <div class="flow-arrow">&rarr;</div>
  <div class="flow-step" style="--accent:#1B5162;"><div class="flow-num">5</div><div class="flow-label">Brief the<br>member services rep</div></div>
</div>
</div>
""")

# ===========================================================================
# SETUP
# ===========================================================================
md(r"""
%md
### Setup: connect to Lakebase and load the demo helpers
Run this once. It connects to the `healthplan-appeals` Lakebase project (production
branch), and defines `embed_text()`, `show()`, `show_hybrid()`, and `run_sql()` used
throughout. The connection uses the Postgres REST API via the SDK's `api_client`, so
it is independent of the in-workspace SDK version.
""")

code(r'''
# MAGIC %pip install --quiet "psycopg[binary]"
# MAGIC dbutils.library.restartPython()
''')

code(r'''
import re, psycopg
from html import escape as _esc
from databricks.sdk import WorkspaceClient

PROJECT_ID, BRANCH = "healthplan-appeals", "production"
EMBEDDING_MODEL = "databricks-gte-large-en"        # 1024-dim, matches stored vectors
SUMMARY_MODEL   = "databricks-claude-haiku-4-5"    # AI summary step (Act D)

w = WorkspaceClient()
user_email = w.current_user.me().user_name

def reconnect():
    """(Re)open a connection to the production branch endpoint. Enabling Lakebase
    Search restarts the project compute and drops connections, so call this to heal."""
    global lb_conn
    eps = w.api_client.do("GET", f"/api/2.0/postgres/projects/{PROJECT_ID}/branches/{BRANCH}/endpoints")["endpoints"]
    ep = eps[0]
    host = ep["status"]["hosts"]["host"]
    token = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": ep["name"]})["token"]
    lb_conn = psycopg.connect(host=host, dbname="databricks_postgres", user=user_email,
                              password=token, sslmode="require", autocommit=True)
    return lb_conn

reconnect()

def run_sql(statements):
    """Run one SQL string or a list; heal a dropped connection once. Returns rows of the last stmt."""
    stmts = [statements] if isinstance(statements, str) else list(statements)
    for attempt in range(2):
        try:
            rows = None
            with lb_conn.cursor() as cur:
                for s in stmts:
                    cur.execute(s)
                    if cur.description is not None:
                        rows = cur.fetchall()
            return rows
        except (psycopg.OperationalError, psycopg.InterfaceError):
            if attempt == 0: reconnect()
            else: raise

def embed_text(text):
    """Embed one string via the Foundation Model; returns a pgvector literal."""
    r = w.serving_endpoints.query(name=EMBEDDING_MODEL, input=[text])
    return "[" + ",".join(f"{float(x):.6f}" for x in r.data[0].embedding) + "]"

print("connected as", user_email, "| rows:", run_sql("SELECT count(*) FROM cases")[0][0])
''')

# render helpers (adapted from the course's Includes; healthcare concept words)
code(r'''
# Result renderers: highlight WHY each case ranked. Green = keyword/code match,
# blue = semantic concept. Row shapes: show() -> (label, score, narrative);
# show_hybrid() -> (label, rrf_score, narrative).
CONCEPT_WORDS = ["denied","denial","medically necessary","prior authorization","authorization","medication","autoimmune","residential",
                 "not covered","out of network","out-of-network","coverage","experimental",
                 "formulary","step therapy","reconsideration","appeal","wheelchair","oxygen",
                 "MRI","biologic","infusion","relapse","stable"]

def _highlight(text, pat, color, width, max_fragments):
    text = (text or "").replace("\n", " ").strip()
    if not pat:
        return _esc(text[:width]) + ("..." if len(text) > width else "")
    matches = list(pat.finditer(text))
    if not matches:
        return _esc(text[:width]) + ("..." if len(text) > width else "")
    frags, used = [], set()
    for m in matches:
        if len(frags) >= max_fragments: break
        c = m.start()
        if any(abs(c - u) < width // 2 for u in used): continue
        used.add(c)
        start = max(0, c - width // 3); end = min(len(text), start + width)
        out = _esc(text[start:end])
        out = pat.sub(lambda mm: f'<span style="background:{color[0]};color:{color[1]};font-weight:700;padding:1px 5px;border-radius:3px">' + _esc(mm.group(0)) + "</span>", out)
        frags.append(("..." if start > 0 else "") + out + ("..." if end < len(text) else ""))
    return " &hellip; ".join(frags)

def _table(rows, head, cell_fn, score_idx=1, mono_score=True, legend=""):
    if not rows:
        displayHTML("<p style='font-size:14pt;color:#5A6F77'>(no rows)</p>"); return
    th = 'style="text-align:left;padding:9px 14px;font-size:13.5pt;color:#fff;background:#1B5162;font-weight:700"'
    td = 'style="padding:9px 14px;font-size:14pt;color:#0b2026;border-bottom:1px solid #ECEAE6;vertical-align:top"'
    tdm = 'style="padding:9px 14px;font-size:13.5pt;color:#1B5162;font-family:Menlo,Monaco,monospace;border-bottom:1px solid #ECEAE6;vertical-align:top"'
    body = ""
    for i, r in enumerate(rows, 1):
        body += f"<tr><td {td}><strong>{i}</strong></td><td {td}>{_esc(str(r[0]))}</td>"
        if score_idx is not None:
            body += f"<td {tdm if mono_score else td}>{_esc(str(r[score_idx]))}</td>"
        body += f"<td {td}>{cell_fn(r[-1])}</td></tr>"
    displayHTML('<table style="border-collapse:collapse;width:100%;max-width:1200px;'
                "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
                'box-shadow:0 2px 10px rgba(11,32,38,.08);border-radius:8px;overflow:hidden">'
                f"<thead><tr>{''.join(f'<th {th}>'+h+'</th>' for h in head)}</tr></thead>"
                f"<tbody>{body}</tbody></table>{legend}")

def show(rows, concepts=CONCEPT_WORDS, score_label="Distance", width=220, max_fragments=3):
    pat = re.compile("|".join(re.escape(w) for w in concepts), re.IGNORECASE) if concepts else None
    _table(rows, ["#", "Plan", score_label, "Case narrative"],
           lambda t: _highlight(t, pat, ("#A7E8C6", "#0B4D33"), width, max_fragments))

def show_hybrid(rows, kw_words, vec_words, width=220, max_fragments=3):
    kw = re.compile("|".join(re.escape(w) for w in kw_words), re.IGNORECASE)
    vec = re.compile("|".join(re.escape(w) for w in vec_words), re.IGNORECASE)
    both = re.compile("|".join(re.escape(w) for w in kw_words + vec_words), re.IGNORECASE)
    def cell(text):
        text = (text or "").replace("\n", " ").strip()
        ms = list(both.finditer(text))
        if not ms: return _esc(text[:width]) + ("..." if len(text) > width else "")
        frags, used = [], set()
        for m in ms:
            if len(frags) >= max_fragments: break
            c = m.start()
            if any(abs(c - u) < width // 2 for u in used): continue
            used.add(c)
            start = max(0, c - width // 3); end = min(len(text), start + width)
            out = _esc(text[start:end])
            out = kw.sub(lambda mm: '<span style="background:#A7E8C6;color:#0B4D33;font-weight:700;padding:1px 5px;border-radius:3px">' + _esc(mm.group(0)) + "</span>", out)
            out = vec.sub(lambda mm: '<span style="background:#BFD9F2;color:#0B3D6B;font-weight:700;padding:1px 5px;border-radius:3px">' + _esc(mm.group(0)) + "</span>", out)
            frags.append(("..." if start > 0 else "") + out + ("..." if end < len(text) else ""))
        return " &hellip; ".join(frags)
    legend = ('<div style="margin:8px 0 0;font-size:13pt;color:#5A6F77">'
              '<span style="background:#A7E8C6;color:#0B4D33;font-weight:700;padding:1px 6px;border-radius:3px">green</span> = keyword / code match &nbsp; '
              '<span style="background:#BFD9F2;color:#0B3D6B;font-weight:700;padding:1px 6px;border-radius:3px">blue</span> = semantic concept</div>')
    _table(rows, ["#", "Plan", "RRF", "Case narrative"], cell, legend=legend)

print("renderers loaded: show(), show_hybrid()")
''')

# ===========================================================================
# ACT A - VECTOR
# ===========================================================================
md(r"""
%md-sandbox
<div class="cw">
<style>
.cw { font-family: sans-serif; max-width:1100px; margin:0 auto; color:#0b2026; }
.ds-banner2 { display:flex; align-items:center; gap:16px; border-radius:10px; padding:18px 24px; background:rgba(66,153,224,0.10); border-left:8px solid #4299E0; box-shadow:0 2px 8px rgba(27,49,57,0.06); }
.ds-banner2 .n { width:44px;height:44px;border-radius:50%;background:#4299E0;color:#fff;font-size:18pt;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.ds-banner2 .t { font-size:20pt;font-weight:700; } .ds-banner2 .s { font-size:14pt;color:#5A6F77; }
</style>
<div class="ds-banner2"><div class="n">A</div><div><div class="t">Semantic (vector) search</div>
<div class="s">The query shares almost no words with the cases it should find. Embeddings match on <i>meaning</i>.</div></div></div>
</div>
""")

code(r'''
# Natural-language query with NO overlapping keywords with the target cases.
q = "a member with a serious autoimmune condition cannot get the medication they need"
qv = embed_text(q)
rows = run_sql(f"""
    SELECT plan_name,
           round((embedding <=> '{qv}')::numeric, 4) AS distance,
           narrative
    FROM cases
    ORDER BY embedding <=> '{qv}'
    LIMIT 6
""")
print("QUERY:", q)
show(rows)   # green highlights show WHY each ranked, even with no shared query words
''')

# ===========================================================================
# ENABLE SEARCH (toggle gate)
# ===========================================================================
md(r"""
%md-sandbox
<div class="bnr-wrap">
<style>
.bnr-wrap { font-family:sans-serif; max-width:1100px; margin:0 auto; }
.ds-banner { display:flex; align-items:center; gap:20px; border-radius:10px; padding:22px 28px; background:rgba(255,171,0,0.12); border-left:8px solid #FFAB00; box-shadow:0 2px 10px rgba(27,49,57,0.08); }
.ds-banner-icon { width:56px;height:56px;border-radius:50%;background:#FFAB00;color:#0b2026;font-size:26pt;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.ds-banner-title { font-size:20pt;font-weight:700;color:#0b2026;margin-bottom:4px; }
.ds-banner-tagline { font-size:14pt;color:#5E7077;line-height:1.5; }
</style>
<div class="ds-banner">
  <div class="ds-banner-icon">&#9888;</div>
  <div>
    <div class="ds-banner-title">One-time: enable Lakebase Search (Beta) on this project</div>
    <div class="ds-banner-tagline">BM25 and hybrid need the <code>lakebase_vector</code> and <code>lakebase_text</code> extensions, which load via <code>shared_preload_libraries</code>. Turn on <b>Lakebase Search</b> in the project settings UI (restarts compute in ~1 min). The next cell builds the Search indexes live.</div>
  </div>
</div>
</div>
""")

code(r'''
# Build the Lakebase Search objects (runs after the Beta toggle is enabled).
# - lakebase_ann: IVF + RaBitQ ANN index (Lakebase-native, storage-backed).
# - lakebase_bm25 index (from lakebase_text) over a tsvector that folds the
#   narrative PLUS the structured codes, so exact-code keyword search works.
run_sql([
    "CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE",
    "CREATE EXTENSION IF NOT EXISTS lakebase_text",
    """ALTER TABLE cases ADD COLUMN IF NOT EXISTS search_tsv tsvector
         GENERATED ALWAYS AS (to_tsvector('english',
           coalesce(narrative,'') || ' ' || coalesce(denial_reason_code,'') || ' ' ||
           coalesce(cpt_hcpcs_code,'') || ' ' || coalesce(icd10_code,'') || ' ' ||
           coalesce(service_category,''))) STORED""",
    "CREATE INDEX IF NOT EXISTS cases_embedding_ann ON cases USING lakebase_ann (embedding vector_cosine_ops)",
    "CREATE INDEX IF NOT EXISTS cases_search_bm25 ON cases USING lakebase_bm25 (search_tsv)",
    "ANALYZE cases",
])
print("Lakebase Search indexes built: lakebase_ann (vector) + lakebase_bm25 (keyword)")
''')

# ===========================================================================
# ACT B - BM25
# ===========================================================================
md(r"""
%md-sandbox
<div class="cw">
<style>
.cw { font-family:sans-serif; max-width:1100px; margin:0 auto; color:#0b2026; }
.ds-banner2 { display:flex; align-items:center; gap:16px; border-radius:10px; padding:18px 24px; background:rgba(0,169,114,0.10); border-left:8px solid #00A972; box-shadow:0 2px 8px rgba(27,49,57,0.06); }
.ds-banner2 .n { width:44px;height:44px;border-radius:50%;background:#00A972;color:#fff;font-size:18pt;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.ds-banner2 .t { font-size:20pt;font-weight:700; } .ds-banner2 .s { font-size:14pt;color:#5A6F77; }
</style>
<div class="ds-banner2"><div class="n">B</div><div><div class="t">Keyword (BM25) search</div>
<div class="s">Exact tokens win here. A specific term like <code>infusion</code> (or a denial code) that vector search does not weight the way literal keyword matching does.</div></div></div>
</div>
""")

code(r'''
# Exact keyword lookup: BM25 nails the literal token; the same word embedded is diffuse.
term = "infusion"
rows = run_sql(f"""
    SELECT plan_name,
           round((search_tsv <@> to_bm25query(to_tsvector('english', '{term}'), 'cases_search_bm25'))::numeric, 3) AS bm25,
           narrative
    FROM cases
    ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', '{term}'), 'cases_search_bm25')
    LIMIT 6
""")
print("KEYWORD QUERY:", term)
show(rows, concepts=[term, "biologic", "medication", "denied"], score_label="BM25")
''')

# ===========================================================================
# ACT C - HYBRID
# ===========================================================================
md(r"""
%md-sandbox
<div class="cw">
<style>
.cw { font-family:sans-serif; max-width:1100px; margin:0 auto; color:#0b2026; }
.ds-banner2 { display:flex; align-items:center; gap:16px; border-radius:10px; padding:18px 24px; background:rgba(255,95,70,0.10); border-left:8px solid #FF5F46; box-shadow:0 2px 8px rgba(27,49,57,0.06); }
.ds-banner2 .n { width:44px;height:44px;border-radius:50%;background:#FF5F46;color:#fff;font-size:18pt;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.ds-banner2 .t { font-size:20pt;font-weight:700; } .ds-banner2 .s { font-size:14pt;color:#5A6F77; }
</style>
<div class="ds-banner2"><div class="n">C</div><div><div class="t">Hybrid search (Reciprocal Rank Fusion)</div>
<div class="s">Rank by vector and by BM25 independently, then fuse: <code>1/(60+rank_vec) + 1/(60+rank_kw)</code>.</div></div></div>
</div>
""")

code(r'''
# A real rep query: paraphrased need + an exact term. Hybrid catches both.
q = "a member with a serious autoimmune condition cannot get the medication they need"
kw = "infusion"
qv = embed_text(q)
rows = run_sql(f"""
    WITH vec AS (
        SELECT case_id, plan_name, narrative,
               row_number() OVER (ORDER BY embedding <=> '{qv}') AS rank
        FROM cases ORDER BY embedding <=> '{qv}' LIMIT 30
    ),
    kw AS (
        SELECT case_id,
               row_number() OVER (ORDER BY search_tsv <@> to_bm25query(to_tsvector('english', '{kw}'), 'cases_search_bm25')) AS rank
        FROM cases
        WHERE search_tsv @@ plainto_tsquery('english', '{kw}')
        LIMIT 30
    )
    SELECT v.plan_name,
           round((coalesce(1.0/(60+v.rank),0) + coalesce(1.0/(60+k.rank),0))::numeric, 5) AS rrf,
           v.narrative
    FROM vec v LEFT JOIN kw k USING (case_id)
    ORDER BY rrf DESC
    LIMIT 6
""")
print("HYBRID QUERY:", q, "| keyword:", kw)
show_hybrid(rows, kw_words=[kw], vec_words=["biologic","medication","autoimmune","condition","stable","progressing","denied"])
''')

# ===========================================================================
# UNDER THE HOOD
# ===========================================================================
md(r"""
%md-sandbox
<div class="cw">
<style>
.cw { font-family:sans-serif; max-width:1100px; margin:0 auto; color:#0b2026; }
.ds-row { display:flex; gap:24px; align-items:stretch; flex-wrap:wrap; margin-top:6px; }
.ds-row > * { flex:1; min-width:240px; }
.ds-card { background:#F9F7F4; border-radius:8px; box-shadow:0 2px 8px rgba(27,49,57,0.06); padding:22px; border-top:8px solid var(--accent,#4299E0); }
.blue{--accent:#4299E0;} .green{--accent:#00A972;} .amber{--accent:#FFAB00;}
.ds-card-title { font-size:18pt; font-weight:700; margin:0 0 8px; }
.ds-card ul { margin:8px 0 0; padding-left:20px; font-size:14pt; line-height:1.55; }
.ds-card li { margin-bottom:10px; }
.h { font-size:20pt; font-weight:700; margin:0 0 6px; }
</style>
<div class="h">What Lakebase Search adds on top of pgvector</div>
<div class="ds-row">
  <div class="ds-card blue"><div class="ds-card-title">lakebase_ann (vector)</div>
    <ul><li>IVF partitioning + RaBitQ quantization</li><li>Storage-backed, built for scale-to-zero and tiered storage</li><li>pgvector-compatible: same <code>vector</code> types and <code>&lt;=&gt;</code> operator</li></ul></div>
  <div class="ds-card green"><div class="ds-card-title">lakebase_bm25 (keyword)</div>
    <ul><li>True BM25 relevance ranking, not <code>ts_rank</code></li><li>Block-Max WAND top-K pushdown</li><li>Query via <code>&lt;@&gt;</code> + <code>to_bm25query(...)</code></li></ul></div>
  <div class="ds-card amber"><div class="ds-card-title">Hybrid</div>
    <ul><li>Reciprocal rank fusion in plain SQL</li><li>Runs inside the OLTP database, so joins, filters, and transactions all still apply</li><li>No separate search service, no data copy</li></ul></div>
</div>
</div>
""")

# ===========================================================================
# ACT D - AI SUMMARY
# ===========================================================================
md(r"""
%md
### Act D: turn the retrieved cases into a rep-ready summary
Hybrid search returns the right cases; a Foundation Model turns them into a short
brief the rep can act on. This is the contextual-lookup pattern an app would run.
""")

code(r'''
# Summarize the top hybrid matches for the member-services rep.
q = "a member with a serious autoimmune condition cannot get the medication they need"
qv = embed_text(q)
top = run_sql(f"""
    SELECT plan_name, disposition, denial_reason_code, narrative
    FROM cases ORDER BY embedding <=> '{qv}' LIMIT 5
""")
context = "\n".join(f"- [{r[0]} | {r[1]} | {r[2]}] {r[3]}" for r in top)
prompt = ("You are helping a health-plan member-services rep. Given these similar prior "
          "appeal/grievance cases, write a 3-bullet brief: the common theme, how they were "
          "typically resolved, and one thing to check on the new case. Be concise.\n\n" + context)
resp = w.api_client.do("POST", f"/serving-endpoints/{SUMMARY_MODEL}/invocations",
    body={"messages": [{"role": "user", "content": prompt}], "max_tokens": 300})
print(resp["choices"][0]["message"]["content"])
''')

# ===========================================================================
# TAKEAWAY
# ===========================================================================
md(r"""
%md-sandbox
<div class="cw">
<style>
.cw { font-family:sans-serif; max-width:1100px; margin:0 auto; color:#0b2026; }
.ds-callout { border-left:6px solid var(--accent,#00A972); border-radius:8px; padding:20px 26px; background:var(--tint,rgba(0,169,114,0.10)); box-shadow:0 2px 8px rgba(27,49,57,0.06); font-size:14pt; line-height:1.55; }
.ds-eyebrow { font-size:14pt; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; color:#00A972; margin-bottom:6px; }
.ds-callout-title { font-size:16pt; font-weight:700; margin-bottom:10px; }
.ds-callout ul { margin:0; padding-left:20px; } .ds-callout li { margin-bottom:10px; }
</style>
<div class="ds-callout">
  <div class="ds-eyebrow">Key Takeaway</div>
  <div class="ds-callout-title">Contextual lookup belongs where your app's data already lives.</div>
  <ul>
    <li>Embeddings and codes sit next to member/claims data in Lakebase Postgres, so you search with normal <code>WHERE</code> filters, joins, and transactions.</li>
    <li>Hybrid retrieval (semantic recall + exact-code precision) with no separate vector service and no ETL out of the system of record.</li>
    <li>Enable it per project with one Beta toggle; your app queries it over the same connection it already uses.</li>
  </ul>
</div>
</div>
""")


# ===========================================================================
# KNOWLEDGE CHECK
# ===========================================================================
md(r"""
%md-sandbox
This knowledge check is **ungraded**, a quick self-check on the three search modes. Pick an answer and click **Check**.

<style>
.qz-shell{display:flex;border:1px solid #DCE0E2;border-radius:12px;overflow:hidden;min-height:360px;font-family:sans-serif}
.qz-nav{flex:0 0 200px;background:#F8F9FC;border-right:1px solid #DCE0E2;padding:12px 0;display:flex;flex-direction:column;justify-content:space-between}
.qz-nav-list{display:flex;flex-direction:column;gap:2px}
.qz-nav-item{padding:10px 16px;font-size:14pt;font-weight:500;color:#5E7077;cursor:pointer;user-select:none;display:flex;align-items:center;gap:10px;transition:background .12s,color .12s}
.qz-nav-item:hover{background:#EEEDE9;color:#0b2026}
.qz-nav-item.active{background:#F8F9FC;color:#0b2026;border-right:3px solid #4299E0}
.qz-dot{width:10px;height:10px;border-radius:50%;border:2px solid #C2C2C2;flex-shrink:0;transition:background .2s,border-color .2s}
.qz-dot.answered{border-color:#4299E0;background:#4299E0}
.qz-dot.correct{border-color:#00A972;background:#00A972}
.qz-dot.wrong{border-color:#FF5F46;background:#FF5F46}
.qz-main{flex:1;padding:24px 28px;display:flex;flex-direction:column;justify-content:center}
.qz-q{font-size:14pt;font-weight:500;color:#0b2026;margin-bottom:16px;line-height:1.5}
.qz-q code{background:#EEEDE9;padding:1px 5px;border-radius:4px;font-size:14pt}
.qz-opts{display:flex;flex-direction:column;gap:10px}
.qz-opt{display:flex;align-items:center;gap:12px;padding:12px 16px;border-radius:8px;border:1px solid #DCE0E2;background:#fff;cursor:pointer;font-size:14pt;color:#0b2026;transition:background .12s,border-color .12s;user-select:none}
.qz-opt:hover{background:#EEEDE9;border-color:#C2C2C2}
.qz-opt.selected{border-color:#4299E0;background:#F8F9FC;font-weight:500}
.qz-opt.right{border-color:#00A972;background:rgba(0,169,114,0.10);color:#00A972;font-weight:500}
.qz-opt.wrong-pick{border-color:#FF5F46;background:rgba(255,95,70,0.10);color:#FF5F46}
.qz-opt.locked{pointer-events:none}
.qz-radio{width:18px;height:18px;border-radius:50%;border:2px solid #C2C2C2;flex-shrink:0;display:flex;align-items:center;justify-content:center}
.qz-opt.selected .qz-radio{border-color:#4299E0;background:#4299E0}
.qz-opt.right .qz-radio{border-color:#00A972;background:#00A972}
.qz-opt.wrong-pick .qz-radio{border-color:#FF5F46;background:#FF5F46}
.qz-radio::after{content:'';width:8px;height:8px;border-radius:50%;background:#fff;display:none}
.qz-opt.selected .qz-radio::after,.qz-opt.right .qz-radio::after,.qz-opt.wrong-pick .qz-radio::after{display:block}
.qz-fb{margin-top:14px;padding:12px 16px;border-radius:8px;font-size:14pt;line-height:1.5;display:none}
.qz-fb.show{display:block}
.qz-fb.ok{background:rgba(0,169,114,0.10);color:#00A972}
.qz-fb.no{background:rgba(255,95,70,0.10);color:#98102A}
.qz-grade-btn{padding:10px 24px;border:none;border-radius:8px;font-size:14pt;font-weight:600;cursor:pointer;background:#4299E0;color:#fff}
.qz-grade-btn:disabled{opacity:.35;cursor:default}
</style>

<div class="qz-shell">
  <div class="qz-nav"><div class="qz-nav-list" id="qz-nav"></div><div></div></div>
  <div class="qz-main" id="qz-main"></div>
</div>

<script>
var QZ=[
  {q:'A rep searches for the exact denial code <code>CO-197</code>, which carries little meaning to embed. Which mode reliably surfaces the cases with that code?',
   opts:['Vector (semantic)','BM25 (keyword)','Neither can','Only a separate vector database'],
   ans:1, fb:'BM25 matches exact tokens, so a code like CO-197 is found precisely. Vector embeds meaning, and a bare code has little meaning, so it gets diluted.'},
  {q:'How does hybrid search combine the vector and keyword results?',
   opts:['It averages the two raw scores','It runs vector first, then filters by keyword','Reciprocal rank fusion of the two rankings','It returns whichever set is larger'],
   ans:2, fb:'Hybrid uses reciprocal rank fusion: 1/(60+rank_vector) + 1/(60+rank_keyword), rewarding results that rank well in both lists.'},
  {q:'Where do the embeddings and the BM25 index live in this demo?',
   opts:['In a separate managed vector service','In the Delta table only','Inside the Lakebase Postgres table, next to the data','In the app server memory'],
   ans:2, fb:'That is the whole point of Lakebase Search: embeddings and the BM25 index sit in the operational Postgres table, so search runs next to the data with plain SQL and no separate service.'}
];
var qzPick=new Array(QZ.length).fill(-1), qzCur=0, qzChecked=new Array(QZ.length).fill(false);
function qzBuildNav(){
  var nav=document.getElementById('qz-nav'); nav.innerHTML='';
  QZ.forEach(function(q,i){
    var item=document.createElement('div');
    item.className='qz-nav-item'+(i===qzCur?' active':'');
    var dc='qz-dot';
    if(qzChecked[i]){dc='qz-dot '+(qzPick[i]===q.ans?'correct':'wrong');}
    else if(qzPick[i]>=0){dc='qz-dot answered';}
    item.innerHTML='<div class="'+dc+'"></div>Question '+(i+1);
    item.onclick=function(){qzCur=i;qzBuildNav();qzShowQ();};
    nav.appendChild(item);
  });
}
function qzShowQ(){
  var q=QZ[qzCur], main=document.getElementById('qz-main');
  var html='<div class="qz-q">'+(qzCur+1)+'. '+q.q+'</div><div class="qz-opts">';
  q.opts.forEach(function(o,oi){
    var cls='qz-opt';
    if(qzChecked[qzCur]){cls+=' locked'; if(oi===q.ans) cls+=' right'; else if(oi===qzPick[qzCur]) cls+=' wrong-pick';}
    else if(oi===qzPick[qzCur]) cls+=' selected';
    html+='<div class="'+cls+'" onclick="qzSelect('+oi+')"><div class="qz-radio"></div><div>'+o+'</div></div>';
  });
  html+='</div>';
  if(qzChecked[qzCur]){var ok=qzPick[qzCur]===q.ans; html+='<div class="qz-fb show '+(ok?'ok':'no')+'">'+(ok?'&#10003; Correct. ':'&#10007; Not quite. ')+q.fb+'</div>';}
  else {html+='<div style="margin-top:14px"><button class="qz-grade-btn" '+(qzPick[qzCur]<0?'disabled':'')+' onclick="qzCheck()">Check</button></div>';}
  main.innerHTML=html;
}
function qzSelect(oi){ if(qzChecked[qzCur]) return; qzPick[qzCur]=oi; qzBuildNav(); qzShowQ(); }
function qzCheck(){ qzChecked[qzCur]=true; qzBuildNav(); qzShowQ(); }
qzBuildNav(); qzShowQ();
</script>
""")


# ---------------------------------------------------------------------------
def emit():
    lines = ["# Databricks notebook source"]
    for i, (kind, content) in enumerate(CELLS):
        if i > 0:
            lines.append("")
            lines.append("# COMMAND ----------")
            lines.append("")
        if kind == "md":
            for ln in content.splitlines():
                lines.append(("# MAGIC " + ln).rstrip())
        else:  # code
            for ln in content.splitlines():
                # already-magic lines (%pip etc.) keep their prefix
                lines.append(ln)
    out = os.path.join(os.path.dirname(__file__), "Lakebase-Search-Appeals.py")
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", out, "-", len(CELLS), "cells")


if __name__ == "__main__":
    emit()
