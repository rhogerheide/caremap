# CAREMap

**Where housing built for childcare providers could matter most.**

CAREMap scores all 3,144 U.S. counties on childcare supply and on housing pressure for both families and childcare workers, then flags the counties where both problems are severe. It was inspired by Rural Homes in Colorado, which designs housing so licensed childcare providers can run their business from home.

**Live map:** https://rhogerheide.github.io/caremap/

## Findings

1. **The two problems rarely overlap.** Across counties, the rank correlation between childcare shortage and every housing measure is within ±0.15. An integrated housing + childcare model fits a specific set of places, not everywhere.
2. **A childcare worker can't comfortably rent anywhere.** In every county, a year of HUD's 2-bedroom Fair Market Rent costs more than 30% of a childcare worker's median pay (46% in the typical county; 55% metro, 42% rural).
3. **63 counties carry both problems at once** (25 metro, 38 rural), with 554 more at Medium priority. The top counties stay in their group's top quarter under all 1,000 random weightings tested.
4. **Validation:** in Michigan, the childcare score tracks licensed slots per child moderately (rank correlation −0.49; −0.62 in metro counties) but not where the Census withholds business counts (−0.10).

## Method

| Step | What happens |
|---|---|
| Childcare score | Children under 5 per childcare worker (County Business Patterns paid staff + Nonemployer home-based providers), empirical-Bayes smoothed, percentile within metro or rural group |
| Withheld data | The Census withholds counts for counties with 0–2 businesses; those are scored at 0 and at 2, and tiers use the lower result |
| Housing score | Half families (renter cost burden, home value to income), half providers (2-bedroom rent ÷ childcare worker pay), percentile within group |
| Combined score | Geometric mean of the two, so a county must be high on both |
| Tiers | High: both scores in the group's top 25%. Medium: combined score in the top 25%. Counties under 100 children under 5 are not scored |
| Stability | 1,000 random weightings; share of draws in the group's top 25% |

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

## Repository

```
pull_v1_data.py          downloads every source and builds data/processed/county_v1_join.csv
notebooks/01_eda.ipynb   exploratory analysis
notebooks/02_scoring.ipynb  scores, tiers, stability check -> data/processed/county_scores_v1.csv
notebooks/03_mi_validation.ipynb  Michigan check against licensed capacity
docs/index.html          the live map (GitHub Pages)
site_build/              scripts that turn the scores + Census boundaries into the map page
figures/                 charts from the notebooks
data/                    raw downloads and processed tables
```

## Reproduce

```
pip install -r requirements.txt
export CENSUS_API_KEY=your_free_key   # https://api.census.gov/data/key_signup.html
python pull_v1_data.py
```

BLS blocks scripted downloads, so save `oesm25ma.zip` and `area_definitions_m2025.xlsx` from bls.gov into `data/raw/manual/` first (the script prints the links). Then run the notebooks in order.

## Limits

Scores show combined need, not proven impact. Nationally, childcare supply is counted in workers, not licensed slots. Counties hide neighborhood differences. College counties are flagged because student incomes inflate rent burden, and worker wages stand in for what home-based providers earn.

---
Built by Ric Hogerheide · Data Science and Economics, Michigan State University
