#!/usr/bin/env python3
"""Extract the notebook's %md-sandbox slide cells into standalone .html files.

Reads the generated Lakebase-Search-Appeals.py, pulls each `%md-sandbox` cell,
strips the `# MAGIC ` prefixes, and writes a self-contained HTML doc per slide
(white background, padded) into ./slides-html/ for easy screenshot/export into a
deck. Purely local; does not touch the workspace.
"""
import os, re

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "Lakebase-Search-Appeals.py")
OUT = os.path.join(HERE, "slides-html")
os.makedirs(OUT, exist_ok=True)

lines = open(SRC).read().splitlines()
cells, cur = [], []
for ln in lines:
    if ln.strip() == "# COMMAND ----------":
        cells.append(cur); cur = []
    else:
        cur.append(ln)
cells.append(cur)

WRAP = ("<!doctype html><html><head><meta charset='utf-8'>"
        "<style>html,body{{background:#fff;margin:0;}}"
        ".stage{{width:1280px;min-height:720px;box-sizing:border-box;padding:56px;"
        "display:flex;flex-direction:column;align-items:center;justify-content:center;}}"
        ".stage>*{{width:100%;}}</style></head>"
        "<body><div class='stage'>\n{body}\n</div></body></html>\n")

def demagic(cell):
    out = []
    for ln in cell:
        if ln.startswith("# MAGIC %md-sandbox") or ln.startswith("# MAGIC %md"):
            continue
        if ln.startswith("# MAGIC "):
            out.append(ln[len("# MAGIC "):])
        elif ln.startswith("# MAGIC"):
            out.append(ln[len("# MAGIC"):])
    return "\n".join(out).strip()

n, names = 0, []
for cell in cells:
    joined = "\n".join(cell)
    if "%md-sandbox" not in joined:
        continue
    html = demagic(cell)
    # derive a short slug from a title-ish token in the HTML
    m = re.search(r'(ds-banner-title|ds-callout-title|class="h"[^>]*)>([^<]{3,60})', html)
    slug = "slide"
    if m:
        slug = re.sub(r"[^a-z0-9]+", "-", m.group(2).lower()).strip("-")[:40]
    n += 1
    fname = f"slide-{n:02d}-{slug}.html"
    with open(os.path.join(OUT, fname), "w") as f:
        f.write(WRAP.format(body=html))
    names.append(fname)

print(f"wrote {n} standalone slides to slides-html/")
for x in names:
    print("  -", x)
