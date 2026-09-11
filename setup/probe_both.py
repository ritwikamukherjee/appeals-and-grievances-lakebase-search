# Databricks notebook source
import json, urllib.request, urllib.error
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
hdr = dict(w.config.authenticate())

APPS = {
  "working_genie": "https://genie-ontology-readiness-YOUR_ORG_ID.2.azure.databricksapps.com",
  "ours":          "https://healthplan-search-compare-YOUR_ORG_ID.2.azure.databricksapps.com",
}

def probe(base, path):
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path, headers=hdr, method="GET"), timeout=30) as r:
            fu = r.geturl()
            return {"status": r.status, "login_redirect": "login.html" in fu, "final_host": fu.split('/')[2]}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final_host": (getattr(e,'url','') or '').split('/')[2] if getattr(e,'url','') else ''}
    except Exception as e:
        return {"error": str(e)[:150]}

out = {name: {p: probe(base, p) for p in ["/", "/api/health"]} for name, base in APPS.items()}
dbutils.notebook.exit(json.dumps(out, indent=2))
