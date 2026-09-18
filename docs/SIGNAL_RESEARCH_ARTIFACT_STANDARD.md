# Phase 2.2B — Signal Research Artifact Standard

## Status, authority, and scope

**Artifact-standard status:** frozen as `research_artifacts_v1`.

This document is the authoritative Phase 2 research-artifact contract. It standardizes package identity, provenance, relationships, serialization, validation, and finalization without standardizing indicator economics, formulas, windows, metrics, charts, evidence dimensions, or state logic. It refines the artifact boundary in the frozen [Signal Research Framework](SIGNAL_RESEARCH_FRAMEWORK.md).

The standard applies to future Rates, Curve, Funding, and Credit research. It is a file contract, not a database schema, signal methodology, calculation library, storage service, or Phase 3 decision rule.

## Governing principles

1. A package must be reproducible without relying on memory or chat history.
2. Provenance, findings, validation, and narrative have distinct authoritative owners.
3. Mandatory artifacts are few; conditional artifacts exist only when the research actually needs them.
4. Generic envelopes are strict. Indicator-specific findings remain extensible.
5. Exact selected-input identity is separate from display formatting and file-byte identity.
6. Structural failure prevents successful finalization; it is not encoded as an ordinary null.
7. Repository-relative portable references replace absolute workstation paths.
8. No finalized artifact may contain credentials, secrets, fabricated availability, or non-finite JSON numbers.

## Standard package layout and naming

Conventional names are normative when the corresponding logical artifact exists:

```text
<research-root>/
    manifest.json
    selected_observations.json        # conditional
    research_results.csv              # conditional
    method_comparison.csv             # conditional
    case_studies.csv                  # conditional
    results.json
    validation.json
    report.md
    README.md
    <justified additional artifacts>  # optional
```

Do not create empty placeholder files. Do not use mutable names such as `final_results2.json`. Additional artifacts require a stable descriptive name and a manifest entry.

All artifact paths stored inside artifacts are repository-relative, use `/`, and contain no drive letter, leading slash, or `..` traversal. An absolute runtime path may appear in an uncommitted local log, but never defines package identity or reproducibility.

## Requiredness

### Mandatory in every finalized package

| Artifact | Required role |
|---|---|
| `manifest.json` | Run identity, input/code/config provenance, artifact inventory, and mirrored package statuses. |
| `results.json` | Machine-readable measured facts, interpretations, recommendations, limitations, and authoritative research decision. |
| `validation.json` | Machine-readable independent checks and authoritative validation status. |
| `report.md` | Human review narrative with evidence/interpretation/recommendation separation and the research outcome. |
| `README.md` | Reproduction entrypoints, environment assumptions, artifact map, scope, and non-goals. |

Research and validator code are also mandatory capabilities, but need not be copied into the output folder. `manifest.json` references their repository-relative entrypoints and hashes.

### Conditionally mandatory

| Artifact | Trigger |
|---|---|
| `selected_observations.json` | The research uses selected market observations or another ordered/cross-sectional input snapshot. Omit only when no observation dataset exists; manifest must record `not_applicable` and why. |
| `research_results.csv` | A decision depends materially on per-observation, per-as-of, or other row-level calculated evidence. |
| `method_comparison.csv` | Two or more genuinely plausible methods, windows, or parameterizations were empirically compared. |
| `case_studies.csv` | Named historical or exact synthetic cases materially support interpretation, failure analysis, or the recommendation. |

When a conditional artifact is omitted, `manifest.json` records the logical role, `not_applicable`, and a non-empty rationale. An empty substitute is invalid.

### Optional

Charts, rendered notebooks, diagnostic tables, secondary exports, and presentation assets are optional. They may support review but do not replace machine-readable evidence. Every retained optional artifact is listed and hashed in the manifest.

## Authoritative field ownership

| Information | Authoritative artifact | Mirrors / references |
|---|---|---|
| Research/version/run identity | `manifest.json` | `results.json` and `validation.json` repeat identifiers only for consistency validation. |
| Input selection, code, configuration, execution, and artifact inventory | `manifest.json` | README explains how to use it. |
| Exact selected input sequence/set | `selected_observations.json` | Manifest owns its semantic snapshot hash and raw-file hash. |
| Row-level calculated evidence | `research_results.csv` | Results and report cite it; they do not redefine its rows. |
| Measured conclusions and research readiness decision | `results.json` | Manifest mirrors decision status; report repeats the conclusion for humans. |
| Independent check details and validation status | `validation.json` | Manifest mirrors validation status. |
| Human interpretation and review narrative | `report.md` | It cites machine-readable evidence. |
| Reproduction instructions and artifact map | `README.md` | It does not duplicate findings. |

Mirrored fields must match their authoritative owner. A mirror is never an alternate source of truth.

## `manifest.json` contract

`manifest.json` answers: **what run is this, what exact inputs/code/configuration produced it, and what artifacts belong to it?** It does not contain detailed economic conclusions.

The generic envelope is validated by [`manifest.schema.json`](research_artifacts/manifest.schema.json). Required concepts are:

| Area | Required content |
|---|---|
| Standard identity | `artifact_standard_version`, fixed to `research_artifacts_v1`. |
| Research identity | `research_id`, `research_version`, and content-derived `run_id`. |
| Subject | Existing or proposed signal ID, component/research subject, and non-empty indicator IDs. |
| Package status | `research_status`, plus mirrored validation and decision statuses. |
| Dataset | Observation count/range, snapshot hash or explicit non-applicability, selection rule, source/series IDs, vintage and availability summaries. |
| Execution | UTC execution time, Git commit or reason unavailable, working-tree state/diff hash, entrypoints, code-file inventories/aggregate hashes, and minimal runtime/environment identity. |
| Candidates | Stable candidate IDs and exact parameter/configuration declarations. |
| Inventory | Logical name, repository-relative path, type/media type, requiredness, raw-file SHA-256, authority role, storage policy, and CSV column metadata where applicable. |
| Omissions | Conditional roles omitted as `not_applicable` with rationale. |

The manifest itself is implicit and is not listed in its own artifact inventory because a self-hash is circular. All other retained package artifacts are listed exactly once.

### Working-tree state

`working_tree_state` is one of `clean`, `dirty`, or `unavailable`.

- `clean`: `git_commit` identifies the repository content; `working_tree_diff_hash` is null.
- `dirty`: record the base `git_commit`. Set `working_tree_diff_hash` to SHA-256 of the raw bytes emitted by `git diff --binary HEAD -- <sorted declared tracked code/config paths>`. Record the scoped command in reproducibility notes. Do not embed the full diff in the artifact package.
- `unavailable`: both Git fields may be null, but `git_commit_unavailable_reason` is mandatory and the package must use entrypoint/code hashes sufficient to identify executed code.

A commit alone never claims to identify dirty code.

`research_code_files` and `validator_code_files` list repository-relative paths and raw-byte hashes for the entrypoints and directly executed/imported research-owned files. Untracked relevant files therefore remain identifiable even though Git diff does not contain them. Each aggregate `*_code_hash` is SHA-256 of the `canonical_json_v1` serialization of its path-sorted code-file list. Git commit/diff identity covers the wider tracked repository context; the code-file list identifies the immediate executable surface.

### Runtime/environment metadata

Record language/runtime name and version. Reference and hash a lockfile or environment specification when dependency versions could change the result. Do not dump a workstation environment or secrets into the manifest.

## `selected_observations.json` contract

This artifact records the exact processed observations or external input identities selected for the research snapshot. It is an input identity artifact, not a duplicate raw-data archive.

The top-level envelope records:

```text
artifact_standard_version
research_id
research_version
run_id
ordering
snapshot_identity_profile = canonical_selected_inputs_v1
observations
```

Each repository-backed observation records at least:

```text
position
indicator_id
processed_observation_id
observation_date
processing_version
information_available_at
availability_precision
retrieved_at
```

A display value/unit is included when needed to audit calculations. Exact processed IDs link through the frozen Phase 1 lineage; the artifact does not copy full raw records.

If an input is not represented by a project processed-observation ID, it must instead carry an `external_input_identity` containing stable source, series, revision/vintage, observation-date, value-as-normalized-decimal-string, unit, and availability identity. Licensed data may use permitted vendor record identifiers and hashes rather than copying prohibited source values; limitations must be explicit.

### Ordering

- A chronological single-series selection uses zero-based contiguous positions, oldest to newest.
- Multi-series, cross-sectional, or role-grouped research declares its ordering keys and role structure explicitly.
- Array order is identity-bearing. Duplicate positions or accidental duplicate input identities are invalid.
- No universal chronological order is imposed where the research question requires another structure, but the structure must be deterministic and documented.

## Selected-input snapshot identity

`selected_input_snapshot_hash` uses the `canonical_selected_inputs_v1` profile and is formatted `sha256:<64 lowercase hexadecimal characters>`.

For repository-backed observations, the canonical identity projection contains, in declared order:

```text
position
indicator_id
processed_observation_id
observation_date
processing_version
information_available_at
availability_precision
retrieved_at
```

The processed ID already binds the canonical value and exact upstream lineage, so those are verified by resolution rather than duplicated in the identity projection. For external inputs, the full `external_input_identity` described above replaces the processed ID and is part of the projection.

The projection is serialized using `canonical_json_v1`:

1. UTF-8 bytes with no BOM;
2. object keys sorted lexicographically;
3. arrays retained in declared order;
4. separators exactly `,` and `:` with no insignificant whitespace;
5. non-ASCII characters encoded directly as UTF-8 JSON strings (`ensure_ascii=False`), matching the established project canonical-identity convention;
6. decimal values represented as normalized strings when included;
7. no `NaN`, `Infinity`, or `-Infinity`.

The hash is SHA-256 of those canonical bytes. Pretty-printing the selected-observation file therefore does not alter snapshot identity. Changing an ordered identity, revision, processing version, or availability identity does.

## Artifact file hashing

Every manifest-listed file has `raw_file_hash = sha256:<hex>` computed over the exact stored file bytes. There is no newline, Unicode, JSON, or CSV normalization for a raw-file hash. A formatting-only rewrite intentionally changes the raw-file hash even when a semantic snapshot hash remains stable.

This separation prevents confusion:

- semantic selected-input identity → canonical snapshot hash;
- exact retained artifact identity → raw-byte file hash.

## `research_results.csv` contract

This artifact is required when row-level evidence materially supports the decision.

- One row represents one explicitly documented grain such as research observation/as-of, cross-section member/as-of, or event/case/offset.
- Stable key/date columns identify the grain.
- There is no implicit DataFrame/index column.
- Header names are stable, unique, and machine-oriented.
- Units and non-obvious null meanings are declared in the manifest's column metadata.
- Row ordering is deterministic and documented.
- Indicator-specific quantitative columns are allowed; there is no universal metric schema.

If the research is structural and has no meaningful row-level dataset, omit the file and record why.

## `method_comparison.csv` contract

This file preserves measured comparisons when genuine methodological ambiguity exists. It must include stable `method_id` and `parameter_set_id` fields plus enough eligibility, behavior, limitation, and unit metadata to interpret research-specific quantitative columns.

It must not invent an aggregate ranking score. Narrative interpretation belongs in `results.json` and `report.md`; measured comparison fields remain distinguishable from interpretation fields.

## `case_studies.csv` contract

The minimum stable fields are:

```text
case_id
case_name
anchor_date
case_type
selection_reason
relevant_method_id
```

Add structured evidence columns appropriate to the signal. Do not force all evidence into one giant text cell. Exact synthetic cases must be labeled synthetic and must never be mixed silently with observed history.

## `results.json` contract

`results.json` answers: **what was measured, how was it interpreted, what design is recommended, and is the research ready for methodology freeze?** It does not own code/input provenance.

The generic envelope is validated by [`results.schema.json`](research_artifacts/results.schema.json) and contains:

```text
artifact_standard_version
research_id
research_version
run_id
research_status
measured_facts
research_interpretations
design_recommendations
method_comparison_summary
recommended_evidence_design
recommended_horizon_or_reference_design
state_recommendation
known_failure_modes
indicator_specific_findings
deferred_questions
production_readiness_decision
```

The envelope is strict; `indicator_specific_findings` and the recommendation payloads may contain signal-specific structures. A measured fact carries a stable `fact_id` and evidence references. Interpretations cite fact IDs. Recommendations cite the evidence or interpretations that justify them. An empirical metric cannot silently become a frozen production decision.

The authoritative decision is exactly one of:

```text
READY_FOR_METHODOLOGY_FREEZE
MORE_RESEARCH_REQUIRED
BLOCKED_BY_DATA_OR_ARCHITECTURE
```

## `validation.json` contract

`validation.json` answers: **which independent checks were run, against what targets, how, and with what outcome?**

The generic envelope is validated by [`validation.schema.json`](research_artifacts/validation.schema.json). Each check has a stable ID, description, method, target references, severity, pass/fail result, and optional expected/observed/invariant fields. Expected/observed values are not required for purely structural boolean checks.

The authoritative validation status is one of:

```text
passed
passed_with_warnings
failed
```

`failed` prevents finalization. `passed_with_warnings` is finalizable only when every warning is explicitly non-blocking and bounded in `unresolved_limitations`.

### Independent validation meaning

Independent does not mean a different programming language. It means critical results are not checked merely by calling the same calculator again. Accepted paths include independent SQL, a separate implementation that does not import the calculator under test, exact fixtures, manual golden calculations, algebraic invariants, and structural validation appropriate to the method.

Quantitative research must independently validate formula-critical behavior, units, input snapshot identity, ordering/current-future exclusion, warm-up, missingness, and selected golden cases. The validator entrypoint and code hash are recorded.

## `report.md` contract

The report is the human review narrative. Its chapter names may vary, but it must visibly separate:

```text
MEASURED FACT
RESEARCH INTERPRETATION
DESIGN RECOMMENDATION
DEFERRED QUESTION
```

It documents scope, data/time limitations, methods considered, failure modes, golden cases, validation, and one exact research readiness outcome matching `results.json`. It must cite artifacts rather than restating large tables.

## `README.md` contract

Every finalized research folder has a README containing:

- scope and explicit non-goals;
- repository-relative research and validator entrypoints;
- reproduction commands and environment assumptions;
- artifact map and conditional omissions;
- input/source prerequisites and licensing limits;
- note that the report owns narrative while results owns machine-readable conclusions.

It does not duplicate the report.

## Artifact and research versioning

These identities are independent:

| Identity | Meaning | Typical change trigger |
|---|---|---|
| `artifact_standard_version` | Shape/semantics of this packaging contract. | Breaking envelope, serialization, hash, or ownership change. |
| `research_id` | Stable lineage for one economic research subject. | Fundamentally different economic subject/question. |
| `research_version` | Immutable semantic design of that research. | Formula, candidate universe/grid, selection contract, or material interpretation-boundary change. |
| `run_id` | Content identity of one code/input/configuration combination. | Snapshot, code hash, or declared candidate configuration changes. |
| `methodology_id` | Frozen production component methodology. | Frozen methodology semantic change. |
| `signal_version` | Outer production signal composition/contract. | Outer composition or compatibility change. |

`artifact_standard_version` is `research_artifacts_v1`; it is not a signal or methodology version.

### Same identity, rerun, or new version

- Same `research_id` + `research_version` + snapshot hash + research-code hash + exact candidate configuration produces the same logical `run_id`; a later execution is a rerun.
- A changed selected snapshot creates a new run ID but does not alone require a new research version.
- A code refactor that preserves semantics changes the run ID through its code hash; document equivalence.
- A research formula, input-selection contract, material parameter grid, or candidate-set change creates a new research version.
- A materially different economic question creates a new research ID; a clarified boundary within the same subject may use a new research version.

`run_id` is `run_sha256:<hex>` over a canonical identity object containing artifact-standard version, research ID/version, selected snapshot hash or explicit no-data token, research code hash, candidate IDs, and exact declared configurations. Execution timestamp and output file hashes are excluded.

## JSON serialization

- UTF-8, no BOM, valid JSON objects/arrays, and no duplicate object keys.
- Only finite JSON numbers; `NaN`, `Infinity`, and `-Infinity` are prohibited.
- Use JSON `null` only where the field contract permits it and its semantic reason is declared.
- Decimal arithmetic is required only where equality, ties, or unit conversion demand it; not every calculation must use Decimal.
- Equality-sensitive decimal values may be serialized as normalized decimal strings when the schema/documentation declares that representation.

## CSV serialization and metadata

- UTF-8, comma-delimited, one header row, RFC 4180 quoting, and deterministic row order.
- No hidden index column and no non-finite tokens.
- Missing scalar values use an empty field, never `NaN`, `Inf`, `N/A`, or locale-specific text.
- When reasons differ materially, pair the value with a status column using documented values such as `available`, `insufficient_history`, `not_applicable`, or `unknown_availability`.
- Structural failure aborts finalization rather than appearing as an empty field.

The preferred column contract is inline manifest metadata for every key/date/status field and every quantitative field whose unit is not self-evident. Metadata records column name, logical type, unit or explicit `not_applicable`, description, and null semantics. The inventory records `row_count` when a retained tabular artifact has an authoritative row count. A large reusable column specification may be a separately listed and hashed repository-relative sidecar; it cannot be an untracked convention.

### Executable selected-input convention

The generic validator recognizes `canonical_selected_inputs_v1`. `selected_observations.json` therefore carries an `ordering` object with `position_semantics` (`zero_based_contiguous` or `unique_positions`), `direction` (`oldest_to_newest`, `newest_to_oldest`, or `declared`), `date_order_required`, `current_input_position` (integer or null), and `as_of_observation_date` (ISO date or null). Each selected observation has its declared position, indicator ID, observation date, processing version, availability identity/precision, retrieval timestamp, and either a processed-observation ID or explicit external input identity. This specifies mechanical reproducibility only; it does not impose an economic window, transform, or calendar convention.

## Units

Ambiguous names such as `change`, `spread`, or `distance` are invalid without unit metadata. Use explicit unit strings such as `percent`, `percentage_point`, `basis_point`, `ratio`, `count`, or `index_point` when applicable. The vocabulary remains extensible, but conversion and scale semantics must be written exactly once in authoritative column metadata.

## Date and timestamp formats

- Observation dates: ISO 8601 full-date `YYYY-MM-DD`.
- Execution, retrieval, and exact availability timestamps: RFC 3339/ISO 8601 with timezone, normalized to UTC `Z` in finalized envelopes.
- Date-only availability uses a full date plus `availability_precision = date_only`.
- Unknown availability uses null plus `availability_precision = unknown`; it is never inferred from retrieval time.
- Locale dates and timezone-free timestamps are invalid.

## Null and missing semantics

The contract distinguishes:

```text
insufficient_history
not_applicable
unknown_availability
ordinary missing source value
structural failure
```

JSON null or a blank CSV cell is a representation, not a meaning. The surrounding field/status contract supplies the meaning. Structural failure is not serializable as a successful result and blocks the package.

## Schema strategy

Phase 2.2B supplies three Draft 7 JSON Schemas:

- [`manifest.schema.json`](research_artifacts/manifest.schema.json)
- [`results.schema.json`](research_artifacts/results.schema.json)
- [`validation.schema.json`](research_artifacts/validation.schema.json)

They strictly validate generic envelopes, identifiers, statuses, hashes, and core relationships while allowing indicator-specific objects only at named extension points. This phase deliberately does not create a universal statistical-results schema or a universal CSV column schema.

The example envelopes in [`docs/research_artifacts/examples`](research_artifacts/examples/) are documentation fixtures, not empirical results.

## Cross-file consistency invariants

A finalized package satisfies all of the following:

1. `artifact_standard_version`, `research_id`, `research_version`, and `run_id` match across manifest, results, validation, and selected inputs when present.
2. Manifest `decision_status` equals the authoritative `results.json` decision and the exact report conclusion.
3. Manifest `validation_status` equals the authoritative `validation.json` status.
4. Selected-input snapshot hash recomputes from the declared profile and matches the manifest.
5. Dataset count/date range agrees with selected inputs where applicable.
6. Every retained artifact except manifest is listed once; every non-null repository path exists, while an external item has a declared external reference and expected hash.
7. Every raw-file hash matches exact file bytes.
8. Every mandatory artifact exists; conditional artifacts either exist or have a declared non-applicability rationale.
9. CSV headers match their declared column metadata; required unit/null semantics exist.
10. Results evidence references and validation targets resolve to listed artifacts/IDs.
11. No finalized JSON contains non-finite values, duplicate keys, absolute paths, or secrets.
12. No future or unknown-availability claim is silently converted into a point-in-time-valid claim.

Repeated values are limited to identifiers and status mirrors needed for package-level validation.

## Research code and notebooks

Scripts, SQL, notebooks, or combinations are supported. Entrypoints and relevant code files are repository-relative and hashed. A notebook's output cells are never the sole authoritative result: its exported machine-readable artifacts are authoritative. If notebook output cells are retained, declare whether they are cleared, deterministic, or review-only. Prefer a deterministic script/export when practical.

## Large artifacts and storage

There is no universal byte threshold. Before finalization, document expected size/growth, regeneration cost, audit need, source license, and version-control impact. Each inventory item declares one storage policy:

```text
committed
regenerable_not_committed
external_reference
```

Non-committed or external artifacts still require a stable locator/identity, expected hash, access limitation, and reproduction path. Phase 2.2B does not implement external artifact storage. Exact reconstruction must not depend on an opaque cache.

## Secrets and proprietary data

Artifacts may not contain API keys, credentials, tokens, connection strings with secrets, or accidental environment dumps. Proprietary/licensed research records source identity, entitlement boundary, permitted identifiers/hashes, and reproduction limitations without copying prohibited datasets. A package that cannot legally include source values may still preserve permitted identities and exact internal lineage, but must not claim public reproducibility.

## Finalization gate

A package is structurally finalized only when:

- mandatory and triggered conditional artifacts are present;
- all three generic envelopes validate;
- manifest inventory, raw-file hashes, and snapshot identity validate;
- cross-file IDs, statuses, counts, dates, paths, references, and column contracts agree;
- independent validation is `passed`, or `passed_with_warnings` with only explicit non-blocking limitations;
- JSON/CSV/date/unit/null conventions pass;
- one exact research outcome is present;
- paths are portable and links resolve;
- no secrets or prohibited source data are present;
- no structural failure remains.

Failure means **the research package is not structurally finalized**. It cannot be repaired by prose assertion. Structural finalization may record any schema-valid research outcome, including `MORE_RESEARCH_REQUIRED`; it is not economic approval. A methodology-freeze gate additionally requires `READY_FOR_METHODOLOGY_FREEZE` and the framework's substantive research/validation conditions. A generic validator pass never grants that decision.

## Validator boundary (Phase 2.2C)

The implemented command is:

```text
validate-research-artifacts <research_dir>
```

Phase 2.2C implements schema loading; canonical snapshot and run hashing; raw-file hashing; path/safety checks; inventory/requiredness checks; CSV header/unit/null checks; cross-file identity/status/reference checks; selected-input ordering/no-future validation; non-finite scans; secret-pattern guardrails; explicit rate-difference-to-bp conversion; and strict named-field rendering. It does not calculate indicator metrics, choose methods, create state thresholds, or infer economic conclusions.

Phase 2.2B implements no reusable helper or validator command.

## SOFR compatibility assessment

Existing SOFR artifacts are not migrated. Compatibility is assessed as follows:

| Study | Already available | Missing for `research_artifacts_v1` | Representable without methodology change? |
|---|---|---|---|
| Anomaly | Selected observations and exact processed IDs; input snapshot hash; code/commit hashes; dataset range/counts; row-level results; method/window comparisons; event cases; independent SQL validation; reports/README. | Separate manifest; run ID; dirty-tree state/diff hash; uniform result/validation envelopes; artifact inventory/raw hashes; portable database reference; explicit column/unit/null metadata; exact readiness mirror. | Yes. Packaging/provenance can be adapted without changing anomaly formulas, windows, or conclusions. |
| Direction | Selected observations; snapshot/script/commit hashes; dataset range/counts; row-level evidence; method comparison; cases; separate independent Python validation; report/README. | Same generic manifest/envelope/inventory/working-tree/path/column metadata gaps; validation checks need structured IDs/method/targets rather than strings. | Yes. Net-change, sign, path, and slope research remain untouched. |
| Level | Selected observations; snapshot/script/commit hashes; dataset range/counts; row-level evidence; method comparison; cases; separate independent Python validation; report/README. | Same generic gaps; large/full-history lineage cost would need an explicit storage-policy record. | Yes. Percentile, median-distance, and prior-only research remain untouched. |

The standard does not assume SOFR windows, bp metrics, chronological single-series calculations, Level/Direction/Anomaly components, expanding history, or SOFR calendar flags. Cross-sectional and multi-series packages use the same identity/provenance envelopes with their own declared ordering and findings.

## Required decisions A1–A16

**A1 — Mandatory artifacts.** `manifest.json`, `results.json`, `validation.json`, `report.md`, and `README.md`; research and validator entrypoints must also exist and be identified.

**A2 — Conditional artifacts.** Selected observations when data are selected; row-level results when decisions use row evidence; method comparison when alternatives are empirically compared; case studies when cases materially inform the decision.

**A3 — Optional artifacts.** Charts, notebooks/renderings, diagnostics, secondary exports, and other presentation aids listed and hashed when retained.

**A4 — Manifest ownership.** Research/run identity, subject, dataset/input provenance, code/config/execution identity, working-tree state, artifact inventory, omissions, and mirrored package statuses.

**A5 — Results ownership.** Measured facts, interpretations, recommendations, failure modes, indicator-specific findings, deferred questions, and authoritative research readiness decision.

**A6 — Validation ownership.** Independent methods/checks, targets, pass/fail/warning counts, limitations, validator identity, and authoritative validation status.

**A7 — Research identity.** Stable research ID plus immutable semantic research version; content-derived run ID distinguishes code/input/config combinations and stable reruns.

**A8 — Snapshot identity.** SHA-256 of the ordered canonical input-identity projection under `canonical_selected_inputs_v1`; exact processed IDs bind values/upstream lineage, with explicit external identity when no processed ID exists.

**A9 — Artifact hashes.** SHA-256 of exact raw file bytes with no normalization; formatted `sha256:<lowercase hex>`. Semantic snapshot/run hashes are separate canonical hashes.

**A10 — Serialization/date/null/unit conventions.** UTF-8 finite JSON; deterministic RFC-4180 CSV; explicit units and null meanings; ISO dates; timezone-aware UTC timestamps; unknown availability remains null/unknown.

**A11 — Cross-file consistency.** Matching standard/research/run IDs, mirrored statuses, snapshot/count/date agreement, complete inventory, valid raw hashes, resolvable references, declared CSV columns, and portable safe paths.

**A12 — Artifact-standard versioning.** `research_artifacts_v1` changes only for contract compatibility changes and remains separate from research, methodology, and signal versions.

**A13 — Independent validation.** Critical results are checked by a genuinely separate calculation or invariant path, not by re-calling the implementation under test; the method is explicit.

**A14 — Finalization.** All artifacts/schemas/hashes/invariants/conventions/validation/outcomes/links/security checks pass with no blocking structural failure.

**A15 — Schema validation now versus deferred.** Phase 2.2B supplies strict generic manifest/results/validation schemas plus validated examples. Indicator findings and CSV metrics remain declared extensions; universal metric schemas are deferred.

**A16 — Phase 2.2C validator scope.** Implement generic schema, canonical/hash, inventory, path, CSV-contract, cross-file, ordering/no-future, non-finite, and secret checks—never indicator calculations or economic decisions.

## Phase boundaries and outcome

Phase 2.2C implemented and tested the generic validator capabilities above with a non-SOFR package fixture and invalid-package cases. At its completion, Phase 2.2D remained the gate for proving the lifecycle with a materially different real signal family; the scoped dogfooding result below now records that assessment.

**PHASE 2.2C GENERIC REUSABLE PRIMITIVES IMPLEMENTED — READY FOR 2.2D**

### Phase 2.2D dogfooding result

The [Treasury assessment](PHASE_22D_FRAMEWORK_VALIDATION.md) exercises this unchanged `research_artifacts_v1` envelope with actual two-leg inputs. Generic corrections reject dangling evidence references, report-decision conflicts, hidden blocking validation failures, blank never-null CSV fields, unordered declared positions, and malformed CSV rows without crashing. Strict ISO/RFC 3339 formats are enforced and explicit non-blocking validation limitations propagate as warnings. These are contract-enforcement fixes, not a new schema or signal method. Economic sufficiency remains independently judged by the research validator and decision.

SOFR v1/v2/v3, all signal methodologies, Phase 1 semantics, Phase 3 logic, and trade logic are unchanged. This implementation adds no reusable signal calculation, universal evidence payload, or state-engine behavior.
