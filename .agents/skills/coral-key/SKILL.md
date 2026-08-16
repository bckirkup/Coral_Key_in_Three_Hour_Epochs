---
name: coral-key-development
description: Development workflow for the Coral Key ReefWatch fishery simulation domain adapter. Covers setup, testing, and extending the domain model.
---

# Coral Key Development Skill

## Quick Setup
```bash
uv sync --locked --no-build --no-binary-package coral-key --no-binary-package domain-runner --no-binary-package tattletots --extra dev
uv run --no-sync --no-build pre-commit install
```

## Running Tests
```bash
# Full suite
uv run --no-sync --no-build pytest

# Smoke tests only (integration)
uv run --no-sync --no-build pytest -m smoke

# Specific module
uv run --no-sync --no-build pytest tests/test_ocean/
uv run --no-sync --no-build pytest tests/test_fleet/
uv run --no-sync --no-build pytest tests/test_sensors/
uv run --no-sync --no-build pytest tests/test_adversary/
uv run --no-sync --no-build pytest tests/test_adapter.py
uv run --no-sync --no-build pytest tests/test_metrics.py
```

## Linting & Type Checking
```bash
uv run --no-sync --no-build ruff check src/ tests/
uv run --no-sync --no-build ruff format --check src/ tests/
uv run --no-sync --no-build mypy src/
```

## Running a Simulation
```bash
uv run --no-sync --no-build coral-key sim --layer domain_only --epochs 100 --verbose
uv run --no-sync --no-build coral-key sim --layer tattletots --config configs/tattletots_integration.json
uv run --no-sync --no-build coral-key batch --config configs/batch_example.json

# Legacy
uv run --no-sync --no-build coral-key --epochs 100 --verbose
uv run --no-sync --no-build coral-key --config scenario.json --output results.json
```

## Architecture Overview

The adapter implements `tattletots.interface.domain_adapter.DomainAdapter`:
- `get_streams()` → 6 sensor streams (AIS, SAR, catch, ocean, eDNA, EM)
- `get_users()` → 3 user profiles (Patrol Commander, Stock Scientist, Policy Director)
- `step(time_step)` → advance simulation by one 3-hour epoch
- `get_ground_truth(time_step)` → whether IUU is currently active
- `get_active_locations(time_step)` → returns `(zone_x, zone_y)` for each active IUU vessel
- `infer_report_location(stream_data, stream_labels)` → finds peak in AIS stream → maps to grid zone
- `score_relevance(signal, user)` → band-aligned role relevance via `tattletots.engine.relevance`
- `compute_costs(...)` → patrol, boarding, and damage costs
- `get_responder_user_id()` → user authorized for COP dispatch
- `dispatch_and_judge_responses(targets, time_step)` → boarding/interdiction outcomes

**Note:** The integration loop uses `world.set_event_state(adapter.get_active_locations(epoch))` (not `set_ground_truth`). Agents must not read `User.trust`.

### Baselines

Standalone baseline comparison files live in `baselines/`:
- `run_coral_key_baselines.py` — Parameter scan runner for A0-A3 architectures
- `coral_key_baselines_config.json` — Scan configuration
- `coral_key_baselines_results.zip` — Pre-computed results

## Integrated Mode (TattleTots Agent Ecology)

```bash
uv run --no-sync --no-build coral-key sim --layer tattletots --config configs/tattletots_integration.json --output results.json --verbose
```

Output conforms to `tattletots.output_schema.SimulationOutput` (unified JSON).
See `docs/COORDINATION.md` for coordination with sibling repos.

## GPU Acceleration

```bash
uv sync --locked --no-build --no-binary-package coral-key --no-binary-package domain-runner --no-binary-package tattletots --extra dev --extra gpu
```

Set `"use_gpu": true` in the `"simulation"` section of the integration config.
Falls back silently to NumPy if CuPy or CUDA is unavailable.

## Parameter Scans

Generate config variants and run in parallel for large sweeps:

```bash
uv run --no-sync --no-build python scripts/run_with_tattletots.py --config <variant>.json --output results/<name>.json
```

Key domain parameters to sweep: `total_epochs`, `n_iuu_vessels`, `n_gaming_vessels`,
`grid_size`, `seed`.

Load results:
```python
from tattletots.output_schema import SimulationOutput
result = SimulationOutput.model_validate_json(path.read_text())
```

## Key Dependencies
- `tattletots` (installed from GitHub: `git+https://github.com/bckirkup/TattleTots.git`)
- `numpy`
- `pydantic>=2.0`

## Extending the Domain

### Adding a new sensor
1. Create `src/coral_key/sensors/new_sensor.py` with `observe()` method
2. Add to `src/coral_key/sensors/__init__.py`
3. Register in `adapter.py` (`_setup_streams` and `_generate_observations`)
4. Add tests in `tests/test_sensors/test_new_sensor.py`

### Adding a new adversary layer
1. Create module in `src/coral_key/adversary/`
2. Integrate in `adapter.step()` method
3. Update metrics collection if new observables emerge

### Adjusting scenario parameters
All config is in `src/coral_key/config.py` using Pydantic models.
Override via JSON config file or constructor parameters.

## Testing the Designed-Reporter Measurement Harness

`scripts/run_designed_reporter_experiment.py` measures the domain's exploitable
margin (best reachable precision minus its own static-prior null) across the
`ordinary` / `all_designed_seed` / `invasion` / `oracle_upper_bound` arms, using
`src/coral_key/reporter_policy.py` as the hand-designed reporter.

### Fast rerun, and the artifact-clobbering trap

The production config (`--epochs 200`, 20 seeds) takes tens of minutes. A fast
verification run:

```bash
uv run --no-sync --no-build python scripts/run_designed_reporter_experiment.py \
  --epochs 30 --seeds 42 43 --grounded-arm 0.67 --jobs 2
```

The script has **no `--docs-dir` flag**: it always writes into `docs/`, so a short
run overwrites the committed artifacts (`docs/designed_reporter_measurement.{json,md}`
and `docs/grounded_access/<label>__<arm>.json`). Restore them afterwards:

```bash
git restore docs/
```

Short windows also print a `WARNING: Coral nulls differ from the 200-step
references` line — expected, not a failure; the nulls are window-dependent.

### What to assert on the artifacts

- All four arms present; each arm file validates via
  `SimulationOutput.model_validate_json`.
- Every `*precision*` / `*rate*` / `*_null*` / `*share*` / `*fraction*` finite and
  within [0,1]; every `*_pp` within [-100,100].
- Markdown agrees with the JSON on the static-prior null, the best feasible arm
  and its precision, the margin in pp, and the ordinary-vs-null wording.
- Each arm's precision recomputes from its raw counts, and per-seed counts sum to
  the pooled totals.
- The oracle arm is never the source of `best_feasible_arm`; with all feasible arms
  zeroed the best feasible arm must come back `None`, not the oracle.

### Determinism, with one legitimate exception

Same command twice must give identical `nulls` / arm summaries / margin and
byte-identical Markdown, and `--jobs 1` must reproduce `--jobs N`. But per-arm
`SimulationOutput` JSON stamps a `timestamp`, so those files are **not**
byte-reproducible — never write a byte-comparison check on them.

### Tamper-testing the reporter policy (two traps)

`CoralEvidenceReporterPolicy` is registered via `register_reporter_policy`.

- Patching the policy class's attribute default is a **no-op** — the registered
  factory already captured it. Re-register the factory with the changed parameter.
- With real IUU events present, the strongest true detection dominates the max, so
  changing the evidence threshold looks like it does nothing. Prove the threshold
  is load-bearing in a **no-event window** (false positives only): threshold on →
  zero designed reports; threshold at 0 → many reports, none correct.

### Ground-truth boundary

The feasible reporter must not reach `adapter.get_ground_truth()` or
`adapter.get_active_locations()` — those belong to the oracle arm only. Assert it
structurally (the reporter module never names them) and at runtime (spy on
`decide(context)`; the context should expose only the public reporter fields).
Also assert the oracle policy instance appears only in the oracle arm's world.

### Reporting precision that comes from silence

A designed reporter reaching ~100% precision does so by declining to report, and
can legitimately exceed the instrument's inferability precision for the same
reason. Always publish the price alongside it (reports per adult lifetime, raw
report counts) and say so in the writeup, or the number reads like a truth leak.
