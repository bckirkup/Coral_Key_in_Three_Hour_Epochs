# Coral Key designed reporter measurement

The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.
The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.

- Seeds: `42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61`
- Epochs per run: `200`
- Per-agent input cap (`max_stream_dim`): `48`
- Mean static-prior precision: **14.84%**
- Mean uniform precision: **1.56%**

| Arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 3.11% | 0 | 6967 | 0.00% | 0.00% | 0.00% | 0.00% |
| all-designed seed | 26.16% | 0.00% | 474 | 0 | 100.00% | 1.18% | 0.46% | 1.49% |
| invasion | 32.79% | 2.66% | 61 | 4892 | 46.06% | 0.98% | 0.93% | 1.41% |
| oracle diagnostic upper bound | 100.00% | — | 189740 | — | — | — | — | — |

## Invasion per-seed report counts

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 19 | 7 | 36.84% |
| 43 | 4 | 0 | 0.00% |
| 44 | 1 | 1 | 100.00% |
| 45 | 1 | 0 | 0.00% |
| 46 | 0 | 0 | 0.00% |
| 47 | 0 | 0 | 0.00% |
| 48 | 6 | 3 | 50.00% |
| 49 | 1 | 0 | 0.00% |
| 50 | 3 | 0 | 0.00% |
| 51 | 0 | 0 | 0.00% |
| 52 | 6 | 3 | 50.00% |
| 53 | 2 | 0 | 0.00% |
| 54 | 0 | 0 | 0.00% |
| 55 | 1 | 1 | 100.00% |
| 56 | 1 | 0 | 0.00% |
| 57 | 8 | 3 | 37.50% |
| 58 | 0 | 0 | 0.00% |
| 59 | 2 | 2 | 100.00% |
| 60 | 5 | 0 | 0.00% |
| 61 | 1 | 0 | 0.00% |

## Interpretation

The designed reporter clears the static-prior null when it receives the published evidence needed to localize a vessel. However, stochastic input redrawing exposes it to AIS and/or SAR evidence on only 1.41% of adult designed-agent steps in the invasion arm and 1.49% in the all-designed arm; the available inputs are drawn from a pool dominated by peer residual streams. The invasion arm therefore measures input starvation at least as much as it measures whether the ordinary economy pays for competence. Its pooled designed-report count should be read alongside the per-seed counts, not as a standalone verdict.

The per-agent input cap is set to the widest stream ReefWatch declares, so every declared oceanographic feature can reach an agent. These numbers supersede the earlier artifact measured at a cap of 30, under which 18 of the 48 declared oceanographic features reached no agent; the two are not comparable run for run, because the agents' input space differs.

The all-designed-seed arm begins with every seeded genome tagged, and the corrected reporter-group telemetry resolves each report through its author's genome even when that author dies during the same step. The post-fix all-designed arm therefore has no ordinary reports; the diagnostic found 82 reports whose authors died before the step record was built, but they remain correctly credited to the designed group.

The invasion arm has 61 designed reports in total, of which the busiest single seed (seed 42) contributes 19, and 5 of 20 seeds produce no designed reports at all. Pooled invasion precision is therefore a statement about the handful of lineages that happened to be attached to vessel streams, not about the typical lineage. The per-seed table is the relevant visibility into that spread.

The oracle row is a harness-local diagnostic upper bound only.
Precision is computed from report and correct-report counts in the time series.
A zero-report group is shown as 0% by the denominator convention, not interpreted as poor precision.
