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
| ordinary | 0.00% | 19.67% | 0 | 489646 | 0.00% | 0.00% | 0.00% | 0.00% |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 23.96% | 100.00% | 100.00% | +0.006 | 20 | 60.0 |

Falsification clauses and reporting economics (payoff levers on):

| Quantity | `ordinary` |
|---|---|
| Adult correct-report rate | 19.63% |
| Clause 1 slope per generation | +0.0045 |
| Generations observed | 12.8 |
| Clause 2 parent–child offspring r | +0.006 |
| Parent–child precision r | +0.089 |
| Reports per adult lifetime | 86.19 |
| Share of adults that never report | 7.43% |
| Eligible-to-reproduce share | 94.44% |
| Steps where the population cap binds | 91.43% |
| Mean offspring, ever-correct adults | 1.308 |
| Mean offspring, never-correct adults | 1.097 |
| Mean offspring, silent adults | 1.142 |
| Seeds with a rising correct-report rate | 15/20 |
| Seeds with clause 2 r above 0.2 | 0/20 |

Per-seed clause metrics, `ordinary` arm:

| Seed | Correct-report rate | Clause 1 slope/generation | Generations | Clause 2 r | Reports/adult | Silent adults | Cap binds |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 19.15% | +0.0073 | 13 | -0.006 | 87.23 | 5.77% | 91.00% |
| 43 | 24.20% | +0.0235 | 10 | +0.039 | 84.26 | 8.21% | 93.33% |
| 44 | 17.93% | +0.0041 | 14 | -0.050 | 51.61 | 5.15% | 88.50% |
| 45 | 24.42% | +0.0035 | 12 | +0.057 | 108.95 | 7.78% | 93.50% |
| 46 | 14.20% | -0.0074 | 8 | -0.128 | 149.41 | 5.13% | 95.17% |
| 47 | 21.05% | +0.0032 | 16 | +0.089 | 49.20 | 9.28% | 85.17% |
| 48 | 20.12% | +0.0013 | 8 | +0.184 | 120.06 | 7.08% | 94.67% |
| 49 | 20.38% | +0.0038 | 13 | -0.089 | 85.42 | 12.55% | 93.67% |
| 50 | 18.24% | +0.0159 | 13 | +0.051 | 75.49 | 6.72% | 92.83% |
| 51 | 19.76% | +0.0149 | 11 | +0.031 | 31.51 | 4.71% | 90.50% |
| 52 | 16.26% | -0.0020 | 10 | -0.042 | 111.22 | 6.52% | 94.67% |
| 53 | 20.26% | +0.0089 | 13 | +0.104 | 86.94 | 8.46% | 91.67% |
| 54 | 22.38% | -0.0032 | 13 | -0.127 | 105.78 | 9.51% | 94.33% |
| 55 | 17.33% | -0.0056 | 12 | +0.019 | 75.83 | 7.07% | 91.17% |
| 56 | 16.59% | +0.0095 | 11 | -0.036 | 95.48 | 10.29% | 93.50% |
| 57 | 18.35% | +0.0050 | 11 | +0.037 | 123.20 | 4.58% | 92.83% |
| 58 | 18.71% | +0.0007 | 14 | -0.013 | 83.03 | 7.79% | 91.50% |
| 59 | 17.17% | +0.0043 | 17 | -0.034 | 44.42 | 8.95% | 88.33% |
| 60 | 23.62% | -0.0062 | 10 | +0.116 | 122.54 | 7.58% | 96.33% |
| 61 | 22.40% | +0.0081 | 26 | -0.079 | 32.14 | 5.41% | 76.00% |
