# Coral Key designed reporter measurement

The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.
The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.

- Seeds: `42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61`
- Epochs per run: `200`
- Mean static-prior precision: **14.84%**
- Mean uniform precision: **1.56%**

| Arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 2.91% | 0 | 6524 | 0.00% | 0.00% | 0.00% | 0.00% |
| all-designed seed | 31.49% | 4.29% | 416 | 70 | 100.00% | 1.07% | 0.51% | 1.43% |
| invasion | 44.70% | 4.11% | 132 | 4326 | 48.01% | 0.85% | 0.72% | 1.38% |
| oracle diagnostic upper bound | 100.00% | — | 186746 | — | — | — | — | — |

## Invasion per-seed report counts

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 6 | 0 | 0.00% |
| 43 | 2 | 0 | 0.00% |
| 44 | 0 | 0 | 0.00% |
| 45 | 4 | 1 | 25.00% |
| 46 | 0 | 0 | 0.00% |
| 47 | 1 | 1 | 100.00% |
| 48 | 6 | 4 | 66.67% |
| 49 | 1 | 0 | 0.00% |
| 50 | 86 | 43 | 50.00% |
| 51 | 0 | 0 | 0.00% |
| 52 | 4 | 3 | 75.00% |
| 53 | 2 | 0 | 0.00% |
| 54 | 5 | 2 | 40.00% |
| 55 | 7 | 0 | 0.00% |
| 56 | 0 | 0 | 0.00% |
| 57 | 5 | 4 | 80.00% |
| 58 | 0 | 0 | 0.00% |
| 59 | 1 | 1 | 100.00% |
| 60 | 2 | 0 | 0.00% |
| 61 | 0 | 0 | 0.00% |

## Interpretation

The designed reporter clears the static-prior null when it receives the published evidence needed to localize a vessel. However, stochastic input redrawing exposes it to AIS and/or SAR evidence on only about 2% of adult designed-agent steps; the available inputs are drawn from a pool dominated by peer residual streams. The invasion arm therefore measures input starvation at least as much as it measures whether the ordinary economy pays for competence. Its pooled designed-report count should be read alongside the per-seed counts, not as a standalone verdict.

The all-designed-seed arm begins with every seeded genome tagged, but the engine's reporter-group telemetry classifies reports from designed agents that die during the same step as ordinary because grouping uses the post-step living population. This is a telemetry classification artifact, not tag-loss: all 70 reports classified this way in the 20-seed artifact were emitted by designed agents that died before the step record was built.

The oracle row is a harness-local diagnostic upper bound only.
Precision is computed from report and correct-report counts in the time series.
A zero-report group is shown as 0% by the denominator convention, not interpreted as poor precision.
