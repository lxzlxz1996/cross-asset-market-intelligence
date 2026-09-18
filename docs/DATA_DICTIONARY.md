# Market Data Dictionary

## Contract

Each indicator record must define: `indicator_id`, `name`, `category`, `subcategory`, `description`, `economic_rationale`, `source`, `source_identifier`, `source_reference`, `frequency`, `unit`, `native_frequency`, `release_lag`, `timezone`, `higher_means`, `lower_means`, `transformation`, `expected_start_date`, `missing_data_policy`, `revision_policy`, `publication_timestamp_available`, `predictive_or_descriptive`, and `notes`.

The entries below are Phase 1 candidates only; no feed is implemented by this document. Source-contract facts were verified in Phase 1.1 on 2026-09-16. A remaining **TBD / requires verification** is intentional and blocks selection or implementation of that aspect.

## Initial Phase 1 entries

### 2-Year Treasury Yield

| Field | Value |
|---|---|
| indicator_id | `us_treasury_2y_yield` |
| category / subcategory | Rates / Treasury yield curve |
| description / rationale | Nominal two-year U.S. Treasury yield; reflects near-term policy expectations and rate-market conditions. |
| source / identifier / reference | Board of Governors of the Federal Reserve System (US), H.15 Selected Interest Rates; FRED distribution series `DGS2`. [Series](https://fred.stlouisfed.org/series/DGS2), [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [Treasury methodology](https://home.treasury.gov/resource-center/data-chart-center/interest-rates). |
| frequency / native frequency / unit | Daily / daily / percent per annum. |
| release lag / timezone | FRED exposes a `last_updated` timestamp, but the official H.15 publication schedule and an observation-level publication timestamp are not established here. Store retrieval time; timezone for the FRED update timestamp is Central Time. Treasury input quotations are obtained about 3:30 p.m. ET on business days. |
| higher means / lower means | Higher yields; interpretation depends on policy, growth, inflation, and risk context. / Lower yields; same contextual limitation. |
| transformation | Direct validated identity normalization from `fred` / `DGS2`; finite values remain percent per annum unchanged (`4.25` remains `4.25`). Processing version: `fred_treasury_direct_percent_identity_v1`. Future changes and spreads must be separately versioned. |
| expected start date | 1976-06-01 in the verified FRED `DGS2` distribution. |
| missing / revision policy | FRED represents non-observations as missing. Preserve them; direct processing omits a processed row for a null raw value and does not forward-fill. For a date with multiple valid stored FRED realtime vintages, select the greatest `(realtime_start, realtime_end, vintage)` tuple; preserve all raw and processed history. FRED says all data are subject to revision and supports real-time/vintage retrieval. |
| publication timestamp available | No observation-level publication timestamp in the documented FRED observations response; `realtime_start`/`realtime_end` are date-level real-time periods, not an intraday release timestamp. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | FRED API requires a registered API key; it supports JSON/XML/XLSX/CSV and vintage dates. The underlying BOG series is marked public domain with citation requested on FRED. Not a standalone growth or risk signal. |

### 10-Year Treasury Yield

| Field | Value |
|---|---|
| indicator_id | `us_treasury_10y_yield` |
| category / subcategory | Rates / Treasury yield curve |
| description / rationale | Nominal ten-year U.S. Treasury yield; summarizes expected short rates, inflation compensation, and term premium. |
| source / identifier / reference | Board of Governors of the Federal Reserve System (US), H.15 Selected Interest Rates; FRED distribution series `DGS10`. [Series](https://fred.stlouisfed.org/series/DGS10), [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [Treasury methodology](https://home.treasury.gov/resource-center/data-chart-center/interest-rates). |
| frequency / native frequency / unit | Daily / daily / percent per annum. |
| release lag / timezone | FRED exposes `last_updated`, but a guaranteed official H.15 schedule and observation-level publication timestamp are not established here. Store retrieval time; FRED's visible update timestamp is Central Time. Treasury input quotations are obtained about 3:30 p.m. ET on business days. |
| higher means / lower means | Higher/lower yields are context-dependent and must not be converted mechanically into risk-on/risk-off labels. |
| transformation | Direct validated identity normalization from `fred` / `DGS10`; finite values remain percent per annum unchanged. Processing version: `fred_treasury_direct_percent_identity_v1`. |
| expected start date | 1962-01-02 in the verified FRED `DGS10` distribution. |
| missing / revision policy | FRED represents non-observations as missing. Preserve them; direct processing omits a processed row for a null raw value and does not forward-fill. For a date with multiple valid stored FRED realtime vintages, select the greatest `(realtime_start, realtime_end, vintage)` tuple; preserve all raw and processed history. FRED states data are subject to revision and supports real-time/vintage retrieval. |
| publication timestamp available | No observation-level publication timestamp in the documented FRED observations response; `realtime_start`/`realtime_end` are date-level real-time periods. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | FRED API requires a registered API key; it supports JSON/XML/XLSX/CSV and vintage dates. The underlying BOG series is marked public domain with citation requested on FRED. Treasury CMTs are interpolated curve points, not necessarily yields of an outstanding security. Term premium is not separately identified. |

### 10Y minus 2Y Yield Curve

| Field | Value |
|---|---|
| indicator_id | `us_treasury_10y_minus_2y` |
| category / subcategory | Rates / Yield-curve spread |
| description / rationale | Ten-year Treasury yield less two-year Treasury yield; describes this segment of curve slope. |
| source / identifier / reference | Derived from validated `us_treasury_10y_yield` and `us_treasury_2y_yield`; no independent raw source. |
| frequency / native frequency / unit | Daily / daily inputs / percentage points. |
| release lag / timezone | Available only after both validated input observations are available. Its availability timestamp is the later input availability timestamp; any missing input makes the result unavailable. |
| higher means / lower means | Steeper/flatter curve; economic interpretation depends on level, drivers, and regime. |
| transformation | `10Y − 2Y`, calculated only from same-date validated processed `us_treasury_10y_yield` and `us_treasury_2y_yield` observations. Processing version: `treasury_10y_minus_2y_percentage_points_v1`. Unit remains percentage points; do not multiply by 100. |
| expected start date | Intersection of verified input histories. |
| missing / revision policy | No processed spread row if either same-date current validated input is missing. Do not fill, interpolate, or pair mismatched dates. For each upstream indicator/date, select the approved direct processed row whose exact raw lineage matches the greatest valid stored FRED realtime vintage; a revision creates a new immutable spread output while preserving the methodology version and history. |
| publication timestamp available | Derived; governed by latest available input timestamp. |
| predictive or descriptive | Descriptive / potential leading research candidate; requires validation. |
| notes | Unit must not be mislabeled as basis points unless explicitly multiplied by 100. |

### Investment Grade OAS

| Field | Value |
|---|---|
| indicator_id | `us_investment_grade_oas` |
| category / subcategory | Credit / Investment-grade spreads |
| description / rationale | Option-adjusted spread for a defined U.S. investment-grade corporate-bond index; a measure of credit compensation and financial conditions. |
| source / identifier / reference | ICE Data Indices, LLC, ICE BofA Indices; FRED distribution series `BAMLC0A0CM`. [Series and terms](https://fred.stlouisfed.org/series/BAMLC0A0CM), [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html). |
| frequency / native frequency / unit | Daily, close / daily, close / percent (not basis points). |
| release lag / timezone | FRED displays `last_updated` and next release date but the underlying ICE publication time and observation timezone are **TBD / requires verification**. Do not infer an intraday availability time. |
| higher means / lower means | Wider/tighter spreads; neither is a standalone allocation action. |
| transformation | Phase 1.7A raw ingestion and Phase 1.7B direct normalization preserve FRED's native percentage-point level without transformation (`0.82` remains `0.82`). Processing version: `fred_credit_oas_direct_percentage_points_identity_v1`; transformation: `validated_identity_percentage_points`. |
| expected start date | FRED states that from April 2026 this distribution includes only three years of observations; do not treat it as a long-history source. Exact rolling-window start is dynamic. |
| missing / revision policy | Preserve missing and revisions. FRED states all data are subject to revision and supports real-time/vintage queries; weekend month-end observations can occur because of accrued-interest adjustments. |
| publication timestamp available | No documented observation-level publication timestamp in the FRED observations response; real-time fields are date-level. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Corporate Master OAS covers investment-grade (BBB or better) debt and is capitalization weighted. Phase 1.7A raw source contract is `fred` / `BAMLC0A0CM`; persist FRED `date` → `observation_date`, numeric `value` unchanged, `realtime_start`/`realtime_end` as vintage `fred_realtime:<start>:<end>`, and a null `publication_timestamp`. Phase 1.7B selects the greatest valid FRED realtime vintage per date, normalizes only finite values into `us_investment_grade_oas`, and records exactly one immutable `source` raw-lineage row; null source values create no processed observation. Phase 1.7C selects only the approved processed output whose exact raw lineage matches that current raw vintage, then calculates read-only 1D/5D/20D valid-observation-count differences in percentage points; insufficient history is unavailable. FRED API needs a registered key. ICE permits FRED top-level data for internal use only and prohibits publication/distribution without approval; confirm intended local storage/use against current terms before implementation. Its FRED availability is rolling/restricted, not a guaranteed full-history right. Index methodology may change; capture source metadata. |

### High Yield OAS

| Field | Value |
|---|---|
| indicator_id | `us_high_yield_oas` |
| category / subcategory | Credit / High-yield spreads |
| description / rationale | Option-adjusted spread for a defined U.S. high-yield corporate-bond index; reflects credit-risk pricing and risk appetite. |
| source / identifier / reference | ICE Data Indices, LLC, ICE BofA Indices; FRED distribution series `BAMLH0A0HYM2`. [Series and terms](https://fred.stlouisfed.org/series/BAMLH0A0HYM2), [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html). |
| frequency / native frequency / unit | Daily, close / daily, close / percent (not basis points). |
| release lag / timezone | FRED displays `last_updated` and next release date but the underlying ICE publication time and observation timezone are **TBD / requires verification**. Do not infer an intraday availability time. |
| higher means / lower means | Wider/tighter spreads; interpretation needs price, liquidity, and macro context. |
| transformation | Phase 1.7A raw ingestion and Phase 1.7B direct normalization preserve FRED's native percentage-point level without transformation. Processing version: `fred_credit_oas_direct_percentage_points_identity_v1`; transformation: `validated_identity_percentage_points`. |
| expected start date | FRED states that from April 2026 this distribution includes only three years of observations; do not treat it as a long-history source. Exact rolling-window start is dynamic. |
| missing / revision policy | Preserve missing and revisions. FRED states all data are subject to revision and supports real-time/vintage queries; weekend month-end observations can occur because of accrued-interest adjustments. |
| publication timestamp available | No documented observation-level publication timestamp in the FRED observations response; real-time fields are date-level. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | High Yield Master II OAS covers below-investment-grade (BB or below) debt and is capitalization weighted. Phase 1.7A raw source contract is `fred` / `BAMLH0A0HYM2`; persist FRED `date` → `observation_date`, numeric `value` unchanged, `realtime_start`/`realtime_end` as vintage `fred_realtime:<start>:<end>`, and a null `publication_timestamp`. Phase 1.7B selects the greatest valid FRED realtime vintage per date, normalizes only finite values into `us_high_yield_oas`, and records exactly one immutable `source` raw-lineage row; null source values create no processed observation. Phase 1.7C selects only the approved processed output whose exact raw lineage matches that current raw vintage, then calculates read-only 1D/5D/20D valid-observation-count differences in percentage points; insufficient history is unavailable. FRED API needs a registered key. ICE permits FRED top-level data for internal use only and prohibits publication/distribution without approval; confirm intended local storage/use against current terms before implementation. Its FRED availability is rolling/restricted, not a guaranteed full-history right. Do not mix OAS from differing vendor/index methodologies. |

### SOFR

| Field | Value |
|---|---|
| indicator_id | `sofr` |
| category / subcategory | Liquidity / Overnight funding |
| description / rationale | Secured Overnight Financing Rate, a broad overnight Treasury-repo funding measure. |
| source / identifier / reference | Federal Reserve Bank of New York (FRBNY), Secured Overnight Financing Rate; raw source `frbny`, series ID `SOFR`, official API rate type `SOFR`. [Official rate page](https://www.newyorkfed.org/markets/reference-rates/sofr), [publication/revision policy](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates), [official range API](https://markets.newyorkfed.org/api/rates/secured/sofr/search.json), [official latest API](https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json). |
| frequency / native frequency / unit | Business daily / business daily / percent per annum. |
| release lag / timezone | Published on each applicable business day at approximately 8:00 a.m. ET for the prior business day's transactions; same-day corrections may be published about 2:30 p.m. ET. Timezone: America/New_York. |
| higher means / lower means | Higher/lower overnight funding rate; interpretation requires policy target and market context. |
| transformation | Phase 1.6B direct validated identity normalization: `frbny` / `SOFR` → `sofr`; finite percent values remain unchanged (`3.62` remains `3.62`). Processing version: `frbny_sofr_direct_percent_identity_v1`. |
| expected start date | 2018-04-03. |
| missing / revision policy | Not published for SIFMA full-closure days and may not be published on other announced market holidays; preserve missing/non-publication days. Same-day revisions occur only when the change exceeds one basis point, with a revision footnote/indicator. |
| publication timestamp available | The API record supplies `effectiveDate`, `percentRate`, and `revisionIndicator`, but no per-observation publication timestamp. `effectiveDate` is the SOFR business/reference date (the prior business day's activity), not a publication date. Store `publication_timestamp` as null and record the timezone-aware local retrieval timestamp. |
| predictive or descriptive | Descriptive. |
| notes | Phase 1.6A uses `.../search.json?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&type=rate` for a bounded range and `.../last/1.json` for the latest record. Map `effectiveDate` → `observation_date`, `percentRate` → native-percent `value`, `revisionIndicator` → metadata and vintage `frbny_sofr_revision:<indicator-or-original>`; preserve the complete source record in metadata. Phase 1.6B recognizes only `original` and revised `r`: select `r` for a date when present, otherwise `original`; other state values fail explicitly. Each selected raw vintage creates an immutable processed identity and exact `source` lineage. Phase 1.6C selects, per date, only the processed `frbny_sofr_direct_percent_identity_v1` output whose source lineage exactly matches that selected raw vintage. Its read-only dashboard projection displays percent levels and observation-count 1D/5D/20D differences in percentage points; insufficient history is `N/A`. Phase 1.6D used the same range endpoint for the bounded 2026-06-19 through 2026-09-16 request; returned business-date history now supports 5D and 20D changes without altering methodology. The API does not expose an intraday revision timestamp or a historical copy of a revision that was not retrieved. Do not fabricate weekend, holiday, or other non-publication-day rows. The endpoints require no authentication in this local implementation; no rate-limit commitment was found in the cited official pages. SOFR is a volume-weighted median of specified Treasury-repo transactions; do not interpret it as total system liquidity. |

### MOVE Index

| Field | Value |
|---|---|
| indicator_id | `move_index` |
| category / subcategory | Volatility / Rates implied volatility |
| description / rationale | ICE BofA MOVE Index, a measure of implied volatility in U.S. Treasury markets. |
| source / identifier / reference | ICE Data Indices, ICE BofA U.S. Bond Market Option Volatility Estimate Index (MOVE). [Official product specification](https://developer.ice.com/fixed-income-data-services/catalog/ice-data-indices-move-index). ICE's public page does not disclose a production delivery identifier; it is **TBD / requires an ICE entitlement**. |
| frequency / native frequency / unit | ICE states intraday and daily availability; index-point unit and exact end-of-day convention are **TBD / requires verification with ICE**. |
| release lag / timezone | **TBD / requires verification with ICE**; no free public publication schedule was verified. |
| higher means / lower means | Higher/lower expected Treasury-market volatility; not direction. |
| transformation | Raw index level. |
| expected start date | ICE product specification says history since 1996; exact entitlements and available historical start must be confirmed with ICE. |
| missing / revision policy | **TBD / requires verification with ICE**. |
| publication timestamp available | **TBD / requires verification with ICE**. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | **Phase 1.8A classification: IMPLEMENTABLE WITH EXPLICIT USER-SUPPLIED ENTITLEMENT / CREDENTIAL.** ICE lists ICE Connect, ICE Consolidated History, ICE Consolidated Feed, ICE Data API, and ICE Data Files as delivery mechanisms, but the public product page requires login to inspect coverage and does not provide a free public historical endpoint. Before implementation, an ICE agreement and credential must establish the exact identifier, delivered fields and unit, EOD convention and timezone, publication-time field, revision/version behavior, retention/local-storage rights, and redistribution limits. The current raw schema is conditionally adequate only after these fields are contracted; do not invent a MOVE vintage or substitute an unofficial feed. |

### VIX

| Field | Value |
|---|---|
| indicator_id | `vix` |
| category / subcategory | Volatility / Equity implied volatility |
| description / rationale | Cboe Volatility Index, a model-based measure of S&P 500 option-implied volatility. |
| source / identifier / reference | Cboe, VIX Index historical daily-close download. [Official historical-data page](https://www.cboe.com/tradable_products/vix/vix_historical_data), [methodology](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf). Current linked download is `VIX_History.csv` at `https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` (an externally linked file, not a documented stable API). |
| frequency / native frequency / unit | Daily close / daily close / annualized implied-volatility index points. |
| release lag / timezone | Cboe says the historical file is updated daily; a fixed daily publication time is **TBD / requires verification**. The close convention must be retained as supplied by Cboe; do not infer an intraday timestamp. |
| higher means / lower means | Higher/lower implied volatility and protection demand; not a directional price forecast. |
| transformation | Raw close or specified timestamp; method must be explicit. |
| expected start date | Cboe states “1990 to present”; the exact earliest row was not reverified because the linked CSV returned HTTP 503 during the Phase 1.8A verification. |
| missing / revision policy | Preserve source values and non-trading-day gaps. The historical-page and methodology materials do not disclose a historical-file correction policy, source vintage, or observation-level publication timestamp. The current file schema is **TBD / requires an authorized successful retrieval**. |
| publication timestamp available | No observation-level publication timestamp was verified; store retrieval timestamp. |
| predictive or descriptive | Descriptive / confirmation. |
| notes | Cboe calculates VIX as an expected 30-day S&P 500 volatility measure from midpoint SPX-option quotes. The current methodology began in 2003; the pre-2003 original VIX used S&P 100 options and corresponds to VXO, so do not merge them. **Phase 1.8A classification: IMPLEMENTABLE WITH EXPLICIT USER-SUPPLIED ENTITLEMENT / CREDENTIAL.** The Cboe [Use of Content terms](https://www.cboe.com/use-of-content) require advance approval and a signed license for Cboe data use; the methodology also prohibits database storage without prior consent. The public linked file was unavailable during verification and has no documented API or correction/vintage contract. A user-supplied Cboe agreement must explicitly cover automated retrieval, local research storage, internal use, and any redistribution; it must also identify the supported delivery/schema and revision treatment. Without a disclosed source version, do not fabricate a raw vintage for later corrected same-date values. |

### S&P 500

| Field | Value |
|---|---|
| indicator_id | `spx` |
| category / subcategory | Equity / Broad U.S. equity index |
| description / rationale | S&P 500 Index level, a large-cap U.S. equity-market reference. |
| source / identifier / reference | S&P Dow Jones Indices LLC; FRED distribution series `SP500`. [Series and terms](https://fred.stlouisfed.org/series/SP500), [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html). |
| frequency / native frequency / unit | Daily, close / daily, close / index points (price index). |
| release lag / timezone | Observation is the market close, typically 4:00 p.m. ET and sometimes earlier on holidays. FRED shows `last_updated` in Central Time but a guaranteed publication time is **TBD / requires verification**. |
| higher means / lower means | Higher/lower price level; does not itself identify the underlying driver. |
| transformation | Raw close or explicitly specified observation timestamp; return series are derived separately. |
| expected start date | In the Phase 1.8A verification window, FRED SP500 covered 2016-09-19 through 2026-09-16. FRED says its agreement provides ten years of daily history, so the available start rolls forward. |
| missing / revision policy | Preserve source gaps and corrections; FRED states data are subject to revision and offers vintage functionality. Do not imply total return from the price index. |
| publication timestamp available | No observation-level publication timestamp was verified from FRED; record retrieval timestamp. |
| predictive or descriptive | Descriptive. |
| notes | **Phase 1.8A classification: IMPLEMENTABLE WITH EXPLICIT USER-SUPPLIED ENTITLEMENT / CREDENTIAL.** Conditional on rights, use source `fred`, series `SP500`, FRED `date` as `observation_date`, and numeric `value` unchanged as index points; retain `publication_timestamp` as null, a timezone-aware UTC retrieval timestamp, `fred_realtime:<start>:<end>` vintage, and the existing FRED realtime/raw-value/missing metadata. The raw schema fits this conditional contract. FRED API requires a registered API key and supports realtime/vintage parameters, but FRED's reviewed terms prohibit storing, caching, or archiving FRED/API content in a database and do not override third-party rights; S&P says reproduction requires prior written permission. An API key alone is insufficient: the user must supply an arrangement expressly permitting local database persistence plus written S&P rights for the intended use. FRED exposes series-level `last_updated` in Central Time, not an observation-level publication timestamp; preserve trading-day gaps and do not infer availability time. The series is a price index, not a total-return index. |
