# Coral Key designed reporter measurement

The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.
The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.

The payoff levers (including the correctness-keyed response gate) are off in the numbers
below. For the evolved arm measured with those levers on, at 600 engine steps and against
the 600-step static-prior null, see
[`response_gate_measurement.md`](response_gate_measurement.md).

- Seeds: `42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61`
- Epochs per run: `200`
- Per-agent input cap (`max_stream_dim`): `48`
- Mean static-prior precision (null): **14.84%**
- Mean uniform precision (null): **1.56%**

Grounded raw-stream access arms (`SimulationConfig.grounded_input_fraction`,
`grounded_attractiveness_multiplier`, `max_input_streams`):

| Grounded arm | Reserved grounded fraction | Raw attractiveness multiplier | Input slots |
|---|---:|---:|---:|
| `f0_m1_k3` | 0.00 | 1.00 | 3 |
| `f0p34_m1_k3` | 0.34 | 1.00 | 3 |
| `f0p67_m1_k3` | 0.67 | 1.00 | 3 |
| `f0_m3_k3` | 0.00 | 3.00 | 3 |

The `fraction 0.00, multiplier 1.00` arm is the baseline: at those values the
engine's stream attachment and its random-number consumption are identical to
unreserved attachment.

## Grounded arm `f0_m1_k3` — fraction 0.00, multiplier 1.00, 3 input slots

| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 2.66% | 0 | 6510 | 0.00% | 0.00% | 0.00% | 0.00% |
| all-designed seed | 32.10% | 0.00% | 458 | 0 | 100.00% | 1.28% | 0.43% | 1.56% |
| invasion | 41.94% | 2.07% | 31 | 5310 | 40.61% | 1.45% | 0.85% | 1.61% |
| oracle diagnostic upper bound | 100.00% | — | 185292 | — | — | — | — | — |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 29.51% | 1.35% | 2.62% | +0.021 | 20 | 59.7 |
| all_designed_seed | 27.19% | 5.19% | 9.55% | +0.008 | 20 | 60.0 |
| invasion | 28.69% | 1.24% | 2.43% | +0.019 | 20 | 59.7 |
| oracle_upper_bound | 43.31% | 0.39% | 0.78% | -0.040 | 20 | 60.0 |

Invasion per-seed report counts:

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 5 | 1 | 20.00% |
| 43 | 0 | 0 | 0.00% |
| 44 | 0 | 0 | 0.00% |
| 45 | 0 | 0 | 0.00% |
| 46 | 0 | 0 | 0.00% |
| 47 | 3 | 0 | 0.00% |
| 48 | 3 | 3 | 100.00% |
| 49 | 2 | 0 | 0.00% |
| 50 | 2 | 1 | 50.00% |
| 51 | 0 | 0 | 0.00% |
| 52 | 2 | 1 | 50.00% |
| 53 | 0 | 0 | 0.00% |
| 54 | 3 | 1 | 33.33% |
| 55 | 1 | 0 | 0.00% |
| 56 | 0 | 0 | 0.00% |
| 57 | 5 | 3 | 60.00% |
| 58 | 1 | 0 | 0.00% |
| 59 | 3 | 3 | 100.00% |
| 60 | 0 | 0 | 0.00% |
| 61 | 1 | 0 | 0.00% |

## Grounded arm `f0p34_m1_k3` — fraction 0.34, multiplier 1.00, 3 input slots

| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 11.82% | 0 | 8365 | 0.00% | 0.00% | 0.00% | 0.00% |
| all-designed seed | 47.48% | 0.00% | 16302 | 0 | 100.00% | 28.69% | 4.78% | 32.95% |
| invasion | 46.27% | 11.69% | 3093 | 7784 | 11.70% | 28.79% | 6.28% | 33.51% |
| oracle diagnostic upper bound | 100.00% | — | 186799 | — | — | — | — | — |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 28.34% | 89.79% | 91.78% | +0.110 | 20 | 59.8 |
| all_designed_seed | 32.32% | 91.85% | 93.42% | +0.125 | 20 | 59.6 |
| invasion | 30.85% | 91.47% | 93.31% | +0.111 | 20 | 59.7 |
| oracle_upper_bound | 60.38% | 89.38% | 91.47% | +0.083 | 20 | 60.0 |

Invasion per-seed report counts:

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 18 | 12 | 66.67% |
| 43 | 311 | 147 | 47.27% |
| 44 | 125 | 68 | 54.40% |
| 45 | 87 | 25 | 28.74% |
| 46 | 37 | 21 | 56.76% |
| 47 | 20 | 8 | 40.00% |
| 48 | 387 | 165 | 42.64% |
| 49 | 7 | 1 | 14.29% |
| 50 | 911 | 452 | 49.62% |
| 51 | 4 | 0 | 0.00% |
| 52 | 5 | 2 | 40.00% |
| 53 | 1 | 0 | 0.00% |
| 54 | 159 | 76 | 47.80% |
| 55 | 94 | 65 | 69.15% |
| 56 | 4 | 0 | 0.00% |
| 57 | 18 | 11 | 61.11% |
| 58 | 562 | 236 | 41.99% |
| 59 | 10 | 4 | 40.00% |
| 60 | 148 | 51 | 34.46% |
| 61 | 185 | 87 | 47.03% |

## Grounded arm `f0p67_m1_k3` — fraction 0.67, multiplier 1.00, 3 input slots

| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 15.26% | 0 | 8281 | 0.00% | 0.00% | 0.00% | 0.00% |
| all-designed seed | 57.61% | 0.00% | 33086 | 0 | 100.00% | 68.42% | 8.78% | 74.97% |
| invasion | 57.93% | 15.84% | 3114 | 7555 | 2.45% | 70.91% | 12.28% | 78.72% |
| oracle diagnostic upper bound | 100.00% | — | 186626 | — | — | — | — | — |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 29.73% | 100.00% | 100.00% | +0.131 | 20 | 59.8 |
| all_designed_seed | 43.85% | 100.00% | 100.00% | +0.111 | 20 | 58.2 |
| invasion | 29.73% | 100.00% | 100.00% | +0.134 | 20 | 59.5 |
| oracle_upper_bound | 57.84% | 100.00% | 100.00% | +0.116 | 20 | 60.0 |

Invasion per-seed report counts:

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 260 | 128 | 49.23% |
| 43 | 33 | 22 | 66.67% |
| 44 | 326 | 246 | 75.46% |
| 45 | 102 | 51 | 50.00% |
| 46 | 251 | 174 | 69.32% |
| 47 | 70 | 37 | 52.86% |
| 48 | 414 | 233 | 56.28% |
| 49 | 6 | 0 | 0.00% |
| 50 | 377 | 227 | 60.21% |
| 51 | 109 | 56 | 51.38% |
| 52 | 27 | 17 | 62.96% |
| 53 | 8 | 4 | 50.00% |
| 54 | 14 | 5 | 35.71% |
| 55 | 62 | 49 | 79.03% |
| 56 | 17 | 7 | 41.18% |
| 57 | 48 | 35 | 72.92% |
| 58 | 245 | 140 | 57.14% |
| 59 | 20 | 11 | 55.00% |
| 60 | 688 | 338 | 49.13% |
| 61 | 37 | 24 | 64.86% |

## Grounded arm `f0_m3_k3` — fraction 0.00, multiplier 3.00, 3 input slots

| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 2.01% | 0 | 6057 | 0.00% | 0.00% | 0.00% | 0.00% |
| all-designed seed | 28.37% | 0.00% | 624 | 0 | 100.00% | 1.69% | 0.54% | 2.07% |
| invasion | 27.72% | 2.31% | 101 | 4674 | 50.48% | 1.80% | 0.62% | 2.08% |
| oracle diagnostic upper bound | 100.00% | — | 187033 | — | — | — | — | — |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 27.69% | 2.48% | 4.70% | +0.050 | 20 | 59.8 |
| all_designed_seed | 23.64% | 7.27% | 12.87% | +0.013 | 20 | 59.9 |
| invasion | 26.28% | 4.19% | 7.70% | +0.022 | 20 | 59.7 |
| oracle_upper_bound | 48.35% | 0.61% | 1.20% | -0.046 | 20 | 60.0 |

Invasion per-seed report counts:

| Seed | Designed reports | Designed correct reports | Designed precision |
|---:|---:|---:|---:|
| 42 | 4 | 1 | 25.00% |
| 43 | 0 | 0 | 0.00% |
| 44 | 0 | 0 | 0.00% |
| 45 | 17 | 1 | 5.88% |
| 46 | 5 | 0 | 0.00% |
| 47 | 19 | 3 | 15.79% |
| 48 | 4 | 4 | 100.00% |
| 49 | 1 | 0 | 0.00% |
| 50 | 0 | 0 | 0.00% |
| 51 | 6 | 2 | 33.33% |
| 52 | 3 | 1 | 33.33% |
| 53 | 0 | 0 | 0.00% |
| 54 | 1 | 0 | 0.00% |
| 55 | 1 | 0 | 0.00% |
| 56 | 9 | 1 | 11.11% |
| 57 | 19 | 10 | 52.63% |
| 58 | 1 | 1 | 100.00% |
| 59 | 3 | 3 | 100.00% |
| 60 | 4 | 0 | 0.00% |
| 61 | 4 | 1 | 25.00% |

## Grounded access comparison

Nulls for every row: static prior 14.84%, uniform 1.56%.

| Grounded fraction | Invasion AIS∨SAR evidence | All-designed AIS∨SAR evidence | Invasion designed precision | Invasion ordinary precision | All-designed designed precision | Invasion solvency | Invasion grounded yield share |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 (×1.00) | 1.61% | 1.56% | 41.94% | 2.07% | 32.10% | 28.69% | 1.24% |
| 0.34 (×1.00) | 33.51% | 32.95% | 46.27% | 11.69% | 47.48% | 30.85% | 91.47% |
| 0.67 (×1.00) | 78.72% | 74.97% | 57.93% | 15.84% | 57.61% | 29.73% | 100.00% |
| 0.00 (×3.00) | 2.08% | 2.07% | 27.72% | 2.31% | 28.37% | 26.28% | 4.19% |

## Interpretation

Every precision below is read against the same two nulls: a 14.84% static-prior precision and a 1.56% uniform precision.

At the baseline grounded fraction the designed reporter sees AIS and/or SAR evidence on 1.61% of adult designed-agent steps in the invasion arm and 1.56% in the all-designed arm, because the available inputs are drawn from a pool dominated by peer residual streams.

- Grounded fraction 0.34 (multiplier 1.00): invasion AIS∨SAR evidence 33.51% versus the 1.61% baseline (20.82× baseline); invasion designed precision 46.27%, invasion ordinary precision 11.69%.
- Grounded fraction 0.67 (multiplier 1.00): invasion AIS∨SAR evidence 78.72% versus the 1.61% baseline (48.91× baseline); invasion designed precision 57.93%, invasion ordinary precision 15.84%.
- Grounded fraction 0.00 (multiplier 3.00): invasion AIS∨SAR evidence 2.08% versus the 1.61% baseline (1.29× baseline); invasion designed precision 27.72%, invasion ordinary precision 2.31%.

The per-agent input cap is set to the widest stream ReefWatch declares, so every declared oceanographic feature can reach an agent.

The all-designed-seed arm begins with every seeded genome tagged, and the reporter-group telemetry resolves each report through its author's genome even when that author dies during the same step. The diagnostic found 79 such reports in the baseline arm; they remain credited to the designed group.

The baseline invasion arm has 31 designed reports in total, of which the busiest single seed (seed 42) contributes 5, and 8 of 20 seeds produce no designed reports at all. Pooled invasion precision is therefore a statement about the handful of lineages that happened to be attached to vessel streams, not about the typical lineage. The per-seed tables are the relevant visibility into that spread, and the same caveat applies to every grounded arm.

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
