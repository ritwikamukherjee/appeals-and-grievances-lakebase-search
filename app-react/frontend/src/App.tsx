import { useState } from "react";
import { search, Result, SearchResponse } from "./api";

// Sample-question presets. Each fills BOTH the query and keyword fields. These are
// verified live: the keyword appears in the narratives (so BM25 + Hybrid show
// green), and hybrid's top 5 differs entirely from vector's top 5, so the reviewer
// sees hybrid rerank by combining meaning and keyword rather than mirroring vector.
interface Preset {
  label: string;
  q: string;
  kw: string;
}
const PRESETS: Preset[] = [
  {
    label: "Autoimmune medication denied",
    q: "a member with a serious autoimmune condition cannot get the medication they need",
    kw: "infusion",
  },
  {
    label: "Mental health care cut short",
    q: "the member's mental health care was stopped too early",
    kw: "residential",
  },
];

// Preset 1 is the initial default.
const DEFAULT_Q = PRESETS[0].q;
const DEFAULT_KW = PRESETS[0].kw;

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Highlight the full narrative, coloring each mode by what it actually matched on:
//   green (hl-kw)      = exact keyword / denial-code hits (BM25 + Hybrid)
//   blue  (hl-concept) = semantic concept words (Vector + Hybrid)
// Matching is case-insensitive and whole-word-ish (won't fire inside a longer
// word). On overlap, green wins. The narrative is never truncated.
function Highlight({
  text,
  greenTerms,
  blueTerms,
}: {
  text: string;
  greenTerms: string[];
  blueTerms: string[];
}) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  const green = [...new Set(greenTerms.map((t) => t.trim()).filter(Boolean))];
  const blue = [...new Set(blueTerms.map((t) => t.trim()).filter(Boolean))];
  const all = [...new Set([...green, ...blue])];
  if (all.length === 0) return <>{clean}</>;

  const greenSet = new Set(green.map((t) => t.toLowerCase()));
  // Longest first so multi-word terms win over their substrings.
  const ordered = all.sort((a, b) => b.length - a.length);
  // Whole-word-ish: not preceded/followed by an alphanumeric character.
  const re = new RegExp(
    `(?<![A-Za-z0-9])(${ordered.map(escapeRe).join("|")})(?![A-Za-z0-9])`,
    "gi"
  );
  const parts = clean.split(re);
  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 1) {
          const cls = greenSet.has(part.toLowerCase()) ? "hl-kw" : "hl-concept";
          return (
            <mark key={i} className={cls}>
              {part}
            </mark>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function dispoClass(d: string | null): string {
  const s = (d || "").toLowerCase();
  if (s.includes("partial")) return "dispo dispo-partial";
  if (s.includes("overturn")) return "dispo dispo-overturned";
  if (s.includes("uphold") || s.includes("upheld") || s.includes("denied"))
    return "dispo dispo-upheld";
  if (s.includes("pending")) return "dispo dispo-pending";
  return "dispo dispo-muted";
}

function Card({
  r,
  rank,
  greenTerms,
  blueTerms,
}: {
  r: Result;
  rank: number;
  greenTerms: string[]; // exact keyword / denial-code hits (BM25 + Hybrid)
  blueTerms: string[]; // semantic concept words (Vector + Hybrid)
}) {
  const denial =
    r.denial_reason_code || r.denial_reason_desc
      ? [r.denial_reason_code, r.denial_reason_desc].filter(Boolean).join(" · ")
      : null;

  return (
    <div className="card">
      <div className="card-head">
        <span className="rank">{rank}</span>
        <span className="case-id">{r.case_id}</span>
        <span className="score">
          {r.score_label} {r.score ?? "n/a"}
        </span>
      </div>

      <div className="card-plan">
        <span className="plan">{r.plan_name}</span>
        {r.line_of_business && <span className="lob">{r.line_of_business}</span>}
      </div>

      <div className="chips">
        {r.service_category && (
          <span className="chip-badge cat">{r.service_category}</span>
        )}
        {denial && <span className="chip-badge denial">{denial}</span>}
        {r.cpt_hcpcs_code && (
          <span className="chip-badge code">
            <span className="chip-k">CPT/HCPCS</span> {r.cpt_hcpcs_code}
          </span>
        )}
        {r.icd10_code && (
          <span className="chip-badge code">
            <span className="chip-k">ICD-10</span> {r.icd10_code}
          </span>
        )}
        {r.disposition && (
          <span className={dispoClass(r.disposition)}>{r.disposition}</span>
        )}
      </div>

      {(r.member_id || r.filed_date) && (
        <div className="meta-line">
          {r.member_id && <span>Member {r.member_id}</span>}
          {r.member_id && r.filed_date && <span className="dot">·</span>}
          {r.filed_date && <span>Filed {r.filed_date}</span>}
        </div>
      )}

      <div className="narrative">
        <Highlight
          text={r.narrative}
          greenTerms={greenTerms}
          blueTerms={blueTerms}
        />
      </div>
    </div>
  );
}

interface ColSpec {
  key: "vector" | "bm25" | "hybrid";
  title: string;
  tag: string;
  caption: string;
}

const COLUMNS: ColSpec[] = [
  {
    key: "vector",
    title: "Vector",
    tag: "semantic",
    caption:
      "embedding <=> query · pgvector / lakebase_ann. Matches meaning, not exact words.",
  },
  {
    key: "bm25",
    title: "BM25",
    tag: "keyword",
    caption:
      "search_tsv <@> to_bm25query(…) · lakebase_bm25. Exact tokens & codes.",
  },
  {
    key: "hybrid",
    title: "Hybrid",
    tag: "RRF",
    caption: "Reciprocal rank fusion of vector + BM25. Recall and precision.",
  },
];

export default function App() {
  const [q, setQ] = useState(DEFAULT_Q);
  const [kw, setKw] = useState(DEFAULT_KW);
  const [limit, setLimit] = useState(5);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(
    e?: React.FormEvent,
    override?: { q?: string; kw?: string }
  ) {
    e?.preventDefault();
    const qv = override?.q ?? q;
    const kwv = override?.kw ?? kw;
    setLoading(true);
    setError(null);
    try {
      const res = await search(qv, kwv, limit);
      setData(res);
    } catch (err: any) {
      setError(err.message || String(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  // Fill both fields from a preset, then run the search immediately.
  function applyPreset(p: Preset) {
    setQ(p.q);
    setKw(p.kw);
    run(undefined, { q: p.q, kw: p.kw });
  }

  // Green terms (exact keyword / code): the literal keyword(s) the user typed.
  // The per-result denial code is added per card below.
  const kwTerms = kw
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  // Blue terms (semantic concepts): the concept vocabulary the API returns.
  const concepts = data?.concepts ?? [];

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-inner">
          <div className="brand">
            <span className="brand-mark" />
            <div>
              <h1>Lakebase Search for Healthcare Appeals</h1>
              <p className="sub">
                Same query, three retrieval modes, side by side, on the live
                Lakebase <code>cases</code> table (health-plan appeals and
                grievances). See how semantic, keyword, and hybrid search differ.
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="container">
        <div className="presets">
          <span className="presets-label">Sample questions</span>
          {PRESETS.map((p) => {
            const active = q === p.q && kw === p.kw;
            return (
              <button
                key={p.label}
                type="button"
                className={`preset${active ? " active" : ""}`}
                onClick={() => applyPreset(p)}
                disabled={loading}
              >
                {p.label}
              </button>
            );
          })}
        </div>

        <form className="controls" onSubmit={run}>
          <label className="field grow">
            <span className="label">Natural-language query</span>
            <span className="hint">used by Vector + Hybrid</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="describe the member's situation…"
            />
          </label>
          <label className="field">
            <span className="label">Keyword / code</span>
            <span className="hint">used by BM25 + Hybrid</span>
            <input
              value={kw}
              onChange={(e) => setKw(e.target.value)}
              placeholder="e.g. CO-50, wheelchair, CPAP"
            />
          </label>
          <label className="field narrow">
            <span className="label">Results</span>
            <span className="hint">per mode</span>
            <input
              type="number"
              min={1}
              max={25}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
          </label>
          <button type="submit" className="go" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </button>
        </form>

        <div className="legend">
          <span className="chip">
            <mark className="hl-kw">green</mark> = exact keyword / code match
          </span>
          <span className="chip">
            <mark className="hl-concept">blue</mark> = semantic concept
          </span>
          <span className="tip">
            Each column is colored by what that mode matched on: Vector on
            meaning (blue), BM25 on the literal keyword / code (green), Hybrid on
            both. With keyword <em>CO-50</em>, watch Hybrid surface DME / mobility
            cases carrying the CO-50 code, where BM25 alone drifts off topic.
          </span>
        </div>

        {error && <div className="error">Search failed: {error}</div>}

        <section className="grid">
          {COLUMNS.map((col) => {
            const rows = data?.[col.key] ?? [];
            // green = keyword/code (BM25 + Hybrid); blue = concepts (Vector + Hybrid)
            const useGreen = col.key === "bm25" || col.key === "hybrid";
            const useBlue = col.key === "vector" || col.key === "hybrid";
            return (
              <div key={col.key} className="column">
                <div className={`col-head ${col.key}`}>
                  <h2>
                    {col.title} <span className="col-tag">{col.tag}</span>
                  </h2>
                  <p className="col-caption">{col.caption}</p>
                </div>
                <div className="col-body">
                  {!data && !loading && (
                    <p className="empty">Run a search to compare modes.</p>
                  )}
                  {data && rows.length === 0 && (
                    <p className="empty">
                      {col.key === "vector"
                        ? "Enter a natural-language query."
                        : col.key === "bm25"
                        ? "Enter a keyword or code."
                        : "Needs both a query and a keyword."}
                    </p>
                  )}
                  {rows.map((r, i) => {
                    const greenTerms = useGreen
                      ? [...kwTerms, r.denial_reason_code || ""]
                      : [];
                    const blueTerms = useBlue ? concepts : [];
                    return (
                      <Card
                        key={i}
                        r={r}
                        rank={i + 1}
                        greenTerms={greenTerms}
                        blueTerms={blueTerms}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </section>

        <footer className="foot">
          Live query against Lakebase autoscale Postgres · project{" "}
          <code>healthplan-appeals</code> / branch <code>production</code> ·
          embeddings from <code>databricks-gte-large-en</code>. Runs as the app
          service principal.
        </footer>
      </main>
    </div>
  );
}
