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
| ordinary | 0.00% | 17.90% | 0 | 525336 | 0.00% | 0.00% | 0.00% | 0.00% |

| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |
|---|---:|---:|---:|---:|---:|---:|
| ordinary | 22.79% | 100.00% | 100.00% | -0.083 | 20 | 60.0 |

Falsification clauses and reporting economics (payoff levers on):

| Quantity | `ordinary` |
|---|---|
| Adult correct-report rate | 17.77% |
| Clause 1 slope per generation | +0.0020 |
| Generations observed | 18.1 |
| Clause 2 parent–child offspring r | -0.083 |
| Parent–child precision r | +0.250 |
| Reports per adult lifetime | 95.17 |
| Share of adults that never report | 6.46% |
| Eligible-to-reproduce share | 94.28% |
| Steps where the population cap binds | 94.70% |
| Mean offspring, ever-correct adults | 1.358 |
| Mean offspring, never-correct adults | 1.050 |
| Mean offspring, silent adults | 1.115 |
| Seeds with a rising correct-report rate | 13/20 |
| Seeds with clause 2 r above 0.2 | 0/20 |

Per-seed clause metrics, `ordinary` arm:

| Seed | Correct-report rate | Clause 1 slope/generation | Generations | Clause 2 r | Reports/adult | Silent adults | Cap binds |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 16.46% | -0.0006 | 18 | -0.039 | 95.18 | 4.75% | 94.83% |
| 43 | 19.44% | +0.0058 | 15 | +0.010 | 80.41 | 3.97% | 94.00% |
| 44 | 10.11% | -0.0018 | 41 | -0.083 | 33.23 | 4.17% | 92.50% |
| 45 | 24.67% | -0.0022 | 12 | -0.103 | 126.24 | 9.87% | 96.00% |
| 46 | 13.81% | -0.0025 | 15 | -0.054 | 103.81 | 7.21% | 95.83% |
| 47 | 20.38% | +0.0033 | 21 | -0.154 | 87.40 | 6.34% | 95.33% |
| 48 | 21.39% | +0.0012 | 15 | -0.154 | 123.53 | 3.46% | 95.83% |
| 49 | 18.02% | +0.0024 | 11 | -0.109 | 119.52 | 9.22% | 95.00% |
| 50 | 11.60% | +0.0033 | 27 | -0.079 | 52.91 | 3.82% | 93.17% |
| 51 | 19.11% | +0.0098 | 17 | -0.163 | 101.64 | 5.34% | 94.67% |
| 52 | 16.44% | +0.0028 | 15 | -0.038 | 83.45 | 6.43% | 94.17% |
| 53 | 21.15% | +0.0077 | 14 | -0.133 | 75.17 | 7.35% | 95.17% |
| 54 | 18.17% | +0.0014 | 15 | -0.055 | 147.54 | 10.05% | 95.00% |
| 55 | 18.21% | -0.0016 | 19 | -0.011 | 96.10 | 8.06% | 96.00% |
| 56 | 17.45% | +0.0129 | 12 | -0.094 | 162.52 | 9.19% | 96.17% |
| 57 | 17.07% | -0.0008 | 14 | -0.153 | 113.62 | 2.74% | 94.00% |
| 58 | 15.32% | +0.0017 | 27 | -0.040 | 61.62 | 4.94% | 91.50% |
| 59 | 16.28% | +0.0039 | 17 | -0.082 | 48.38 | 11.36% | 94.17% |
| 60 | 18.55% | -0.0158 | 14 | -0.122 | 109.70 | 3.49% | 97.50% |
| 61 | 21.72% | +0.0097 | 23 | +0.005 | 81.53 | 7.47% | 93.17% |
