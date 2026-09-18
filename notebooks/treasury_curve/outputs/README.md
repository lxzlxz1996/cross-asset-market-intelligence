# Phase 2.2D — Treasury 2s10s framework validation

This is offline, bounded research over validated local Phase 1 `DGS2` and `DGS10`. It tests multi-input alignment, exact lineage, state governance and `research_artifacts_v1`. It creates research files, with no source retrieval or market-database writes.

## Reproduce from the repository root

```powershell
.\.venv\Scripts\python.exe notebooks/treasury_curve/analyze.py
.\.venv\Scripts\python.exe notebooks/treasury_curve/validate.py
.\.venv\Scripts\python.exe -m cross_asset_market_intelligence validate-research-artifacts notebooks/treasury_curve/outputs
```

`analyze.py` exports actual selected inputs and invokes an independent validator. The validation entrypoint never imports the research calculator. The generic CLI emits structured JSON and exits 0 for passed/acceptable warnings and 1 for failure. `validate.py --snapshot-only` can check portable exports but explicitly cannot establish original database ID resolution.

Entrypoints: `notebooks/treasury_curve/analyze.py`, `notebooks/treasury_curve/validate.py`. Exact question, candidate grid, exclusions and availability boundaries are in `notebooks/treasury_curve/research_contract.json`. Semantic synthetic fixtures are in `notebooks/treasury_curve/synthetic_cases.json`. These files and executed helpers are hashed in the manifest. The report template is retained at `notebooks/treasury_curve/report_template.md`.

## Input and environment prerequisites

Use Python >=3.11 and project dependencies from `pyproject.toml`; actual runtime versions are saved in `outputs/environment.json`. `data/market_intelligence.duckdb` must contain validated current-vintage direct processed Treasury rows and the existing same-date derived observations with exact dependencies. Current local coverage is only ten aligned dates. Local permitted research use follows the existing Phase 1 source contract; no new source or entitlement is inferred. The source database is not redistributed by this package.

Research snapshot ordering is `(observation_date, two_year then ten_year)`. Global position enumerates selected leg records, with separate `role_position` sequences. Two same-date inputs are a pair, not adjacent time-series observations. There is no merged single current leg: `current_input_position` is null; each role has its own deterministic current endpoint. Candidate calculations use one curve observation per aligned date. No filling, interpolation or inserted non-business dates occurs.

## Artifact map

| Artifact | Owner/grain |
| --- | --- |
| `manifest.json` | Run/input/code/config identity and inventory; selected count means leg records |
| `selected_observations.json` | Actual processed leg records, values, availability and FRED vintages |
| `aligned_levels.csv` | One same-date curve observation; both exact leg IDs and existing derived ID |
| `alignment_audit.csv` | One retained raw date; absent/null/unprocessed/available leg statuses |
| `research_results.csv` | One aligned date/candidate; complete-window warm-up, metric units and separate magnitude/CDF fields |
| `method_comparison.csv` | Candidate eligibility, tie-band and slope-versus-endpoint diagnostics |
| `case_studies.csv` | Observed or explicitly synthetic case, never mixed in observed distributions |
| `synthetic_fixtures.json` | Exact synthetic expectations; anchor dates are labels only |
| `research_brief.json` | The economic/input/grid contract |
| `framework_scorecard.csv` | One framework capability and compatibility issue |
| `environment.json` | Minimal runtime/dependency identity |
| `results.json` | Authoritative machine-readable conclusions and research decision |
| `validation.json` | Independent checks and bounded limitations |
| `report.md` | Human narrative and matching research decision |
| `README.md` | Reproduction and artifact map |

All conditional artifacts are applicable and present; no omissions or empty placeholders. CSV rows follow as-of then declared candidate order; comparison rows follow candidate order; cases follow named deterministic selection/fixture order. Empty numeric fields mean documented warm-up, inapplicable metric or undefined zero-gross-path retention; there is no shorter-reference fallback. CDF reference dates refer to level dates or change-ending dates; a change also needs the preceding level, which remains in the exact snapshot.

This package can validate structurally while its research outcome remains `MORE_RESEARCH_REQUIRED`. Package integrity does not promote an incomplete economic study to methodology-freeze readiness. `results.json` owns conclusions; `report.md` owns narrative. No production curve signal, recession forecast, trading rule, portfolio allocation or Phase 3 relationship is created.
