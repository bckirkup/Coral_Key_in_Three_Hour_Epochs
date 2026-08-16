# Baseline Comparisons (Without TattleTots)

Parameter scans using **only** conventional baseline architectures (A0–A3), no TattleTots agent ecology.

## Run from workspace root

```bash
cd D:\TotsFiles
uv run --no-sync --no-build --project Coral-Key-in-Three-Hour-Epochs python Coral-Key-in-Three-Hour-Epochs/baselines/run_coral_key_baselines.py --smoke-test
uv run --no-sync --no-build --project Coral-Key-in-Three-Hour-Epochs python Coral-Key-in-Three-Hour-Epochs/baselines/run_coral_key_baselines.py --workers 8
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
uv sync --locked --no-build --no-binary-package coral-key --no-binary-package domain-runner --no-binary-package tattletots --extra dev
```
