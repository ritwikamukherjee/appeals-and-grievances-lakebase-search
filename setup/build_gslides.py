#!/usr/bin/env python3
"""Build a Google Slides deck from the rendered slide PNGs.

Uploads each PNG to Drive (link-shared), creates a 16:9 presentation, and places
each image full-bleed on its own slide. Prints the presentation URL.
"""
import glob, json, mimetypes, os, subprocess, sys, urllib.request

AUTH = "PATH_TO_GOOGLE_AUTH"
QUOTA = "YOUR_GCP_QUOTA_PROJECT"
PNG_DIR = "REPO_ROOT/notebook/slides-png"
TITLE = "Lakebase Search - Appeals & Grievances"

token = subprocess.run(["python3", AUTH, "token"], capture_output=True, text=True).stdout.strip()
assert token and "ERROR" not in token, f"no token: {token[:200]}"
H = {"Authorization": f"Bearer {token}", "x-goog-user-project": QUOTA}


def api(method, url, body=None, headers=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    hh = dict(H)
    if headers: hh.update(headers)
    if data is not None and raw is None: hh["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, headers=hh, method=method)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def upload_png(path):
    """Multipart upload to Drive + make link-readable. Returns file id."""
    meta = {"name": os.path.basename(path)}
    boundary = "====lbsearch===="
    body = b""
    body += f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
    body += (json.dumps(meta) + "\r\n").encode()
    body += f"--{boundary}\r\nContent-Type: image/png\r\n\r\n".encode()
    body += open(path, "rb").read() + b"\r\n"
    body += f"--{boundary}--".encode()
    res = api("POST", "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
              raw=body, headers={"Content-Type": f"multipart/related; boundary={boundary}"})
    fid = res["id"]
    api("POST", f"https://www.googleapis.com/drive/v3/files/{fid}/permissions",
        body={"role": "reader", "type": "anyone"})
    return fid


def main():
    pngs = sorted(glob.glob(os.path.join(PNG_DIR, "slide-*.png")))
    assert pngs, "no PNGs found"
    print(f"uploading {len(pngs)} images to Drive...")
    ids = []
    for p in pngs:
        fid = upload_png(p)
        ids.append(fid)
        print(f"  {os.path.basename(p)} -> {fid}")

    pres = api("POST", "https://slides.googleapis.com/v1/presentations", body={"title": TITLE})
    pid = pres["presentationId"]
    W = pres["pageSize"]["width"]["magnitude"]   # EMU (16:9 default)
    Hh = pres["pageSize"]["height"]["magnitude"]
    default_slide = pres["slides"][0]["objectId"]
    print(f"presentation {pid}  page {W}x{Hh} EMU")

    reqs = []
    for i, fid in enumerate(ids):
        sid = f"slide_{i:02d}"
        img_url = f"https://drive.google.com/thumbnail?id={fid}&sz=w2560"
        reqs.append({"createSlide": {"objectId": sid, "insertionIndex": i,
                                     "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        reqs.append({"createImage": {"url": img_url,
            "elementProperties": {"pageObjectId": sid,
                "size": {"width": {"magnitude": W, "unit": "EMU"},
                         "height": {"magnitude": Hh, "unit": "EMU"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "EMU"}}}})
    # remove the default first slide (now after our inserted ones)
    reqs.append({"deleteObject": {"objectId": default_slide}})

    api("POST", f"https://slides.googleapis.com/v1/presentations/{pid}:batchUpdate",
        body={"requests": reqs})
    url = f"https://docs.google.com/presentation/d/{pid}/edit"
    print("\nDECK URL:", url)


if __name__ == "__main__":
    main()
