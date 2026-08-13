# Coral Key designed reporter measurement

The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.
The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.

- Seeds: `42, 43, 44, 45, 46`
- Epochs per run: `200`
- Mean static-prior precision: **14.84%**
- Mean uniform precision: **1.56%**

| Arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 0.33% | 0 | 1795 | 0.00% | 0.00% | 0.00% | 0.00% |
| all_designed | 25.26% | 8.00% | 95 | 25 | 100.00% | 1.46% | 0.41% | 1.74% |
| invasion | 0.00% | 1.94% | 11 | 1085 | 57.00% | 0.59% | 0.51% | 0.86% |
| oracle diagnostic upper bound | 100.00% | — | 46363 | — | — | — | — | — |

Precision is computed from report and correct-report counts in the time series.
A zero-report group is shown as 0% by the denominator convention, not interpreted as poor precision.
