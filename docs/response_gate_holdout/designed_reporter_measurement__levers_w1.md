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
| ordinary | 0.00% | 19.70% | 0 | 499795 | 0.00% | 0.00% | 0.00% | 0.00% |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 24.44% | 100.00% | 100.00% | +0.005 | 20 | 60.0 |

Falsification clauses and reporting economics (payoff levers on):

| Quantity | `ordinary` |
|---|---|
| Adult correct-report rate | 19.60% |
| Clause 1 slope per generation | +0.0066 |
| Generations observed | 14.1 |
| Clause 2 parent–child offspring r | +0.005 |
| Parent–child precision r | +0.123 |
| Reports per adult lifetime | 84.26 |
| Share of adults that never report | 6.85% |
| Eligible-to-reproduce share | 94.54% |
| Steps where the population cap binds | 91.24% |
| Mean offspring, ever-correct adults | 1.308 |
| Mean offspring, never-correct adults | 1.085 |
| Mean offspring, silent adults | 1.119 |
| Seeds with a rising correct-report rate | 19/20 |
| Seeds with clause 2 r above 0.2 | 1/20 |

Per-seed clause metrics, `ordinary` arm:

| Seed | Correct-report rate | Clause 1 slope/generation | Generations | Clause 2 r | Reports/adult | Silent adults | Cap binds |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 101 | 19.04% | +0.0020 | 13 | -0.159 | 125.37 | 7.72% | 93.33% |
| 102 | 21.73% | +0.0034 | 8 | +0.079 | 123.67 | 5.65% | 94.67% |
| 103 | 15.01% | +0.0028 | 17 | -0.025 | 50.70 | 6.76% | 91.33% |
| 104 | 17.27% | +0.0032 | 18 | -0.037 | 50.74 | 5.29% | 86.33% |
| 105 | 19.85% | +0.0139 | 15 | +0.078 | 90.22 | 4.39% | 91.17% |
| 106 | 20.19% | +0.0026 | 13 | +0.015 | 131.26 | 7.38% | 93.00% |
| 107 | 18.24% | +0.0055 | 12 | +0.069 | 123.03 | 10.57% | 93.50% |
| 108 | 21.84% | +0.0057 | 18 | -0.119 | 62.62 | 7.96% | 91.00% |
| 109 | 20.35% | +0.0045 | 22 | +0.041 | 32.51 | 4.80% | 82.33% |
| 110 | 18.46% | -0.0004 | 13 | -0.028 | 69.96 | 11.14% | 90.67% |
| 111 | 20.80% | +0.0090 | 15 | +0.106 | 40.69 | 5.59% | 89.50% |
| 112 | 16.87% | +0.0076 | 11 | -0.065 | 76.83 | 5.74% | 92.50% |
| 113 | 22.78% | +0.0095 | 11 | +0.206 | 108.35 | 10.00% | 94.17% |
| 114 | 19.48% | +0.0075 | 15 | -0.011 | 53.73 | 5.12% | 87.83% |
| 115 | 22.15% | +0.0101 | 16 | +0.046 | 82.46 | 8.89% | 91.17% |
| 116 | 20.47% | +0.0082 | 12 | +0.036 | 115.10 | 7.87% | 92.33% |
| 117 | 16.99% | +0.0080 | 13 | -0.030 | 77.81 | 5.58% | 92.17% |
| 118 | 19.21% | +0.0129 | 12 | -0.035 | 81.22 | 5.47% | 92.17% |
| 119 | 20.71% | +0.0072 | 10 | -0.017 | 140.30 | 3.18% | 96.00% |
| 120 | 20.57% | +0.0083 | 18 | -0.051 | 48.61 | 7.83% | 89.67% |
