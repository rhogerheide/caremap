"""
CAREMap v2: pull Michigan census-tract data for the tract-level zoom-in.

Downloads:
  - 2024 Census cartographic boundary file for Michigan tracts (cb_2024_26_tract_500k.zip)
  - ACS 2020-2024 5-year tract estimates for Michigan: children under 5 (with margins of error),
    renter cost burden, median household income

Run from the project folder (same API key as before):
  export CENSUS_API_KEY=your_key
  python3 pull_mi_tracts.py

Writes:
  data/raw/mi_tracts/cb_2024_26_tract_500k.zip
  data/raw/mi_tracts/acs_mi_tracts_2020_2024.csv
"""

import os
import sys
from pathlib import Path

import pandas as pd
import requests

KEY = os.environ.get("CENSUS_API_KEY")
if not KEY:
    sys.exit("Set the CENSUS_API_KEY environment variable first.")

OUT = Path("data/raw/mi_tracts")
OUT.mkdir(parents=True, exist_ok=True)

BOUNDARY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_26_tract_500k.zip"
zip_path = OUT / "cb_2024_26_tract_500k.zip"
if not zip_path.exists():
    r = requests.get(BOUNDARY_URL, timeout=300)
    if r.status_code != 200:
        sys.exit(f"Boundary download failed: HTTP {r.status_code}")
    zip_path.write_bytes(r.content)
print(f"Tract boundaries: {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")

VARS = {
    "B01001_003E": "male_under5", "B01001_003M": "male_under5_moe",
    "B01001_027E": "female_under5", "B01001_027M": "female_under5_moe",
    "B25070_001E": "renters_total", "B25070_007E": "rent_pct_30_35", "B25070_008E": "rent_pct_35_40",
    "B25070_009E": "rent_pct_40_50", "B25070_010E": "rent_pct_50plus", "B25070_011E": "rent_pct_not_computed",
    "B19013_001E": "median_hh_income",
}
params = [("get", ",".join(["NAME"] + list(VARS))), ("for", "tract:*"), ("in", "state:26"), ("in", "county:*"),
          ("key", KEY)]
r = requests.get("https://api.census.gov/data/2024/acs/acs5", params=params, timeout=300)
if r.status_code != 200 or not r.text.lstrip().startswith("["):
    sys.exit(f"ACS tract pull failed: HTTP {r.status_code} - {r.text[:300]}")
rows = r.json()
df = pd.DataFrame(rows[1:], columns=rows[0]).rename(columns=VARS)
df["GEOID"] = df["state"] + df["county"] + df["tract"]
df.to_csv(OUT / "acs_mi_tracts_2020_2024.csv", index=False)
print(f"ACS tracts: {len(df):,} Michigan tracts written to {OUT / 'acs_mi_tracts_2020_2024.csv'}")
print("Done.")
