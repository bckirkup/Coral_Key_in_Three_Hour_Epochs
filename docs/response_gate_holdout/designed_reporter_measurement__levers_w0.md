# Coral Key designed reporter measurement

The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.
The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.

- Seeds: `101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120`
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

Payoff levers (`levers_w0`), the only engine settings that differ from
the default-off measurement:

- `correct_report_attention_value`: `8.0`
- `reproduction_merit_ordering`: `True`
- `escalation_calibration_in_score_units`: `True`
- `false_alarm_break_even_precision`: `0.2`
- `reproduction_correctness_weight`: `0.0`
- `gene_pool_escalation_threshold_range`: `[0.05, 0.3]`

## Grounded arm `f0p67_m1_k3` — fraction 0.67, multiplier 1.00, 3 input slots

| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 0.00% | 17.61% | 0 | 517651 | 0.00% | 0.00% | 0.00% | 0.00% |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 23.00% | 100.00% | 100.00% | -0.060 | 20 | 60.0 |

Falsification clauses and reporting economics (payoff levers on):

| Quantity | `ordinary` |
|---|---|
| Adult correct-report rate | 17.59% |
| Clause 1 slope per generation | +0.0037 |
| Generations observed | 22.9 |
| Clause 2 parent–child offspring r | -0.060 |
| Parent–child precision r | +0.228 |
| Reports per adult lifetime | 89.71 |
| Share of adults that never report | 6.75% |
| Eligible-to-reproduce share | 93.37% |
| Steps where the population cap binds | 92.20% |
| Mean offspring, ever-correct adults | 1.340 |
| Mean offspring, never-correct adults | 1.084 |
| Mean offspring, silent adults | 1.180 |
| Seeds with a rising correct-report rate | 18/20 |
| Seeds with clause 2 r above 0.2 | 0/20 |

Per-seed clause metrics, `ordinary` arm:

| Seed | Correct-report rate | Clause 1 slope/generation | Generations | Clause 2 r | Reports/adult | Silent adults | Cap binds |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 101 | 14.52% | +0.0009 | 25 | -0.117 | 56.93 | 5.99% | 89.50% |
| 102 | 20.71% | +0.0011 | 11 | -0.014 | 139.82 | 3.81% | 95.83% |
| 103 | 14.70% | -0.0000 | 21 | -0.117 | 57.61 | 8.12% | 94.33% |
| 104 | 12.41% | +0.0033 | 42 | -0.070 | 42.91 | 3.71% | 90.00% |
| 105 | 8.26% | +0.0024 | 17 | -0.011 | 105.95 | 7.54% | 95.33% |
| 106 | 19.15% | +0.0009 | 35 | -0.075 | 50.64 | 4.86% | 89.17% |
| 107 | 15.95% | +0.0024 | 15 | -0.163 | 105.46 | 5.43% | 95.50% |
| 108 | 20.26% | +0.0050 | 20 | -0.029 | 50.89 | 6.93% | 93.50% |
| 109 | 18.43% | +0.0026 | 31 | -0.026 | 78.39 | 2.99% | 93.00% |
| 110 | 20.07% | +0.0056 | 11 | +0.113 | 119.50 | 10.38% | 94.83% |
| 111 | 20.41% | +0.0096 | 15 | -0.040 | 64.74 | 10.07% | 94.50% |
| 112 | 14.13% | +0.0016 | 70 | -0.044 | 11.49 | 5.82% | 57.00% |
| 113 | 24.78% | +0.0128 | 13 | -0.004 | 171.99 | 10.34% | 95.83% |
| 114 | 18.55% | +0.0043 | 20 | -0.073 | 88.97 | 4.15% | 95.00% |
| 115 | 18.52% | +0.0057 | 23 | -0.131 | 56.76 | 11.08% | 93.33% |
| 116 | 16.86% | -0.0014 | 35 | -0.071 | 60.71 | 3.59% | 94.17% |
| 117 | 15.05% | +0.0041 | 14 | -0.144 | 139.18 | 7.01% | 95.67% |
| 118 | 16.67% | +0.0058 | 13 | -0.027 | 110.42 | 8.38% | 95.67% |
| 119 | 22.29% | +0.0022 | 10 | -0.053 | 167.49 | 5.81% | 96.50% |
| 120 | 20.04% | +0.0052 | 17 | -0.100 | 114.39 | 8.96% | 95.33% |
