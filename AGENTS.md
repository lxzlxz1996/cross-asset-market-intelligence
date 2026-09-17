# Development Rules

- Read `docs/PROJECT_BLUEPRINT.md` before making a major change; it is the project source of truth.
- Work only in the explicitly authorized development phase.
- Keep data ingestion, storage, indicators, signals, models, risk, portfolio, and presentation modular.
- Preserve raw observations and their source, retrieval time, publication time, and vintage when available.
- Never introduce look-ahead bias; use only information available at the decision timestamp.
- Do not invent data, sources, financial definitions, or silently change them. Document assumptions and definition changes.
- Keep research indicators distinct from validated portfolio or trading signals.
- Prefer transparent, auditable methods and justified dependencies over unnecessary complexity.
- Add deterministic tests for important calculations and do not fetch live data in unit tests.
- Record transformation and processing versions so derived data can be reproduced.
