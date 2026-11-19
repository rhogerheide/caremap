"""Inject site_data.json and the Michigan check summary into template.html -> index.html.

Usage: python3 make_index.py template.html site_data.json mi_licensed_model_summary.csv index.html
"""
import json
import sys
from pathlib import Path

import pandas as pd

template, data_json, mi_summary, out = map(Path, sys.argv[1:5])

KEYS = {"All Michigan": "all", "Metro": "metro", "Rural": "rural",
        "Business data published": "pub", "Business data withheld": "withheld"}
m = pd.read_csv(mi_summary, index_col=0)
miv = [{"key": KEYS[k], "subset": k, "counties": int(r["counties"]), "rho": float(r["rank correlation"]),
        "overlap": r["worst-quarter overlap"]} for k, r in m.iterrows()]

html = template.read_text()
assert "__DATA__" in html and "__MIV__" in html
html = html.replace("__DATA__", data_json.read_text()).replace("__MIV__", json.dumps(miv))
out.write_text(html)
print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")
