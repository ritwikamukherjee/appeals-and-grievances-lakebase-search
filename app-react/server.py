"""
FastAPI backend for the Lakebase Search mode-comparison app.

Serves the built React SPA (frontend/dist) and a small JSON API that runs the
same query in three modes (Vector / BM25 / Hybrid RRF) against the live Lakebase
`cases` table. Runs as the app service principal.
"""
import os
import logging
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import lakebase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("app")

app = FastAPI(title="Lakebase Search for Healthcare Appeals")

DIST = Path(__file__).parent / "frontend" / "dist"


# NOTE: no Lakebase work at startup. The app must boot instantly and serve the
# SPA/health check without depending on Lakebase (which can scale-to-zero and be
# slow to wake). All DB connections are lazy, per-request, in lakebase.search().
# Use GET /api/diag for an on-demand connectivity self-test.


@app.get("/api/health")
def health():
    return {"status": "ok", "project": lakebase.PROJECT, "branch": lakebase.BRANCH}


@app.get("/api/diag")
def diag():
    """On-demand self-test (SP -> Lakebase). Useful to confirm the auth path live."""
    return lakebase.selftest()


@app.get("/api/search")
def api_search(
    q: str = Query("", description="natural-language query (vector + hybrid)"),
    kw: str = Query("", description="keyword / code (bm25 + hybrid)"),
    limit: int = Query(5, ge=1, le=25),
    mode: str = Query("all"),
):
    try:
        return JSONResponse(lakebase.search(q, kw, limit, mode))
    except Exception as e:
        log.exception("search failed")
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


# ---- Static SPA ---------------------------------------------------------------
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/")
def index():
    return FileResponse(DIST / "index.html")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    f = DIST / full_path
    if f.is_file():
        return FileResponse(f)
    return FileResponse(DIST / "index.html")


# ---- Entrypoint: bind to the port Databricks assigns (DATABRICKS_APP_PORT) ----
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("DATABRICKS_APP_PORT", "8080"))
    log.info("BOOT: binding uvicorn to 0.0.0.0:%s (DATABRICKS_APP_PORT=%r)",
             port, os.environ.get("DATABRICKS_APP_PORT"))
    uvicorn.run(app, host="0.0.0.0", port=port)
