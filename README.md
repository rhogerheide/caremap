# CAREMap

**Where housing built for childcare providers could matter most.**

CAREMap scores all 3,144 U.S. counties on childcare supply and on housing pressure for both families and childcare workers, then flags the counties where both problems are severe. It was inspired by Rural Homes in Colorado, which designs housing so licensed childcare providers can run their business from home.

**Live map:** https://rhogerheide.github.io/caremap/

## Findings

1. **The two problems rarely overlap.** Across counties, the rank correlation between childcare shortage and every housing measure is within ±0.15. An integrated housing + childcare model fits a specific set of places, not everywhere.
2. **A childcare worker can't comfortably rent anywhere.** In every county, a year of HUD's 2-bedroom Fair Market Rent costs more than 30% of a childcare worker's median pay (46% in the typical county; 55% metro, 42% rural).
3. **106 counties carry both problems at once:** 63 confirmed High (25 metro, 38 rural) plus 43 "High, unconfirmed" that rest on withheld Census business counts, with 654 more at Medium priority. The top counties stay in their group's top quarter under all 1,000 random weightings tested.
4. **The overlap clusters.** High counties border each other 34 times against about 10 expected by chance. Hot spots: Texas into western Louisiana, the Southwest and Great Basin, the southern Appalachians. The two shortages do not travel together; the overlap is where two separately clustered patterns cross.
5. **Few of the neediest places are an easy fit.** 9 of 106 High counties meet all four measurable conditions behind the Ouray project. Fit pulls against childcare need: the worst-off counties have the fewest home-based providers to recruit.
6. **Michigan check:** ranking counties by children per worker and by children per licensed slot agrees at 0.62 (13 of the 20 worst counties shared), but only 0.22 where the Census withholds business counts. The state's provider file attaches county and capacity to the wrong rows; they were shuffled together, so county totals still hold and only those are used.
7. **Case studies:** Maui's #2 rank is not a 2023 wildfire artifact; Archuleta County, CO is the closest match to Ouray; Lake County, MI has the overlap but would need a low-cost rental version of the model.

## Method

| Step | What happens |
|---|---|
| Childcare score | Children under 5 per childcare worker (County Business Patterns paid staff + Nonemployer home-based providers), empirical-Bayes smoothed, percentile within metro or rural group |
| Withheld data | The Census withholds counts for counties with 0–2 businesses; those are scored at 0 (the better match to Michigan's licensed slots) and checked at 2. A High that disappears at 2 is labeled "High, unconfirmed" |
| Housing score | Half families (renter cost burden, home value to income), half providers (2-bedroom rent ÷ childcare worker pay), percentile within group |
| Combined score | Geometric mean of the two, so a county must be high on both |
| Tiers | High: both scores in the group's top 25%. Medium: combined score in the top 25%. Counties under 100 children under 5 are not scored |
| Stability | 1,000 random weightings; share of draws in the group's top 25% |
| Clustering | Moran's I, bivariate Moran's I, join counts and local Moran (LISA), queen contiguity, 999 permutations |
| Fit (separate layer) | For High and Medium counties: population holding or growing, median home value ≥ $275k, local pool of home-based providers, state license for 12-child homes. Never changes the ranking |

## Data

| Source | Use | Year |
|---|---|---|
| Census American Community Survey (5-year) | Children, rent burden, home value, income, college enrollment | 2020–2024 |
| Census County Business Patterns (NAICS 624410) | Childcare businesses with paid staff | 2023 |
| Census Nonemployer Statistics (NAICS 6244) | Home-based solo providers | 2023 |
| HUD Fair Market Rents | 2-bedroom rent | FY2027 |
| BLS Occupational Employment and Wage Statistics (SOC 39-9011) | Childcare worker median pay | May 2025 |
| USDA ERS Rural-Urban Continuum Codes | Metro vs. rural grouping | 2023 |
| Census population estimates | Population change | Vintage 2025 |
| Michigan MiLEAP child care licensing | Licensed capacity, for validation | 2025–26 |
| Census ACS tracts + cartographic boundaries (Michigan) | Tract-level children and licensed-provider placement | 2020–2024 / 2024 |
| ACF ECQA Center group child care home licensing study | Which states license 7–12-child homes | 2017 |

## Repository

```
pull_v1_data.py          downloads every source and builds data/processed/county_v1_join.csv
notebooks/01_eda.ipynb   exploratory analysis
notebooks/02_scoring.ipynb  scores, tiers, stability check -> data/processed/county_scores_v1.csv
notebooks/03_mi_validation.ipynb  first Michigan check against licensed capacity (version 1)
notebooks/04_mi_licensed_model.ipynb  Michigan licensed-slot model, data check, census tracts
notebooks/05_clustering.ipynb  do the shortages cluster? (Moran's I, LISA)
notebooks/06_feasibility_fit.ipynb  fit layer drawn from the Ouray project
notebooks/07_case_studies.ipynb  Maui (wildfire test), Archuleta CO, Lake MI
pull_mi_tracts.py        Michigan tract boundaries and ACS tract data
docs/index.html          the live map (GitHub Pages)
site_build/              build_site_data.py + make_index.py turn the scores into the map page
figures/                 charts from the notebooks
data/                    raw downloads and processed tables
```

## Reproduce

```
pip install -r requirements.txt
export CENSUS_API_KEY=your_free_key   # https://api.census.gov/data/key_signup.html
python pull_v1_data.py
```

BLS blocks scripted downloads, so save `oesm25ma.zip` and `area_definitions_m2025.xlsx` from bls.gov into `data/raw/manual/` first (the script prints the links). Then run `python pull_mi_tracts.py` and the notebooks in order.

## Limits

Scores show combined need, not proven impact, and fit uses a few national measures that can't see land, partners or local politics. Nationally, childcare supply is counted in workers, not licensed slots. Counties hide neighborhood differences. College counties are flagged because student incomes inflate rent burden, and worker wages stand in for what home-based providers earn.

---
Built by Ric Hogerheide · Data Science and Economics, Michigan State University
