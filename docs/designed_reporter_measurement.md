# Coral Key designed reporter measurement

The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.
The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.

- Seeds: `42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61`
- Epochs per run: `200`
- Mean static-prior precision: **14.84%**
- Mean uniform precision: **1.56%**
- Decoder precision on the 200-step declared-geometry validator: **25.82%**
- The incumbent decoder scored **0.00%** on this validator; the new decoder is above the **14.84%** static-prior null.

| Arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 2.04% | 0 | 6781 | 0.00% | 0.00% | 0.00% | 0.00% |
| all-designed seed | 27.57% | 0.00% | 486 | 0 | 100.00% | 1.07% | 0.51% | 1.43% |
| invasion | 28.57% | 2.47% | 56 | 4494 | 50.92% | 0.67% | 0.65% | 1.19% |
| oracle diagnostic upper bound | 100.00% | — | 186746 | — | — | — | — | — |

## Invasion per-seed report counts

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 3 | 0 | 0.00% |
| 43 | 2 | 0 | 0.00% |
| 44 | 0 | 0 | 0.00% |
| 45 | 5 | 1 | 20.00% |
| 46 | 0 | 0 | 0.00% |
| 47 | 0 | 0 | 0.00% |
| 48 | 3 | 3 | 100.00% |
| 49 | 2 | 0 | 0.00% |
| 50 | 7 | 1 | 14.29% |
| 51 | 0 | 0 | 0.00% |
| 52 | 6 | 3 | 50.00% |
| 53 | 2 | 0 | 0.00% |
| 54 | 6 | 0 | 0.00% |
| 55 | 8 | 1 | 12.50% |
| 56 | 3 | 3 | 100.00% |
| 57 | 3 | 3 | 100.00% |
| 58 | 0 | 0 | 0.00% |
| 59 | 1 | 1 | 100.00% |
| 60 | 5 | 0 | 0.00% |
| 61 | 0 | 0 | 0.00% |

## Interpretation

The designed reporter clears the static-prior null when it receives the published evidence needed to localize a vessel. However, stochastic input redrawing exposes it to AIS and/or SAR evidence on only about 2% of adult designed-agent steps; the available inputs are drawn from a pool dominated by peer residual streams. The invasion arm therefore measures input starvation at least as much as it measures whether the ordinary economy pays for competence. Its pooled designed-report count should be read alongside the per-seed counts, not as a standalone verdict.

The all-designed-seed arm begins with every seeded genome tagged, and the corrected reporter-group telemetry resolves each report through its author's genome even when that author dies during the same step. The post-fix all-designed arm therefore has no ordinary reports; the diagnostic found 70 reports whose authors died before the step record was built, but they remain correctly credited to the designed group.

The corrected invasion arm has 56 designed reports. Seven reports were attributed to designed authors that died during the same step and remain correctly credited to the designed group. The pooled invasion precision is therefore based on sparse evidence; the per-seed table is the relevant visibility into that spread.

The oracle row is a harness-local diagnostic upper bound only.
Precision is computed from report and correct-report counts in the time series.
A zero-report group is shown as 0% by the denominator convention, not interpreted as poor precision.
