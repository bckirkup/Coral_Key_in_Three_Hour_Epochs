# Coral Key designed reporter measurement

The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.
The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.

- Seeds: `42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61`
- Epochs per run: `600`
- Per-agent input cap (`max_stream_dim`): `48`
- Mean static-prior precision (null): **12.80%**
- Mean uniform precision (null): **1.56%**

Grounded raw-stream access arms (`SimulationConfig.grounded_input_fraction`,
`grounded_attractiveness_multiplier`, `max_input_streams`):

| Grounded arm | Reserved grounded fraction | Raw attractiveness multiplier | Input slots |
|---|---:|---:|---:|
| `f0p67_m1_k3` | 0.67 | 1.00 | 3 |

The `fraction 0.00, multiplier 1.00` arm is the baseline: at those values the
engine's stream attachment and its random-number consumption are identical to
unreserved attachment.

Payoff levers (`levers_w1`), the only engine settings that differ from
the default-off measurement:

- `correct_report_attention_value`: `8.0`
- `reproduction_merit_ordering`: `True`
- `escalation_calibration_in_score_units`: `True`
- `false_alarm_break_even_precision`: `0.2`
- `reproduction_correctness_weight`: `1.0`
- `gene_pool_escalation_threshold_range`: `[0.05, 0.3]`

## Grounded arm `f0p67_m1_k3` — fraction 0.67, multiplier 1.00, 3 input slots

| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all-designed seed | 58.69% | 0.00% | 321645 | 0 | 100.00% | 80.98% | 7.56% | 85.87% |
| invasion | 56.92% | 18.71% | 156041 | 273005 | 54.33% | 73.98% | 9.90% | 81.03% |
| oracle diagnostic upper bound | 100.00% | — | 647781 | — | — | — | — | — |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| all_designed_seed | 41.33% | 100.00% | 100.00% | +0.018 | 20 | 60.0 |
| invasion | 29.78% | 100.00% | 100.00% | +0.004 | 20 | 60.0 |
| oracle_upper_bound | 73.27% | 100.00% | 100.00% | -0.097 | 20 | 60.0 |

Invasion per-seed report counts:

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 6618 | 3319 | 50.15% |
| 43 | 8870 | 5022 | 56.62% |
| 44 | 18269 | 10801 | 59.12% |
| 45 | 7369 | 4770 | 64.73% |
| 46 | 10329 | 6724 | 65.10% |
| 47 | 11911 | 6308 | 52.96% |
| 48 | 7067 | 3589 | 50.79% |
| 49 | 15 | 6 | 40.00% |
| 50 | 12785 | 8294 | 64.87% |
| 51 | 10160 | 4731 | 46.56% |
| 52 | 60 | 37 | 61.67% |
| 53 | 15086 | 8348 | 55.34% |
| 54 | 5204 | 2803 | 53.86% |
| 55 | 15460 | 8369 | 54.13% |
| 56 | 5547 | 3156 | 56.90% |
| 57 | 229 | 114 | 49.78% |
| 58 | 12468 | 7286 | 58.44% |
| 59 | 81 | 26 | 32.10% |
| 60 | 8308 | 5003 | 60.22% |
| 61 | 205 | 113 | 55.12% |

Falsification clauses and reporting economics (payoff levers on):

| Quantity | `all_designed_seed` | `invasion` | `oracle_upper_bound` |
|---|---|---|---|
| Adult correct-report rate | 58.57% | 34.23% | 100.00% |
| Clause 1 slope per generation | +0.0167 | +0.0362 | +0.0000 |
| Generations observed | 7.9 | 10.8 | 4.0 |
| Clause 2 parent–child offspring r | +0.018 | +0.004 | -0.097 |
| Parent–child precision r | +0.097 | +0.349 | +0.000 |
| Reports per adult lifetime | 79.05 | 85.83 | 306.44 |
| Share of adults that never report | 10.55% | 7.93% | 2.05% |
| Eligible-to-reproduce share | 96.43% | 95.42% | 98.29% |
| Steps where the population cap binds | 94.92% | 92.83% | 98.47% |
| Mean offspring, ever-correct adults | 1.222 | 1.257 | 1.073 |
| Mean offspring, never-correct adults | 1.034 | 1.161 | 0.000 |
| Mean offspring, silent adults | 1.123 | 1.131 | 0.685 |
| Seeds with a rising correct-report rate | 13/20 | 18/20 | 6/20 |
| Seeds with clause 2 r above 0.2 | 0/20 | 0/20 | 0/20 |

Per-seed clause metrics, `all_designed_seed` arm:

| Seed | Correct-report rate | Clause 1 slope/generation | Generations | Clause 2 r | Reports/adult | Silent adults | Cap binds |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 65.15% | +0.0063 | 9 | +0.075 | 39.23 | 8.40% | 92.67% |
| 43 | 67.29% | -0.0133 | 8 | -0.104 | 90.76 | 12.75% | 96.00% |
| 44 | 59.83% | +0.0184 | 10 | -0.080 | 71.48 | 11.27% | 93.83% |
| 45 | 62.22% | +0.0055 | 9 | +0.140 | 78.71 | 8.20% | 95.17% |
| 46 | 64.51% | +0.0324 | 6 | +0.010 | 105.11 | 5.59% | 96.50% |
| 47 | 49.92% | +0.0158 | 10 | -0.119 | 43.62 | 9.49% | 92.83% |
| 48 | 51.65% | -0.0320 | 7 | +0.164 | 90.74 | 7.45% | 96.33% |
| 49 | 55.24% | +0.0168 | 11 | +0.008 | 69.17 | 8.86% | 93.33% |
| 50 | 63.86% | +0.0882 | 6 | +0.080 | 99.90 | 16.95% | 95.17% |
| 51 | 53.05% | +0.0260 | 10 | -0.011 | 85.73 | 17.54% | 94.00% |
| 52 | 60.90% | -0.0229 | 6 | +0.173 | 75.09 | 7.04% | 96.67% |
| 53 | 60.54% | +0.0207 | 8 | +0.065 | 83.68 | 7.86% | 95.17% |
| 54 | 61.20% | +0.0896 | 7 | -0.126 | 77.04 | 19.07% | 94.33% |
| 55 | 54.17% | -0.0182 | 8 | +0.083 | 94.50 | 3.85% | 95.33% |
| 56 | 60.24% | +0.0329 | 7 | -0.028 | 81.92 | 7.47% | 95.50% |
| 57 | 45.94% | -0.0301 | 7 | -0.089 | 79.64 | 8.56% | 96.00% |
| 58 | 64.01% | -0.0040 | 5 | +0.127 | 130.67 | 8.46% | 97.50% |
| 59 | 59.21% | -0.0080 | 8 | +0.008 | 46.52 | 14.93% | 91.67% |
| 60 | 55.30% | +0.0977 | 6 | -0.053 | 82.65 | 14.86% | 95.50% |
| 61 | 57.08% | +0.0130 | 10 | +0.047 | 54.93 | 12.46% | 94.83% |

Per-seed clause metrics, `invasion` arm:

| Seed | Correct-report rate | Clause 1 slope/generation | Generations | Clause 2 r | Reports/adult | Silent adults | Cap binds |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 31.50% | +0.0177 | 14 | +0.056 | 38.79 | 7.52% | 87.17% |
| 43 | 36.20% | +0.0503 | 10 | -0.041 | 80.91 | 9.44% | 94.17% |
| 44 | 53.80% | +0.0428 | 11 | -0.039 | 66.46 | 5.40% | 92.33% |
| 45 | 36.94% | +0.0400 | 9 | +0.033 | 134.61 | 10.92% | 95.17% |
| 46 | 42.30% | +0.0841 | 8 | +0.056 | 102.29 | 5.24% | 95.17% |
| 47 | 43.59% | +0.0452 | 12 | -0.094 | 50.41 | 8.87% | 90.83% |
| 48 | 29.99% | +0.0261 | 11 | +0.079 | 92.27 | 8.12% | 92.83% |
| 49 | 19.02% | +0.0093 | 12 | +0.172 | 131.79 | 8.55% | 92.50% |
| 50 | 44.19% | +0.0737 | 8 | -0.021 | 98.58 | 10.75% | 93.50% |
| 51 | 34.33% | +0.0466 | 10 | -0.025 | 64.96 | 8.74% | 94.17% |
| 52 | 17.57% | -0.0012 | 13 | -0.001 | 97.01 | 8.09% | 93.17% |
| 53 | 48.79% | +0.0590 | 11 | +0.008 | 60.27 | 5.14% | 93.00% |
| 54 | 27.71% | +0.0522 | 11 | -0.051 | 105.17 | 8.37% | 94.17% |
| 55 | 48.47% | +0.0087 | 9 | +0.076 | 104.93 | 11.86% | 96.00% |
| 56 | 24.27% | +0.0608 | 11 | -0.176 | 114.65 | 6.38% | 94.33% |
| 57 | 16.98% | +0.0002 | 13 | -0.023 | 86.22 | 4.37% | 91.33% |
| 58 | 49.71% | +0.0587 | 8 | -0.067 | 75.05 | 9.13% | 94.67% |
| 59 | 17.34% | -0.0047 | 13 | +0.126 | 51.36 | 8.57% | 88.33% |
| 60 | 38.50% | +0.0424 | 7 | +0.071 | 85.66 | 4.07% | 95.00% |
| 61 | 23.40% | +0.0120 | 14 | -0.061 | 75.20 | 9.14% | 88.67% |

Per-seed clause metrics, `oracle_upper_bound` arm:

| Seed | Correct-report rate | Clause 1 slope/generation | Generations | Clause 2 r | Reports/adult | Silent adults | Cap binds |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 100.00% | +0.0000 | 3 | -0.181 | 315.84 | 0.00% | 99.00% |
| 43 | 100.00% | +0.0000 | 3 | -0.129 | 360.09 | 0.00% | 99.00% |
| 44 | 100.00% | -0.0000 | 4 | -0.076 | 319.40 | 3.92% | 98.00% |
| 45 | 100.00% | -0.0000 | 4 | -0.068 | 259.29 | 1.57% | 97.50% |
| 46 | 100.00% | -0.0000 | 4 | -0.085 | 332.49 | 0.00% | 98.50% |
| 47 | 100.00% | -0.0000 | 5 | -0.244 | 290.75 | 7.21% | 98.33% |
| 48 | 100.00% | -0.0000 | 5 | +0.052 | 246.40 | 0.00% | 98.67% |
| 49 | 100.00% | +0.0000 | 3 | -0.026 | 338.78 | 0.00% | 98.67% |
| 50 | 100.00% | +0.0000 | 3 | -0.034 | 312.61 | 1.00% | 98.50% |
| 51 | 100.00% | -0.0000 | 4 | -0.142 | 290.96 | 0.00% | 98.50% |
| 52 | 100.00% | -0.0000 | 5 | -0.137 | 264.07 | 0.00% | 98.17% |
| 53 | 100.00% | -0.0000 | 4 | -0.122 | 294.03 | 7.34% | 98.33% |
| 54 | 100.00% | -0.0000 | 4 | -0.051 | 313.81 | 2.83% | 98.50% |
| 55 | 100.00% | -0.0000 | 4 | -0.150 | 366.04 | 0.00% | 99.17% |
| 56 | 100.00% | -0.0000 | 4 | -0.029 | 373.84 | 2.25% | 98.50% |
| 57 | 100.00% | +0.0000 | 3 | -0.134 | 292.72 | 0.00% | 98.67% |
| 58 | 100.00% | -0.0000 | 4 | -0.092 | 286.22 | 0.00% | 98.17% |
| 59 | 100.00% | -0.0000 | 4 | +0.025 | 281.94 | 0.00% | 99.00% |
| 60 | 100.00% | +0.0000 | 3 | -0.148 | 353.67 | 0.00% | 99.00% |
| 61 | 100.00% | -0.0000 | 6 | -0.175 | 235.76 | 14.81% | 97.33% |

## Grounded access comparison

Nulls for every row: static prior 12.80%, uniform 1.56%.

| Grounded fraction | Invasion AIS∨SAR evidence | All-designed AIS∨SAR evidence | Invasion designed precision | Invasion ordinary precision | All-designed designed precision | Invasion solvency | Invasion grounded yield share |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.67 (×1.00) | 81.03% | 85.87% | 56.92% | 18.71% | 58.69% | 29.78% | 100.00% |

## Interpretation

Every precision below is read against the same two nulls: a 12.80% static-prior precision and a 1.56% uniform precision.

At the baseline grounded fraction the designed reporter sees AIS and/or SAR evidence on 81.03% of adult designed-agent steps in the invasion arm and 85.87% in the all-designed arm, because the available inputs are drawn from a pool dominated by peer residual streams.


The per-agent input cap is set to the widest stream ReefWatch declares, so every declared oceanographic feature can reach an agent.

The all-designed-seed arm begins with every seeded genome tagged, and the reporter-group telemetry resolves each report through its author's genome even when that author dies during the same step. The diagnostic found 1227 such reports in the baseline arm; they remain credited to the designed group.

The baseline invasion arm has 156041 designed reports in total, of which the busiest single seed (seed 44) contributes 18269, and 0 of 20 seeds produce no designed reports at all. Pooled invasion precision is therefore a statement about the handful of lineages that happened to be attached to vessel streams, not about the typical lineage. The per-seed tables are the relevant visibility into that spread, and the same caveat applies to every grounded arm.

The parent–child reproductive correlation is the Pearson correlation between a parent's offspring count and its child's offspring count over all parent-child pairs in a run, averaged over the runs where both series vary.

The oracle row is a harness-local diagnostic upper bound only.
Precision is computed from report and correct-report counts in the time series.
A zero-report group is shown as 0% by the denominator convention, not interpreted as poor precision.

## Superseded provenance

The pre-grounding-fix measurement recorded here previously reported, at the same
20 seeds, 200 epochs and `max_stream_dim=48`, against a 14.84% static-prior null
and a 1.56% uniform null:

| Superseded arm | Designed precision | Ordinary precision | Designed reports | AIS/SAR evidence |
|---|---:|---:|---:|---:|
| ordinary | 0.00% | 3.11% | 0 | 0.00% |
| all-designed seed | 26.16% | 0.00% | 474 | 1.49% |
| invasion | 32.79% | 2.66% | 61 | 1.41% |

Those numbers were measured against the `tattletots` revision pinned in this
repository's lockfile at the time. The arms in this document were measured
against the grounded-access branch build of `tattletots`, which also carries
engine changes unrelated to the grounded knobs, so the 0.0 arm here is the
correct baseline for the comparison and is not run-for-run comparable to the
superseded table. The superseded numbers are kept as provenance only.

The earlier artifact measured at `max_stream_dim=30`, under which 18 of the 48
declared oceanographic features reached no agent, remains superseded for the
same reason: the agents' input space differs.
