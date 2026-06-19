# Baseline Comparisons (Without TattleTots)

This directory contains scripts and results for running the Coral Key (ReefWatch)
simulation using **only** the conventional baseline detection architectures (A0-A3),
without the TattleTots agent ecology.

## Contents

| File | Purpose |
|------|---------|
| `run_coral_key_baselines.py` | Parameter scan runner sweeping IUU vessel count, adversary levels, and SAR revisit intervals |
| `coral_key_baselines_config.json` | Scan configuration (factors, seeds, epochs) |
| `coral_key_baselines_results.zip` | Pre-computed results from a full parameter scan |

## Usage

These scripts are designed to run from a workspace root that has all domain repos
installed. They depend on `baseline_parallel` (a shared utility in the TattleTots
`Large Experiments/` directory).

```bash
# From the workspace root (parent of all repos):
python Coral_Key_in_Three_Hour_Epochs/baselines/run_coral_key_baselines.py --smoke-test
```

## Relationship to TattleTots

These baselines serve as the **control group** for evaluating TattleTots agent
ecology performance. Compare results here against the integrated runs produced by
`scripts/run_with_tattletots.py`.
