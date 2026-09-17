# Signal Definitions

No signal engine is implemented in Phase 0. This contract reserves a consistent future output shape.

| Field | Meaning |
|---|---|
| `signal_id` | Stable identifier for the rule or research output. |
| `indicator_id` | Input indicator defined in the data dictionary. |
| `date` | As-of date; future work must also retain availability time where relevant. |
| `signal_type` | Descriptive, confirmation, leading, predictive, or portfolio-allocation. |
| `value` | Numeric rule output. |
| `state` | Explainable categorical result, if applicable. |
| `model_version` | Version of rule, parameters, and input methodology. |

Future standard outputs may include current level, 1D/5D/20D changes, Z-score, rolling percentile, trend, momentum, volatility, freshness, confidence, and a trace to raw inputs. Thresholds and interpretations must be documented and empirically evaluated before any portfolio use.
