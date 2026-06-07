# Contributing to Coral Key in Three Hour Epochs

## Rule 0: Patch, don't report

If you find a bug, fix it. Don't open an issue describing it unless you cannot
fix it yourself. This follows the TattleTots contribution philosophy.

## Setup

```bash
pip install -e ".[dev]"
pre-commit install
```

## Before Committing

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest
```

All four commands must pass cleanly.

## Code Style

- Python 3.11+ with strict typing
- Pydantic v2 for data models
- NumPy for numerical operations
- `from __future__ import annotations` in every module
- Line length: 100 characters (ruff enforced)
- No comments explaining the diff — comments explain the code in general

## Testing

- Unit tests for every module in `tests/test_<module>/`
- Smoke tests in `tests/test_smoke.py` for integration validation
- Use `pytest.mark.smoke` for tests that validate emergent behavior
- Use `pytest.mark.slow` for tests that take >5 seconds
- Test configs should use small grids (4x4) for speed

## Architecture

This repo implements `tattletots.interface.domain_adapter.DomainAdapter`.
Never import internal TattleTots engine code — only use the public interface
(`DomainAdapter`, `Stream`, `User`).

## Adding New Sensor Types

1. Create `src/coral_key/sensors/new_sensor.py`
2. Implement `dimensionality`, `label`, and `observe()` interface
3. Register in `adapter.py` (`_setup_streams` and `_generate_observations`)
4. Add to `sensors/__init__.py`
5. Write tests in `tests/test_sensors/test_new_sensor.py`
6. Update README sensor table

## Adding New Adversary Layers

1. Create module in `src/coral_key/adversary/`
2. Integrate in `ReefWatchAdapter.step()` method
3. Add to `adversary/__init__.py`
4. Update `EpochMetrics` if new observables emerge
5. Write tests and update README
