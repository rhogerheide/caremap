"""
Childcare + Housing Map: pull the v1 county data and report coverage.

Pulls:
  - ACS 2020-2024 5-year (kids under 5, rent burden, home value, income, rental vacancy)
  - County Business Patterns 2023, NAICS 624410 (childcare businesses with paid staff)
  - Nonemployer Statistics 2023, NAICS 624410 (home-based / solo childcare providers)
  - USDA ERS 2023 Rural-Urban Continuum Codes (metro vs. nonmetro grouping)
  - HUD FY2027 Fair Market Rents (2-bedroom) and BLS May 2025 childcare worker wages (SOC 39-9011)
  - Michigan licensed child care providers with capacity (MiLEAP, State of Michigan map service)
  - Census Vintage 2025 county population estimates (population trend 2020-2025)
  - 2024 Census Gazetteer county list (the master list every source is checked against)

Setup (once):
  pip install pandas requests openpyxl
  Mac/Linux:  export CENSUS_API_KEY=your_key
  Windows:    setx CENSUS_API_KEY your_key   (then open a new terminal)

Run:
  python pull_v1_data.py

Writes:
  data/raw/acs_2020_2024.csv, data/raw/cbp_2023_624410.csv, data/raw/nes_2023_624410.csv,
  data/raw/rucc_2023.csv, data/raw/popest_v2025.csv
  data/processed/coverage_report.csv      one row per source: counties present / missing
  data/processed/missing_by_county.csv    every missing county, by source
  data/processed/county_v1_join.csv       all sources joined onto the master list
"""

import io
import os
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

KEY = os.environ.get("CENSUS_API_KEY")
if not KEY:
    sys.exit("Set the CENSUS_API_KEY environment variable first (see the top of this file).")

RAW = Path("data/raw")
OUT = Path("data/processed")
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

API = "https://api.census.gov/data"


# ---------- helpers ----------

def census_get(path, get_vars, predicates=None):
    params = {"get": ",".join(get_vars), "for": "county:*", "key": KEY}
    if predicates:
        params.update(predicates)
    r = requests.get(f"{API}/{path}", params=params, timeout=180)
    if r.status_code != 200 or not r.text.lstrip().startswith("["):
        raise RuntimeError(f"{path} {predicates or ''} {get_vars}: HTTP {r.status_code} - {r.text[:300]}")
    rows = r.json()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["GEOID"] = df["state"] + df["county"]
    return df


def first_working(path, attempts):
    """Variable and industry-code names shift between releases, so try a few spellings."""
    errors = []
    for get_vars, predicates in attempts:
        try:
            df = census_get(path, get_vars, predicates)
            print(f"  {path}: ok with get={get_vars} {predicates}")
            return df
        except RuntimeError as e:
            errors.append(str(e))
    raise RuntimeError(f"Every attempt for {path} failed:\n  " + "\n  ".join(errors))


def cached(path, pull):
    """Reuse a file that an earlier run already downloaded."""
    if path.exists():
        print(f"  using saved {path}")
        return pd.read_csv(path, dtype={"GEOID": str, "state": str, "county": str})
    return pull()


def nes_variables(year):
    """Ask the API which variable names this Nonemployer release actually uses."""
    r = requests.get(f"{API}/{year}/nonemp/variables.json", timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"{year}/nonemp/variables.json: HTTP {r.status_code} - {r.text[:300]}")
    names = sorted(r.json()["variables"])
    (RAW / f"nes_{year}_variables.txt").write_text("\n".join(names))
    return names


def keep_all_category_rows(df, cols):
    """Some business APIs return one row per size class or legal form; '001' means all."""
    for c in cols:
        if c in df.columns:
            df = df[df[c] == "001"]
    dupes = df["GEOID"].duplicated().sum()
    if dupes:
        print(f"  WARNING: {dupes} duplicate county rows remain - check before using")
    return df


# ---------- 1. master county list ----------

GAZ_URLS = [
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip",
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_counties_national.zip",
]


def load_master():
    for url in GAZ_URLS:
        r = requests.get(url, timeout=180)
        if r.status_code != 200:
            continue
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            name = next(n for n in z.namelist() if n.endswith(".txt"))
            df = pd.read_csv(z.open(name), sep="\t", dtype={"GEOID": str})
        df.columns = df.columns.str.strip()
        df = df[df["USPS"] != "PR"][["GEOID", "USPS", "NAME"]].rename(columns={"NAME": "county_name"})
        print(f"  master list: {len(df):,} counties (50 states + DC) from {url.rsplit('/', 1)[-1]}")
        return df
    sys.exit("Couldn't download the Gazetteer county list.")


print("Master list")
master = load_master()


# ---------- 2. ACS 2020-2024 5-year ----------

ACS_VARS = {
    "B01001_003E": "male_under5",
    "B01001_003M": "male_under5_moe",
    "B01001_027E": "female_under5",
    "B01001_027M": "female_under5_moe",
    "B25070_001E": "renters_total",
    "B25070_007E": "rent_pct_30_35",
    "B25070_008E": "rent_pct_35_40",
    "B25070_009E": "rent_pct_40_50",
    "B25070_010E": "rent_pct_50plus",
    "B25070_011E": "rent_pct_not_computed",
    "B25077_001E": "median_home_value",
    "B19013_001E": "median_hh_income",
    "B25003_003E": "renter_occupied",
    "B25004_002E": "vacant_for_rent",
    "B25004_003E": "vacant_rented_not_occupied",
}

print("ACS 2020-2024 5-year")
acs = cached(RAW / "acs_2020_2024.csv",
             lambda: census_get("2024/acs/acs5", ["NAME"] + list(ACS_VARS)).rename(columns=ACS_VARS))
nums = list(ACS_VARS.values())
acs[nums] = acs[nums].apply(pd.to_numeric, errors="coerce")
estimates = [c for c in nums if not c.endswith("_moe")]
acs[estimates] = acs[estimates].mask(acs[estimates] < 0)  # Census codes like -666666666 = not available

acs["kids_under5"] = acs["male_under5"] + acs["female_under5"]
acs["kids_under5_moe"] = np.sqrt(acs["male_under5_moe"].clip(lower=0) ** 2 + acs["female_under5_moe"].clip(lower=0) ** 2)
burdened = acs[["rent_pct_30_35", "rent_pct_35_40", "rent_pct_40_50", "rent_pct_50plus"]].sum(axis=1)
acs["rent_burden_share"] = burdened / (acs["renters_total"] - acs["rent_pct_not_computed"])
acs["price_to_income"] = acs["median_home_value"] / acs["median_hh_income"]
acs["rental_vacancy_rate"] = acs["vacant_for_rent"] / (
    acs["renter_occupied"] + acs["vacant_rented_not_occupied"] + acs["vacant_for_rent"]
)
acs = acs.replace([np.inf, -np.inf], np.nan)
acs.to_csv(RAW / "acs_2020_2024.csv", index=False)


# ---------- 3. County Business Patterns 2023 ----------

print("County Business Patterns 2023 (NAICS 624410)")


def pull_cbp():
    df = first_working("2023/cbp", [
        (["NAME", "ESTAB", "EMP", "EMPSZES"], {"NAICS2017": "624410"}),
        (["NAME", "ESTAB", "EMP", "EMPSZES"], {"NAICS2022": "624410"}),
        (["NAME", "ESTAB", "EMP"], {"NAICS2017": "624410"}),
        (["NAME", "ESTAB", "EMP"], {"NAICS2022": "624410"}),
    ])
    df = keep_all_category_rows(df, ["EMPSZES"])
    df[["ESTAB", "EMP"]] = df[["ESTAB", "EMP"]].apply(pd.to_numeric, errors="coerce")
    df = df.rename(columns={"ESTAB": "cbp_estab", "EMP": "cbp_emp"})
    df.to_csv(RAW / "cbp_2023_624410.csv", index=False)
    return df


cbp = cached(RAW / "cbp_2023_624410.csv", pull_cbp)


# ---------- 4. Nonemployer Statistics 2023 ----------

print("Nonemployer Statistics 2023 (NAICS 624410)")


def pull_nes():
    names = nes_variables(2023)
    naics = [n for n in names if n.startswith("NAICS") and not n.endswith("_LABEL") and "_" not in n[5:]]
    estab = [n for n in names if n in ("NESTAB", "NONEMP", "ESTAB")]
    filters = [n for n in ("LFO", "RCPSZES") if n in names]
    print(f"  industry codes: {naics}  establishment counts: {estab}  filters: {filters}")
    if not naics or not estab:
        raise RuntimeError(f"Unexpected variable names - see {RAW / 'nes_2023_variables.txt'}")
    # County files may not go down to 6 digits. 6244 / 62441 contain only childcare (624410),
    # so the shorter codes count exactly the same providers.
    attempts = []
    for industry in ("624410", "62441", "6244"):
        attempts += [(["NAME", estab[0]] + filters, {code: industry}) for code in naics]
        attempts += [(["NAME", estab[0]], {code: industry}) for code in naics]
    df = first_working("2023/nonemp", attempts)
    df = keep_all_category_rows(df, filters)
    df[estab[0]] = pd.to_numeric(df[estab[0]], errors="coerce")
    df = df.rename(columns={estab[0]: "nes_estab"})
    df.to_csv(RAW / "nes_2023_624410.csv", index=False)
    return df


nes = cached(RAW / "nes_2023_624410.csv", pull_nes)


# ---------- 4b. rural-urban codes + population trend (plain file downloads) ----------

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def download_csv(url):
    r = requests.get(url, headers=BROWSER_HEADERS, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"{url}: HTTP {r.status_code}")
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(io.StringIO(r.content.decode(enc)), dtype=str)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"{url}: couldn't decode the file")


RUCC_URL = "https://ers.usda.gov/media/5768/2023-rural-urban-continuum-codes.csv?v=21521"


def pull_rucc():
    df = download_csv(RUCC_URL)
    if "Attribute" in df.columns:  # ERS ships this file in long format: one row per county per attribute
        df = df.pivot_table(index=["FIPS", "State", "County_Name"], columns="Attribute",
                            values="Value", aggfunc="first").reset_index()
    fips_col = next(c for c in df.columns if c.upper() == "FIPS")
    rucc_col = next(c for c in df.columns if c.upper().startswith("RUCC"))
    df = df.rename(columns={fips_col: "GEOID", rucc_col: "rucc_2023"})
    df["GEOID"] = df["GEOID"].str.zfill(5)
    df["rucc_2023"] = pd.to_numeric(df["rucc_2023"], errors="coerce")
    df = df[["GEOID", "rucc_2023"]].dropna()
    df["metro"] = df["rucc_2023"] <= 3  # ERS: codes 1-3 metro, 4-9 nonmetro
    df.to_csv(RAW / "rucc_2023.csv", index=False)
    return df


POPEST_URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv"


def pull_popest():
    df = download_csv(POPEST_URL)
    df = df[df["SUMLEV"] == "050"].copy()  # county rows only (040 = state totals)
    df["GEOID"] = df["STATE"].str.zfill(2) + df["COUNTY"].str.zfill(3)
    years = sorted(int(c[-4:]) for c in df.columns if c.startswith("POPESTIMATE") and c[-4:].isdigit())
    first, last = years[0], years[-1]
    df["pop_first"] = pd.to_numeric(df[f"POPESTIMATE{first}"])
    df["pop_last"] = pd.to_numeric(df[f"POPESTIMATE{last}"])
    df["pop_change_pct"] = (df["pop_last"] / df["pop_first"] - 1) * 100
    print(f"  population estimates: July {first} to July {last}")
    df = df[["GEOID", "pop_first", "pop_last", "pop_change_pct"]]
    df.to_csv(RAW / "popest_v2025.csv", index=False)
    return df


COLLEGE_VARS = {
    "B14001_001E": "pop_3plus",
    "B14001_008E": "enrolled_undergrad",
    "B14001_009E": "enrolled_grad",
}


def pull_college():
    df = census_get("2024/acs/acs5", ["NAME"] + list(COLLEGE_VARS)).rename(columns=COLLEGE_VARS)
    nums = list(COLLEGE_VARS.values())
    df[nums] = df[nums].apply(pd.to_numeric, errors="coerce")
    df["college_share"] = (df["enrolled_undergrad"] + df["enrolled_grad"]) / df["pop_3plus"]
    df.to_csv(RAW / "acs_college_2020_2024.csv", index=False)
    return df


def download_bytes(url):
    r = requests.get(url, headers=BROWSER_HEADERS, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"{url}: HTTP {r.status_code}")
    return r.content


def find_col(df, *needles):
    """First column whose lowercase name contains all the needles."""
    for c in df.columns:
        name = str(c).lower().replace("_", " ")
        if all(n in name for n in needles):
            return c
    raise KeyError(f"No column containing {needles}. Columns: {list(df.columns)}")


# ----- HUD Fair Market Rents FY2027 (2-bedroom), by county -----

FMR_URL = "https://www.huduser.gov/portal/datasets/fmr/fmr2027/FY27_FMRs.xlsx"


def pull_fmr():
    df = pd.read_excel(io.BytesIO(download_bytes(FMR_URL)), dtype=str)
    fips = find_col(df, "fips")
    fmr2 = next(c for c in df.columns if str(c).lower().replace("_", "") in ("fmr2", "fmr2br"))
    pop = next((c for c in df.columns if "pop" in str(c).lower()), None)
    df["GEOID"] = df[fips].str.zfill(10).str[:5]
    df["fmr_2br"] = pd.to_numeric(df[fmr2], errors="coerce")
    df["w"] = pd.to_numeric(df[pop], errors="coerce").fillna(1) if pop else 1
    # New England files list towns; weight them to one value per county
    out = (df.assign(wx=df["fmr_2br"] * df["w"]).groupby("GEOID")
             .agg(wx=("wx", "sum"), w=("w", "sum")).reset_index())
    out["fmr_2br"] = out["wx"] / out["w"]
    out = out[["GEOID", "fmr_2br"]]
    print(f"  FMR: {len(out):,} counties (columns used: {fips}, {fmr2}, weight={pop})")
    out.to_csv(RAW / "fmr_fy2027.csv", index=False)
    return out


# ----- BLS OEWS May 2025: childcare worker wages (SOC 39-9011), by metro/nonmetro area -----

OEWS_URL = "https://www.bls.gov/oes/special-requests/oesm25ma.zip"
OEWS_AREAS_URL = "https://www.bls.gov/oes/area_definitions_m2025.xlsx"


MANUAL = RAW / "manual"
MANUAL.mkdir(exist_ok=True)


def local_or_download(url):
    """BLS blocks scripted downloads, so use a copy saved by hand in data/raw/manual/ if there is one."""
    local = MANUAL / url.rsplit("/", 1)[-1]
    if local.exists():
        print(f"  using {local}")
        return local.read_bytes()
    try:
        return download_bytes(url)
    except RuntimeError as e:
        sys.exit(f"\n{e}\nDownload it in your browser and save it as {local.resolve()}\n  {url}\nthen run this script again.")


def pull_oews():
    with zipfile.ZipFile(io.BytesIO(local_or_download(OEWS_URL))) as z:
        # the zip holds metro areas (MSA_...) and nonmetro "balance of state" areas (BOS_...) in separate files
        names = [n for n in z.namelist() if n.lower().endswith(".xlsx")
                 and any(k in n.lower().rsplit("/", 1)[-1] for k in ("msa", "bos"))]
        frames = []
        for name in names:
            part = pd.read_excel(z.open(name), dtype=str)
            part.columns = [str(c).upper() for c in part.columns]
            frames.append(part)
        print(f"  OEWS files read: {names}")
        wages = pd.concat(frames, ignore_index=True)
    cw = wages[wages["OCC_CODE"] == "39-9011"].copy()
    cw["childcare_wage"] = pd.to_numeric(cw["A_MEDIAN"], errors="coerce")
    hourly = pd.to_numeric(cw["H_MEDIAN"], errors="coerce") * 2080
    cw["childcare_wage"] = cw["childcare_wage"].fillna(hourly)
    cw["wage_imputed"] = cw["childcare_wage"].isna()
    state_median = cw.groupby("PRIM_STATE")["childcare_wage"].transform("median")
    cw["childcare_wage"] = cw["childcare_wage"].fillna(state_median)  # suppressed areas: state's median area
    cw = cw[["AREA", "AREA_TITLE", "PRIM_STATE", "childcare_wage", "wage_imputed"]]

    areas = pd.read_excel(io.BytesIO(local_or_download(OEWS_AREAS_URL)), dtype=str)
    st = find_col(areas, "fips")
    co = find_col(areas, "county code")
    ar = next(c for c in areas.columns if "code" in str(c).lower() and ("msa" in str(c).lower() or "area" in str(c).lower()))
    areas["GEOID"] = areas[st].str.zfill(2) + areas[co].str.zfill(3)
    areas = areas[["GEOID", ar]].rename(columns={ar: "AREA"}).drop_duplicates("GEOID")
    areas["AREA"] = areas["AREA"].str.lstrip("0")
    cw["AREA"] = cw["AREA"].str.lstrip("0")
    out = areas.merge(cw, on="AREA", how="left")
    # areas with no published childcare wage at all: use the median of the state's other counties
    missing = out["childcare_wage"].isna()
    state_fill = out.groupby(out["GEOID"].str[:2])["childcare_wage"].transform("median")
    out.loc[missing, "childcare_wage"] = state_fill[missing]
    out["wage_imputed"] = out["wage_imputed"].astype("boolean").fillna(False) | missing
    print(f"  OEWS: {cw['AREA'].nunique()} areas with childcare wages; {len(out):,} counties mapped "
          f"(columns used: {st}, {co}, {ar}); {int(out['wage_imputed'].sum())} counties use a state-median wage")
    out.to_csv(RAW / "oews_childcare_wage_m2025_v2.csv", index=False)
    return out


# ----- Michigan licensed child care (MiLEAP, via the State of Michigan map service) -----

# Statewide layer owned by the State of Michigan (item a79c3b0caedf412599085941e2af91d4, "Child Care")
MI_URL = ("https://utility.arcgis.com/usrsvcs/servers/a79c3b0caedf412599085941e2af91d4"
          "/rest/services/CSS/CSS_LARA/MapServer/5/query")


def norm_county(name):
    s = str(name).lower().replace(" county", "").replace(".", "").replace("saint ", "st ").strip()
    return " ".join(s.split())


def pull_mi_licensing():
    rows, offset = [], 0
    while True:
        r = requests.get(MI_URL, params={
            "where": "1=1",
            "outFields": "LicenseNumber,FacilityName,FacilityTypeCode,FacilityType,Capacity,CountyCode,City,ZIPCode,Latitude,Longitude",
            "returnGeometry": "false", "f": "json", "resultOffset": offset, "resultRecordCount": 1000,
            "orderByFields": "OBJECTID",
        }, headers=BROWSER_HEADERS, timeout=180)
        page = r.json()
        if "error" in page:
            raise RuntimeError(f"Michigan service error: {page['error']}")
        feats = page.get("features", [])
        rows += [f["attributes"] for f in feats]
        if not feats or not page.get("exceededTransferLimit"):
            break
        offset += len(feats)
    df = pd.DataFrame(rows)
    # CountyCode holds county names ("Wayne"); match them to the master list's Michigan counties
    mi = master[master["USPS"] == "MI"].assign(key=lambda d: d["county_name"].map(norm_county))
    lookup = dict(zip(mi["key"], mi["GEOID"]))
    df["GEOID"] = df["CountyCode"].map(norm_county).map(lookup)
    unmatched = df.loc[df["GEOID"].isna(), "CountyCode"].value_counts()
    print(f"  Michigan licensing: {len(df):,} providers in {df['GEOID'].nunique()} of 83 counties; "
          f"{df['GEOID'].isna().sum()} rows with an unmatched county {dict(unmatched.head(5))}")
    df.to_csv(RAW / "mi_licensed_childcare_v2.csv", index=False)
    return df


print("HUD Fair Market Rents FY2027")
fmr = cached(RAW / "fmr_fy2027.csv", pull_fmr)
print("BLS childcare worker wages, May 2025")
oews = cached(RAW / "oews_childcare_wage_m2025_v2.csv", pull_oews)
print("Michigan licensed child care")
mi_lic = cached(RAW / "mi_licensed_childcare_v2.csv", pull_mi_licensing)

print("ACS college enrollment (for the college-county flag)")
college = cached(RAW / "acs_college_2020_2024.csv", pull_college)

print("Rural-Urban Continuum Codes 2023")
rucc = cached(RAW / "rucc_2023.csv", pull_rucc)
print("Population estimates, Vintage 2025")
popest = cached(RAW / "popest_v2025.csv", pull_popest)


# ---------- 5. coverage report ----------

def coverage(source, df, col, absent_label):
    in_scope = df[~df["GEOID"].str.startswith("72")]  # drop Puerto Rico
    merged = master.merge(in_scope[["GEOID", col]], on="GEOID", how="left")
    missing = merged[merged[col].isna()]
    unmatched = sorted(set(in_scope["GEOID"]) - set(master["GEOID"]))
    print(f"\n{source}: {len(master) - len(missing):,} / {len(master):,} counties have a value")
    if len(missing):
        label = absent_label or "missing"
        print(f"  {len(missing):,} {label}; most by state:")
        print("  " + missing.groupby("USPS").size().sort_values(ascending=False).head(8).to_string().replace("\n", "\n  "))
    if unmatched:
        print(f"  {len(unmatched)} county codes in the source aren't on the master list "
              f"(boundary mismatch, e.g. old Connecticut counties): {unmatched[:10]}")
    report_rows.append({
        "source": source,
        "counties_with_value": len(master) - len(missing),
        "counties_missing": len(missing),
        "what_missing_means": absent_label or "missing",
        "codes_not_on_master_list": len(unmatched),
        "connecticut_present": int(merged[merged["USPS"] == "CT"][col].notna().sum()),
    })
    missing_rows.append(missing.assign(source=source)[["source", "GEOID", "USPS", "county_name"]])


report_rows, missing_rows = [], []
coverage("ACS kids under 5", acs, "kids_under5", None)
coverage("ACS rent burden share", acs, "rent_burden_share", None)
coverage("ACS price-to-income", acs, "price_to_income", None)
coverage("ACS rental vacancy rate", acs, "rental_vacancy_rate", None)
coverage("CBP 2023 childcare employees", cbp, "cbp_emp",
         "not published: CBP withholds counties with fewer than 3 businesses (0, 1 or 2)")
coverage("NES 2023 childcare solo providers", nes, "nes_estab", "not listed (likely zero)")
coverage("USDA rural-urban code 2023", rucc, "rucc_2023", None)
coverage("Population change 2020-2025", popest, "pop_change_pct", None)
coverage("ACS college enrollment share", college, "college_share", None)
coverage("HUD 2-bedroom Fair Market Rent FY2027", fmr, "fmr_2br", None)
coverage("BLS childcare worker median wage May 2025", oews, "childcare_wage", None)

pd.DataFrame(report_rows).to_csv(OUT / "coverage_report.csv", index=False)
pd.concat(missing_rows).to_csv(OUT / "missing_by_county.csv", index=False)


# ---------- 6. joined table ----------

joined = (
    master
    .merge(acs[["GEOID", "kids_under5", "kids_under5_moe", "rent_burden_share",
                "price_to_income", "rental_vacancy_rate", "median_hh_income"]], on="GEOID", how="left")
    .merge(cbp[["GEOID", "cbp_estab", "cbp_emp"]], on="GEOID", how="left")
    .merge(nes[["GEOID", "nes_estab"]], on="GEOID", how="left")
    .merge(rucc[["GEOID", "rucc_2023", "metro"]], on="GEOID", how="left")
    .merge(popest[["GEOID", "pop_first", "pop_last", "pop_change_pct"]], on="GEOID", how="left")
    .merge(college[["GEOID", "college_share"]], on="GEOID", how="left")
    .merge(fmr[["GEOID", "fmr_2br"]], on="GEOID", how="left")
    .merge(oews[["GEOID", "childcare_wage", "wage_imputed"]], on="GEOID", how="left")
    .merge(acs[["GEOID", "renters_total", "rent_pct_not_computed", "rent_pct_30_35", "rent_pct_35_40",
                "rent_pct_40_50", "rent_pct_50plus"]], on="GEOID", how="left")
)
# CBP leaves out counties with 0-2 childcare businesses, so their staff count is unknown, not zero.
# Keep it blank and flag it; the scoring stage decides how to fill it.
joined["cbp_withheld_0to2"] = joined["cbp_emp"].isna()
joined["nes_listed"] = joined["nes_estab"].notna()
joined["nes_estab"] = joined["nes_estab"].fillna(0)
# Provider housing: a year of 2-bedroom Fair Market Rent as a share of a childcare worker's median pay.
# Above 0.30 means a childcare worker paying that rent would be cost-burdened.
joined["provider_rent_share"] = joined["fmr_2br"] * 12 / joined["childcare_wage"]

# Michigan validation input: licensed capacity per county
mi_cap = (mi_lic.assign(Capacity=pd.to_numeric(mi_lic["Capacity"], errors="coerce"))
          .groupby("GEOID").agg(mi_licensed_capacity=("Capacity", "sum"), mi_licensed_providers=("Capacity", "size"))
          .reset_index())
joined = joined.merge(mi_cap, on="GEOID", how="left")

joined.to_csv(OUT / "county_v1_join.csv", index=False)

print(f"\nDone. {len(joined):,} counties written to {OUT / 'county_v1_join.csv'}")
print(f"Coverage summary: {OUT / 'coverage_report.csv'}")
