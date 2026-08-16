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
