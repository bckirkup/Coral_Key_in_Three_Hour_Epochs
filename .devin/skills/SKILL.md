---
name: coral-key-development
description: Development workflow for the Coral Key ReefWatch fishery simulation domain adapter. Covers setup, testing, and extending the domain model.
---

# Coral Key Development Skill

## Quick Setup
```bash
cd /home/ubuntu/repos/Coral_Key_in_Three_Hour_Epochs
pip install -e ".[dev]"
pre-commit install
```

## Running Tests
```bash
# Full suite
pytest

# Smoke tests only (integration)
pytest -m smoke

# Specific module
pytest tests/test_ocean/
pytest tests/test_fleet/
pytest tests/test_sensors/
pytest tests/test_adversary/
pytest tests/test_adapter.py
pytest tests/test_metrics.py
```

## Linting & Type Checking
```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
```

## Running a Simulation
```bash
# Quick run with verbose output
coral-key --epochs 100 --verbose

# With custom config
coral-key --config scenario.json --output results.json

# Short test
coral-key --epochs 50 --seed 123 --verbose
```

## Architecture Overview

The adapter implements `tattletots.interface.domain_adapter.DomainAdapter`:
- `get_streams()` → 6 sensor streams (AIS, SAR, catch, ocean, eDNA, EM)
- `get_users()` → 3 user profiles (Patrol Commander, Stock Scientist, Policy Director)
- `step(time_step)` → advance simulation by one 3-hour epoch
- `get_ground_truth(time_step)` → whether IUU is currently active
- `score_relevance(signal, user)` → domain-specific relevance scoring
- `compute_costs(...)` → patrol, boarding, and damage costs

## Key Dependencies
- `tattletots` (the engine this domain plugs into)
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
