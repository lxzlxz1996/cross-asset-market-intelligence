# Phase 2.1A — Signal Engine Foundation

## Purpose and boundaries

A Signal is a versioned, reproducible, economically interpretable statement derived from validated processed observations under a defined information set. Phase 2.1A creates only the contract and audit infrastructure. It does not implement quantitative SOFR methodology, thresholds, classifications, cross-asset interpretation, regimes, backtests, portfolio actions, forecasts, or LLM-generated states.

The chain is `processed observations → evidence → orthogonal state dimensions → deterministic explanation`. Evidence is structured numerical or factual input (`some_measure: 2.4`); a state is a methodology-derived label (`anomaly_state: unusual`). Neither is a trade or regime conclusion.

## Contracts and versioning

`signal_definitions` holds immutable methodology metadata identified by `(signal_id, signal_version)`: economic question/hypothesis, what it measures and does not mean, limitations, methodology description, structured parameter definition, and lifecycle (`draft`, `active`, `deprecated`). Any changed methodology or threshold contract requires a new version such as `v2`; old definitions remain resolvable.

`signal_observations` records a deterministic statement for one as-of information set. `level_state`, `direction_state`, and `anomaly_state` are independent nullable dimensions: `rising` and `unusual` can coexist. `evidence_quality` is `sufficient`, `limited`, or `insufficient`, with structured `quality_reasons`; it describes evidence completeness, not probability of a correct market interpretation.

`signal_observation_inputs` records every exact `processed_observation_id` used. `input_role` is extensible. `window_position` is nullable for unordered roles; in an ordered window, `window_position=0` means the oldest input, increasing toward the current input. A date range alone is not lineage.

## Point-in-time semantics

- `as_of_observation_date`: economic date represented by latest evidence.
- `information_available_at`: exact known availability time, only when genuinely known.
- `calculated_at`: when this system generated the record.

`information_available_date` exists only for `date_only`, avoiding fabricated midnight timestamps. `availability_precision` is `exact_timestamp`, `date_only`, `source_schedule`, or `unknown`. Unknown availability without a timestamp/date is valid. The foundation rejects processed inputs after the as-of date. It cannot infer unrecorded intraday availability from Phase 1 data; later methodologies must apply stricter source-specific rules where available.

## Identity and deterministic explanations

Observation IDs are SHA-256 hashes of canonical JSON containing definition/version, time semantics, parameters, and complete ordered inputs. Calculation time and calculated output are excluded. Identical replays are idempotent; a replay with the same deterministic identity but different evidence, states, quality, or explanation is rejected as a methodology inconsistency rather than persisted as a duplicate. Different input IDs, versions, parameters, or availability semantics yield distinct identities. Incompatible reuse of a stored definition version is rejected through the persistence API.

Explanations use a small named-field deterministic template function. An LLM may be a future UI rephraser only; it cannot determine or alter a persisted state. Database foreign keys preserve the chain from a signal observation to processed observations and then existing Phase 1 raw lineage.

## Conceptual example

```text
signal_id: example_signal
signal_version: v1
direction_state: rising
anomaly_state: unusual
evidence_quality: sufficient
evidence:
  some_measure: 2.4
```

This is a contract example, not a production market signal.
