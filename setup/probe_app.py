# Databricks notebook source
import json, urllib.request, urllib.error
from databricks.sdk import WorkspaceClient

APP = "https://healthplan-search-compare-YOUR_ORG_ID.2.azure.databricksapps.com"
w = WorkspaceClient()
hdr = dict(w.config.authenticate())  # OAuth bearer for this principal

def probe(path):
    url = APP + path
    req = urllib.request.Request(url, headers=hdr, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(300).decode("utf-8", "replace")
            return {"path": path, "status": r.status, "final_url": r.geturl(), "body": body}
    except urllib.error.HTTPError as e:
        return {"path": path, "status": e.code, "final_url": getattr(e, "url", ""), "body": e.read(300).decode("utf-8", "replace")}
    except Exception as e:
        return {"path": path, "error": str(e)[:200]}

out = {p: probe(p) for p in ["/api/health", "/"]}
dbutils.notebook.exit(json.dumps(out, indent=2))
