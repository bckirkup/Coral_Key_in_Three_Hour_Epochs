# AGENTS.md — AI Agent Guidelines for Coral Key in Three Hour Epochs

## Repository Purpose
ReefWatch fishery monitoring domain adapter for the TattleTots simulation engine.
Testbed for evaluating BMA/TattleTots architecture against centralized fishery
monitoring systems in a mixed ecological-adversarial environment.

## Setup
```bash
pip install -e domain-runner[dev]
pip install -e TattleTots[dev]   # only for --layer tattletots
pip install -e ".[dev]"
pre-commit install
```

## Validation Commands
Run these before committing:
```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest
```

## Architecture Rules
- **Implements TattleTots DomainAdapter**: Must conform to the ABC in `tattletots.interface.domain_adapter`
- **Never modify TattleTots**: This repo depends on TattleTots as an installed package
- **Streams are TattleTots Stream objects**: Use `tattletots.models.stream.Stream`
- **Users are TattleTots User objects**: Use `tattletots.models.user.User`
- **3-hour epoch time step**: All temporal logic is in 3-hour increments
- **Biomass floor**: Fish biomass never goes to zero (minimum 1.0)
- **Spatial distributions sum to 1**: Always renormalize after updates

## Key Files
| File | Purpose |
|------|---------|
| `src/coral_key/adapter.py` | Main DomainAdapter + COP dispatch hooks (`score_relevance` → band alignment) |
| `src/coral_key/runner.py` | domain-runner hooks (`CoralDomainHooks`, `run_coral_simulation`) |
| `src/coral_key/config.py` | All scenario configuration (Pydantic) |
| `src/coral_key/ocean/fish_stock.py` | Schaefer logistic production model |
| `src/coral_key/fleet/behavior.py` | Fleet lifecycle and fishing decisions |
| `src/coral_key/sensors/ais.py` | AIS stream with dark vessel / spoofing logic |
| `src/coral_key/adversary/iuu.py` | Ground truth IUU oracle |
| `src/coral_key/metrics.py` | Domain-specific metric collection |
| `tests/test_smoke.py` | Integration smoke tests |

## Domain Specifics
- **Species**: Schaefer model with MSY = rK/4, BMSY = K/2
- **Fleet types**: Legal (honest), Gaming (underreport/high-grade), IUU (MPA violators)
- **Sensor cadence**: AIS every epoch, SAR every 8 epochs, eDNA every 56 epochs
- **Adversary layers**: L1 (IUU), L2 (gaming), L3 (platform interference)
- **Users**: Patrol Commander (daily), Stock Scientist (quarterly), Policy Director (annual)

## Performance Notes
- Default 8x8 grid (64 zones) with 28 vessels for production runs
- Small test configs use 4x4 grid (16 zones) with ~9 vessels
- Smoke tests run 100-200 epochs; keep under 5 seconds

## PR Requirements
- All ruff checks pass
- mypy strict passes on src/
- All tests pass (including smoke tests)
- New features include tests
- Update README if adding new sensor types or adversary layers
