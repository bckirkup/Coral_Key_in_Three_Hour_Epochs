# Baseline Comparisons (Without TattleTots)

Parameter scans using **only** conventional baseline architectures (A0–A3), no TattleTots agent ecology.

## Run from workspace root

```bash
cd D:\TotsFiles
python Coral_Key_in_Three_Hour_Epochs/baselines/run_coral_key_baselines.py --smoke-test
python Coral_Key_in_Three_Hour_Epochs/baselines/run_coral_key_baselines.py --workers 8
```

Parallel mode uses **ProcessPoolExecutor** (separate Python worker processes).

## Files

| File | Purpose |
|------|---------|
| `run_coral_key_baselines.py` | Parameter scan runner |
| `coral_key_baselines_config.json` | Factor levels, seeds, epochs |
| `coral_key_baselines_results.zip` | Pre-computed results (optional) |

## Shared utilities

Multiprocessing helpers live in `TattleTots/Large Experiments/baseline_parallel.py`.

## Prerequisites

```bash
pip install -e TattleTots[dev]
pip install -e Coral_Key_in_Three_Hour_Epochs[dev]
```
