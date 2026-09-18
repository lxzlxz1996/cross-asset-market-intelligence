# SOFR Rate State production versions

## Version matrix

| Outer identity | Status | Components | State fields |
|---|---|---|---|
| `sofr_rate_state/v1` | Active / frozen | `sofr_change_rarity_v1` anomaly evidence only | `level_state=null`, `direction_state=null`, `anomaly_state=null` |
| `sofr_rate_state/v2` | Active | Unchanged `sofr_change_rarity_v1` plus `sofr_direction_evidence_v1` | `level_state=null`, `direction_state=null`, `anomaly_state=null` |
| `sofr_rate_state/v3` | Active | Unchanged anomaly and Direction plus `sofr_level_evidence_v1` | `level_state=null`, `direction_state=null`, `anomaly_state=null` |

Version 1 remains immutable and reproducible. Version 2 is a new definition and observation identity; it does not update, migrate, reinterpret, or backfill-overwrite v1. Level methodology is not implemented in either version.

The [SOFR Level methodology v1](SOFR_LEVEL_METHODOLOGY_V1.md) is implemented in v3. Adding Level changes the outer economic question, parameter definition, explanation, evidence payload, and lineage, so v3 is a distinct immutable definition and does not mutate v2.

## Generation interface

Generation is explicitly versioned:

```powershell
python -m cross_asset_market_intelligence generate-sofr-rate-state --version v1 --as-of YYYY-MM-DD
python -m cross_asset_market_intelligence generate-sofr-rate-state --version v2 --as-of YYYY-MM-DD
python -m cross_asset_market_intelligence generate-sofr-rate-state --version v3 --as-of YYYY-MM-DD
```

`--version` defaults to `v1` so the pre-v2 command retains its established behavior. There is no `latest` alias.

Programmatic interfaces:

```text
generate_sofr_rate_state(...)      # v1
generate_sofr_rate_state_v2(...)   # v2
generate_sofr_rate_state_v3(...)   # v3
```

All three use the Phase 2.1A immutable definition, deterministic observation identity, idempotent persistence, honest availability, and exact ordered processed-input lineage contracts. `--version` still defaults to v1; callers must select v2 or v3 explicitly.

## V2 evidence composition

V2 preserves the v1 anomaly fields and values unchanged, then adds `direction_evidence` under the frozen [SOFR Direction methodology v1](SOFR_DIRECTION_METHODOLOGY_V1.md). The shared ordered `sofr_level_history` contains the minimum available suffix up to 254 unique levels. Direction uses the last 21 levels; its secondary slope uses the last 20. No duplicate Direction lineage rows or schema extension are used.

Warm-up boundaries are component-specific:

- fewer than 20 total valid changes: Direction unavailable;
- 20 or more total valid changes: Direction available;
- fewer than 60 prior changes before the current change: recent anomaly unavailable;
- 60 or more prior changes: recent anomaly available;
- 252 or more prior changes: broad anomaly available.

The outer quality remains governed by the frozen anomaly/availability rules. Direction availability never promotes it.

## Non-goals

V2 adds no Level evidence, categorical Direction or anomaly state, magnitude/materiality threshold, step/reversal classifier, policy/FOMC cause, holiday adjustment, Phase 3 relationship, portfolio logic, or trade interpretation.

## V3 evidence composition

V3 preserves v2 anomaly and Direction calculations and adds only `sofr_level_evidence_v1`: raw current level, expanding prior-only tie-audited historical rank, and prior-60 median distance. One growing ordered `sofr_level_history` set supplies all components; Level's expanding history contains the shorter anomaly, Direction, and recent-Level suffixes. At 2026-09-16 this is 2,112 exact links. V3 does not imply a categorical Level state, policy regime, funding-stress conclusion, or outer-quality promotion. Exact expanding lineage is accepted specifically for this SOFR Level methodology and is not a default architecture rule for other signals.
