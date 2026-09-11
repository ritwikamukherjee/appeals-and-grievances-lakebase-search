# How to demo Lakebase Search (Appeals & Grievances)

**Time:** ~10 min. **Audience:** health-plan / payer technical + business.
**One-liner:** semantic + keyword + hybrid retrieval running *inside* the operational
Postgres that already backs your app, no separate vector service, no ETL out of the
system of record.

## Before you present (already done)
- Catalog `healthplan_appeals.appeals` + Lakebase project `healthplan-appeals` seeded
  (800 appeal/grievance cases, 1024-dim embeddings, pgvector + Lakebase Search indexes).
- **Lakebase Search (Beta) is enabled** on the project.
- Notebook: `/WorkspaceYOUR_HOME@databricks.com/healthplan-lakebase-search/Lakebase-Search-Appeals`

## Setup at the podium
1. Open the notebook, attach **Serverless**, **Run All** (or run cell-by-cell to narrate).
2. Everything renders inline, the `%md-sandbox` slides are the deck; the result tables
   highlight *why* each case matched (green = keyword/code, blue = semantic concept).

## The narration (cell by cell)
1. **Title + "the problem" slides**, A member-services rep needs the right prior appeal
   fast. The narrative is free text; the codes are structured. Keyword-only misses
   paraphrases; vector-only misses exact codes.
2. **Setup cell**, "We're connecting to the *same* Lakebase Postgres the app uses. The
   search happens here, next to member/claims data."
3. **Act A, vector.** Query: *"a member with a serious autoimmune condition cannot get the
   medication they need."* It shares almost no words with the cases it finds, yet returns the
   specialty pharmacy narratives. Embeddings match on meaning.
4. **Enable-Search slide**, one-time per-project Beta toggle (already on). The next cell
   builds the Search indexes: `lakebase_ann` (vector) + `lakebase_bm25` (keyword).
5. **Act B, BM25.** Keyword **`infusion`**. Exact-token retrieval nails every narrative that
   uses that word, and shows green highlights, something vector matching does not do.
6. **Act C, hybrid (RRF).** Query about the autoimmune medication plus keyword *infusion*.
   Hybrid reranks to entirely different top cases than vector (semantic recall plus exact-term
   precision, fused with reciprocal rank fusion). The two-color highlights make the "why" obvious.
7. **Under-the-hood slide**, what Lakebase Search adds over pgvector: IVF+RaBitQ ANN,
   true BM25 with Block-Max WAND, hybrid in plain SQL, all inside the OLTP DB.
8. **Act D, AI brief.** A Foundation Model turns the top matches into a 3-bullet,
   rep-ready summary, the contextual-lookup pattern an app would run on every case.
9. **Takeaway slide**, embeddings + codes live next to the data; hybrid retrieval with no
   separate service and no copy; enable per project with one toggle.

## The money line
> "Your app already talks to this database. Turn on one toggle and it can now do semantic,
> keyword, and hybrid search over your own records, with normal SQL filters, joins, and
> transactions, instead of standing up and syncing a separate vector store."

## If you re-run / reset
- The build-indexes cell is idempotent (`IF NOT EXISTS`).
- Enabling Search sets the project to always-on compute (min 1 CU, no scale-to-zero). To
  park cost after the demo, lower it or disable Search again in the project settings.
