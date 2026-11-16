"""Turn county_scores_v1.csv + projected boundaries into compact JSON for the CAREMap page."""
import json
import sys
from pathlib import Path

import pandas as pd

scores_csv, mi_csv, counties_geo, states_geo, out = map(Path, sys.argv[1:6])

s = pd.read_csv(scores_csv, dtype={"GEOID": str})
mi = pd.read_csv(mi_csv, dtype={"GEOID": str})[["GEOID", "mi_licensed_capacity", "kids_per_slot"]]
s = s.merge(mi, on="GEOID", how="left")

group_sizes = s[~s["screened_out"]].groupby("group").size().to_dict()
tier_code = {"High": "H", "Medium": "M", "Low": "L", "Not scored": "N"}


def r(x, d=1):
    return None if pd.isna(x) else round(float(x), d)


data = {}
for _, row in s.iterrows():
    data[row["GEOID"]] = [
        row["county_name"], row["USPS"], "M" if row["group"] == "Metro" else "N",
        tier_code.get(row["tier"], "N"),
        r(row["childcare_score"]), r(row["housing_score"]), r(row["combined_score"]),
        None if pd.isna(row["rank_in_group"]) else int(row["rank_in_group"]),
        r(row["stable_share"], 2),
        int(row["kids_under5"]) if not pd.isna(row["kids_under5"]) else None,
        r(row["rent_burden_eb"] * 100 if not pd.isna(row["rent_burden_eb"]) else None),
        r(row["price_to_income"], 2),
        r(row["provider_rent_share"] * 100 if not pd.isna(row["provider_rent_share"]) else None),
        r(row["fmr_2br"], 0), r(row["childcare_wage"], 0),
        r(row["kpw_low_eb"]), r(row["kpw_high_eb"]),
        r(row["pop_change_pct"]), r(row["college_share"] * 100 if not pd.isna(row["college_share"]) else None),
        int(bool(row["cbp_withheld_0to2"])), int(bool(row["wage_imputed"])) if not pd.isna(row["wage_imputed"]) else 0,
        int(bool(row["college_county"])) if not pd.isna(row["college_county"]) else 0,
        int(bool(row["tier_uncertain"])) if not pd.isna(row["tier_uncertain"]) else 0,
        r(row["mi_licensed_capacity"], 0), r(row["kids_per_slot"], 2),
        r(row["provider_rent_pctile"]), r(row["rent_burden_pctile"]), r(row["price_to_income_pctile"]),
    ]


def load(geo_path):
    return json.loads(geo_path.read_text())["features"]


cf, sf = load(counties_geo), load(states_geo)
allx, ally = [], []
for f in cf:
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        for ring in poly:
            for x, y in ring:
                allx.append(x); ally.append(y)
X0, X1, Y0, Y1 = min(allx), max(allx), min(ally), max(ally)
SCALE = 1000 / (X1 - X0)
W, H = 1000, round((Y1 - Y0) * SCALE, 1)


def paths(features, key):
    out_ = []
    for f in features:
        g = f["geometry"]
        if not g:
            continue
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        d = []
        for poly in polys:
            for ring in poly:
                pts, last = [], None
                for x, y in ring:
                    p_ = (round((x - X0) * SCALE, 1), round((Y1 - y) * SCALE, 1))
                    if p_ != last:
                        pts.append(p_); last = p_
                if len(pts) >= 3:
                    d.append("M" + "L".join(f"{a:g},{b:g}" for a, b in pts) + "Z")
        out_.append([f["properties"].get(key, ""), "".join(d)])
    return out_


county_paths = paths(cf, "GEOID")
state_paths = paths(sf, "STUSPS")
bbox = [0, 0, W, H]

payload = {"data": data, "groups": group_sizes, "counties": county_paths, "states": state_paths, "bbox": bbox}
out.write_text(json.dumps(payload, separators=(",", ":")))
print(f"{len(data)} counties of data, {len(county_paths)} shapes, {len(state_paths)} states, "
      f"{out.stat().st_size / 1e6:.2f} MB, bbox {bbox}")
missing = set(data) - {g for g, _ in county_paths}
print("scored counties without a shape:", sorted(missing)[:20], len(missing))
