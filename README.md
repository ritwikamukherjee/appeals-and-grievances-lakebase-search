# Lakebase Search for Healthcare Appeals

A Databricks demo that shows semantic, keyword, and hybrid search running inside
Lakebase (Databricks managed Postgres), over a synthetic health plan appeals and
grievances dataset. It reskins the Lakebase Search "BakeReview" pattern for a
health plan member services audience.

The point of the demo: a member services rep, when a member calls about a denied
claim, needs to find similar prior cases fast. The case narrative is free text
and the codes are structured, so no single search style is enough. Hybrid search
(vector plus BM25, fused with reciprocal rank fusion) handles both.

## What is in here

| Path | What it is |
|---|---|
| `setup/generate_appeals_data.py` | Deterministic synthetic data generator, writes `data/plans.csv` and `data/cases.csv` |
| `setup/run_sql.py` | Small SQL runner (Statement Execution API) used to create UC objects and load Delta |
| `setup/seed_lakebase.py` | Notebook that loads Delta into Lakebase, computes 1024-dim embeddings, builds a pgvector index |
| `setup/validate_search.py` | Notebook that builds the Lakebase Search objects (`lakebase_ann`, `lakebase_bm25`, `search_tsv`) and validates vector, BM25, and hybrid |
| `setup/add_embeddings_to_delta.py` | Notebook that writes the embeddings back into the UC Delta table as `ARRAY<FLOAT>` |
| `setup/eval_modes.py`, `setup/eval_compound.py` | Precision at k evaluations comparing the three search modes |
| `notebook/build_notebook.py` | Assembles the lecture notebook from clean cells (branded slide HTML plus runnable Acts) |
| `notebook/Lakebase-Search-Appeals.py` | The generated lecture notebook, Acts A to D |
| `notebook/export_slides.py`, `notebook/build_gslides.py` | Export the notebook slides to standalone HTML and to a Google Slides deck |
| `app-react/` | The deployed Databricks App: React frontend plus FastAPI backend, three way search comparison |
| `app/` | An earlier Streamlit prototype of the same comparison (superseded by `app-react`) |
| `data/` | The generated CSV seed data |

## Data model

- **plans**: plan_id, plan_name, line_of_business (Medicare Advantage, Medicaid,
  Commercial, ACA Marketplace, D-SNP), state, region.
- **cases** (800 rows): case_id, plan_id, case_type (Appeal or Grievance),
  member_id, member_name, filed_date, service_category (10 categories),
  denial_reason_code (CARC code such as CO-197 or CO-50), denial_reason_desc,
  cpt_hcpcs_code, icd10_code, disposition (Upheld, Overturned, and so on), and a
  free text **narrative**. In Lakebase the narrative also has a `vector(1024)`
  embedding plus a `search_tsv` tsvector.

All data is synthetic. The narratives are generated; the code systems they use
(CARC denial codes, CPT/HCPCS, ICD-10, plan types) are real public taxonomies.

## Architecture

```
generate_appeals_data.py  ->  CSV  ->  UC Volume  ->  Delta (healthplan_appeals.appeals.cases)
                                                          |
                                          seed_lakebase.py (read Delta, embed, insert)
                                                          v
                                     Lakebase Postgres cases (vector + search_tsv)
                                          |  lakebase_ann (vector), lakebase_bm25 (keyword)
                                          v
                              FastAPI + React app  ->  vector | BM25 | hybrid, side by side
```

The app runs as its own service principal, mints a short lived Lakebase OAuth
credential per request, connects with psycopg as its Postgres role, and embeds
the query through a Foundation Model serving endpoint.

## The three search modes

- **Vector**: `embedding <=> query`, pgvector or `lakebase_ann`. Matches meaning.
- **BM25**: `search_tsv <@> to_bm25query(...)`, `lakebase_bm25`. Matches exact tokens and codes.
- **Hybrid**: reciprocal rank fusion of the two, `1/(60+rank_vec) + 1/(60+rank_kw)`.

On a task that needs both signals (find the right case type carrying the right
denial code), a precision at 5 evaluation across sample queries scored hybrid
0.95, vector 0.70, and BM25 0.20. Vector gets the topic but misses the exact
code; BM25 gets the code but the wrong topics; hybrid gets both.

## Configuration (fill these in)

The code ships with placeholder tokens instead of a specific workspace or
identity. Set them before running, either by editing the files or by exporting
the environment variables the scripts read (`PROFILE`, `WAREHOUSE_ID`, and so on).

| Placeholder | What it is | How to get it |
|---|---|---|
| `YOUR_PROFILE` | Databricks CLI profile name | `databricks auth login --host <workspace-url> --profile <name>` |
| `YOUR_ORG_ID` | Workspace org id (appears in the workspace and app URLs) | the number in `https://adb-<org-id>.N.azuredatabricks.net` |
| `YOUR_USERNAME` | Your Databricks username, used in `/Workspace/Users/...` paths | `databricks current-user me` |
| `YOUR_WAREHOUSE_ID` | A SQL warehouse id, used by `run_sql.py` | `databricks warehouses list` |
| `YOUR_APP_SP_CLIENT_ID` | The app service principal client id, set as `PGUSER` in `app-react/app.yaml` | after `databricks apps create`, read `service_principal_client_id` from `databricks apps get <app>`, then grant that Postgres role SELECT on the Lakebase `cases` table |
| `YOUR_GCP_QUOTA_PROJECT`, `PATH_TO_GOOGLE_AUTH`, `YOUR_DECK_URL` | Only for the Google Slides export (`build_gslides.py`) | your GCP quota project, the local google-auth helper path, and your deck URL |
| `REPO_ROOT`, `YOUR_HOME` | Local filesystem paths | point them at your clone and home directory |

Resource names the setup creates (catalog `healthplan_appeals`, schema `appeals`,
Lakebase project `healthplan-appeals`, app `healthplan-search-compare`) are not
secrets. Rename them if you like.

## Run it

Prerequisites: a serverless Databricks workspace with Lakebase, the Databricks
CLI authenticated to a profile, and `psql` for the grant steps. Fill in the
placeholders above first.

1. Generate data: `python3 setup/generate_appeals_data.py`
2. Create the catalog, schema, volume, and Delta tables, then upload the CSVs
   (see `setup/run_sql.py`).
3. Provision a Lakebase project, then run `setup/seed_lakebase.py` to load and embed.
4. Enable **Lakebase Search (Beta)** on the project in the UI. This loads
   `lakebase_vector` and `lakebase_text` via `shared_preload_libraries` and
   requires a compute restart.
5. Run `setup/validate_search.py` to build the `lakebase_ann` and `lakebase_bm25`
   indexes and confirm all three modes.
6. Deploy the app from `app-react/` (build the frontend, then `databricks apps deploy`).

Note on ports: Databricks Apps route to the port in `DATABRICKS_APP_PORT`, so the
app binds to that env var (not a hardcoded port).

See `DEMO.md` for the presentation walkthrough.
