# Market Data Dictionary

## Contract

Each indicator record must define: `indicator_id`, `name`, `category`, `subcategory`, `description`, `economic_rationale`, `source`, `source_identifier`, `source_reference`, `frequency`, `unit`, `native_frequency`, `release_lag`, `timezone`, `higher_means`, `lower_means`, `transformation`, `expected_start_date`, `missing_data_policy`, `revision_policy`, `publication_timestamp_available`, `predictive_or_descriptive`, and `notes`.

The entries below are Phase 1 candidates only. They are **definitions for verification**, not an implemented feed. Any item marked **TBD / requires verification** must be confirmed, including its licensing and historical availability, before ingestion.

## Initial Phase 1 entries

### 2-Year Treasury Yield

| Field | Value |
|---|---|
| indicator_id | `us_treasury_2y_yield` |
| category / subcategory | Rates / Treasury yield curve |
| description / rationale | Nominal two-year U.S. Treasury yield; reflects near-term policy expectations and rate-market conditions. |
| source / identifier / reference | FRED / `DGS2` / **TBD / requires verification** of use terms and release metadata. |
| frequency / native frequency / unit | Daily / daily / percent per annum. |
| release lag / timezone | **TBD / requires verification** / U.S. market convention; exact timezone TBD. |
| higher means / lower means | Higher yields; interpretation depends on policy, growth, inflation, and risk context. / Lower yields; same contextual limitation. |
| transformation | Raw level; future changes and spreads must be separately versioned. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | Preserve missing value; do not forward-fill raw data. Preserve source revisions/vintages when available. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Not a standalone growth or risk signal. |

### 10-Year Treasury Yield

| Field | Value |
|---|---|
| indicator_id | `us_treasury_10y_yield` |
| category / subcategory | Rates / Treasury yield curve |
| description / rationale | Nominal ten-year U.S. Treasury yield; summarizes expected short rates, inflation compensation, and term premium. |
| source / identifier / reference | FRED / `DGS10` / **TBD / requires verification** of use terms and release metadata. |
| frequency / native frequency / unit | Daily / daily / percent per annum. |
| release lag / timezone | **TBD / requires verification** / U.S. market convention; exact timezone TBD. |
| higher means / lower means | Higher/lower yields are context-dependent and must not be converted mechanically into risk-on/risk-off labels. |
| transformation | Raw level. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | Preserve missing; preserve source revisions/vintages when available. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Term premium is not separately identified by this series. |

### 10Y minus 2Y Yield Curve

| Field | Value |
|---|---|
| indicator_id | `us_treasury_10y_minus_2y` |
| category / subcategory | Rates / Yield-curve spread |
| description / rationale | Ten-year Treasury yield less two-year Treasury yield; describes this segment of curve slope. |
| source / identifier / reference | Derived from validated `us_treasury_10y_yield` and `us_treasury_2y_yield`; no independent raw source. |
| frequency / native frequency / unit | Daily / daily inputs / percentage points. |
| release lag / timezone | Available only after both inputs are available; exact timestamp policy **TBD / requires verification**. |
| higher means / lower means | Steeper/flatter curve; economic interpretation depends on level, drivers, and regime. |
| transformation | `10Y − 2Y`, calculated only from same-date validated observations; transformation version required. |
| expected start date | Intersection of verified input histories. |
| missing / revision policy | Null if either input is missing; recompute when an input vintage changes and preserve processing version. |
| publication timestamp available | Derived; governed by latest available input timestamp. |
| predictive or descriptive | Descriptive / potential leading research candidate; requires validation. |
| notes | Unit must not be mislabeled as basis points unless explicitly multiplied by 100. |

### Investment Grade OAS

| Field | Value |
|---|---|
| indicator_id | `us_investment_grade_oas` |
| category / subcategory | Credit / Investment-grade spreads |
| description / rationale | Option-adjusted spread for a defined U.S. investment-grade corporate-bond index; a measure of credit compensation and financial conditions. |
| source / identifier / reference | FRED / likely `BAMLC0A0CM` / **TBD / requires verification** of exact index definition, license, and availability. |
| frequency / native frequency / unit | Daily / daily / percentage points, **TBD / requires verification**. |
| release lag / timezone | **TBD / requires verification**. |
| higher means / lower means | Wider/tighter spreads; neither is a standalone allocation action. |
| transformation | Raw level; derived changes/percentiles are separate. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | Preserve missing and source revisions. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Index methodology may change; capture source metadata. |

### High Yield OAS

| Field | Value |
|---|---|
| indicator_id | `us_high_yield_oas` |
| category / subcategory | Credit / High-yield spreads |
| description / rationale | Option-adjusted spread for a defined U.S. high-yield corporate-bond index; reflects credit-risk pricing and risk appetite. |
| source / identifier / reference | FRED / likely `BAMLH0A0HYM2` / **TBD / requires verification** of exact index definition, license, and availability. |
| frequency / native frequency / unit | Daily / daily / percentage points, **TBD / requires verification**. |
| release lag / timezone | **TBD / requires verification**. |
| higher means / lower means | Wider/tighter spreads; interpretation needs price, liquidity, and macro context. |
| transformation | Raw level. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | Preserve missing and source revisions. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Do not mix OAS from differing vendor/index methodologies. |

### SOFR

| Field | Value |
|---|---|
| indicator_id | `sofr` |
| category / subcategory | Liquidity / Overnight funding |
| description / rationale | Secured Overnight Financing Rate, a broad overnight Treasury-repo funding measure. |
| source / identifier / reference | Federal Reserve Bank of New York / `SOFR` / **TBD / requires verification** of API, terms, timestamp fields, and historical revisions. |
| frequency / native frequency / unit | Business daily / business daily / percent per annum. |
| release lag / timezone | **TBD / requires verification**. |
| higher means / lower means | Higher/lower overnight funding rate; interpretation requires policy target and market context. |
| transformation | Raw published rate. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | Preserve non-publication days as missing; preserve revisions if supplied. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive. |
| notes | Do not interpret it as total system liquidity. |

### MOVE Index

| Field | Value |
|---|---|
| indicator_id | `move_index` |
| category / subcategory | Volatility / Rates implied volatility |
| description / rationale | ICE BofA MOVE Index, a measure of implied volatility in U.S. Treasury markets. |
| source / identifier / reference | **TBD / requires verification** / **TBD / requires verification** / licensing and redistribution conditions require verification. |
| frequency / native frequency / unit | **TBD / requires verification** / likely business daily / index points. |
| release lag / timezone | **TBD / requires verification**. |
| higher means / lower means | Higher/lower expected Treasury-market volatility; not direction. |
| transformation | Raw index level. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | **TBD / requires verification**. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Vendor and licensing uncertainty intentionally unresolved. |

### VIX

| Field | Value |
|---|---|
| indicator_id | `vix` |
| category / subcategory | Volatility / Equity implied volatility |
| description / rationale | Cboe Volatility Index, a model-based measure of S&P 500 option-implied volatility. |
| source / identifier / reference | Cboe or approved public market-data provider / **TBD / requires verification** / index and data-license terms require verification. |
| frequency / native frequency / unit | Business daily / business daily / annualized volatility index points. |
| release lag / timezone | **TBD / requires verification**. |
| higher means / lower means | Higher/lower implied volatility and protection demand; not a directional price forecast. |
| transformation | Raw close or specified timestamp; method must be explicit. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | Preserve source values and selected timestamp convention. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Do not mix intraday and close values. |

### S&P 500

| Field | Value |
|---|---|
| indicator_id | `spx` |
| category / subcategory | Equity / Broad U.S. equity index |
| description / rationale | S&P 500 Index level, a large-cap U.S. equity-market reference. |
| source / identifier / reference | S&P Dow Jones Indices or approved provider / **TBD / requires verification** / licensing and level-return convention require verification. |
| frequency / native frequency / unit | Business daily / business daily / index points. |
| release lag / timezone | **TBD / requires verification**. |
| higher means / lower means | Higher/lower price level; does not itself identify the underlying driver. |
| transformation | Raw close or explicitly specified observation timestamp; return series are derived separately. |
| expected start date | **TBD / requires verification**. |
| missing / revision policy | Preserve source gaps and corrections; do not imply total return from price index. |
| publication timestamp available | **TBD / requires verification**. |
| predictive or descriptive | Descriptive. |
| notes | Price index, not total-return index, unless a separately defined series is chosen. |
