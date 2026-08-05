#!/usr/bin/env python3
"""Refresh this mirror from the canonical live endpoints.

The domains are the source of truth; this repo is a discovery/reproducibility
mirror. Run from the repo root:  python scripts/fetch_latest.py
"""
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITES = ("dabyte", "dablock")
FILES = (("api/aiv.json", "aiv.json"), ("aiv.csv", "aiv.csv"),
         ("api/history.json", "history.json"), ("api/rankings.json", "rankings.json"))

for site in SITES:
    out = ROOT / "data" / site
    out.mkdir(parents=True, exist_ok=True)
    for remote, local in FILES:
        url = f"https://{site}.ai/{remote}"
        with urllib.request.urlopen(url, timeout=30) as r:
            (out / local).write_bytes(r.read())
        print(f"  {site}/{local}  <-  {url}")
print("done — commit and push to update the mirror")
