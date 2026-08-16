# Coral Key in Three Hour Epochs

**ReefWatch** — a fishery monitoring, IUU detection, and ocean sensor ecology domain adapter for the [TattleTots](https://github.com/bckirkup/TattleTots) simulation engine.

## Overview

Coral Key simulates a marine protected area (MPA) with surrounding legal fishing grounds. It tests whether a TattleTots information ecology can improve fishery monitoring and IUU (Illegal, Unreported, Unregulated) detection in a mixed ecological-adversarial domain.

The simulation advances in **3-hour epochs**, modeling:
- **Fish stock dynamics** — Schaefer logistic production model with spatial distribution
- **Mixed fleet** — Legal, gaming (underreporting), and IUU vessels with strategic behavior
- **6 sensor modalities** — AIS/VMS, SAR satellite, catch reports, oceanographic data, eDNA, electronic monitoring
- **Adversarial behavior** — AIS disabling/spoofing, platform interference, catch underreporting
- **3 user profiles** — Patrol Commander, Stock Assessment Scientist, Policy Director

## Installation

```bash
git clone https://github.com/bckirkup/Coral_Key_in_Three_Hour_Epochs.git
cd Coral_Key_in_Three_Hour_Epochs
uv sync --locked --no-build --no-binary-package coral-key --no-binary-package domain-runner --no-binary-package tattletots --extra dev
uv run --no-sync --no-build pre-commit install
```

The lockfile provides the domain-runner and TattleTots dependencies.

## Quick Start

```bash
uv run --no-sync --no-build coral-key sim --layer domain_only --epochs 200 --verbose
uv run --no-sync --no-build coral-key batch --config configs/batch_example.json

# Legacy
uv run --no-sync --no-build coral-key --epochs 200 --verbose
uv run --no-sync --no-build coral-key --config scenario.json --output results.json
```

### As a TattleTots Domain Adapter

```python
from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig

config = ScenarioConfig(total_epochs=672, seed=42)
adapter = ReefWatchAdapter(config=config)

# Plug into TattleTots engine
streams = adapter.get_streams()
users = adapter.get_users()

for epoch in range(672):
    adapter.step(epoch)
    ground_truth = adapter.get_ground_truth(epoch)
```

## Architecture

```
src/coral_key/
├── adapter.py          # DomainAdapter implementation (ReefWatchAdapter)
├── config.py           # Pydantic scenario configuration
├── cli.py              # Standalone CLI
├── users.py            # Domain user profiles
├── metrics.py          # Metrics collection and scoring
├── ocean/
│   ├── grid.py         # Spatial grid with MPA/port zones
│   ├── oceanography.py # SST, chlorophyll, currents, seasons
│   └── fish_stock.py   # Schaefer production model
├── fleet/
│   ├── vessel.py       # Vessel models (legal/gaming/IUU)
│   └── behavior.py     # Fleet lifecycle and fishing decisions
├── sensors/
│   ├── ais.py          # AIS/VMS with dark vessel detection
│   ├── sar.py          # SAR satellite vessel detection
│   ├── catch_reports.py # Self-reported catch (falsifiable)
│   ├── oceanographic.py # Ocean state observations
│   ├── edna.py         # Environmental DNA sampling
│   └── electronic_monitoring.py  # On-vessel cameras
└── adversary/
    ├── iuu.py          # IUU ground truth oracle
    └── interference.py # Platform interference (Layer 3)
```

## Sensor Streams

| Stream | Update Frequency | Failure Modes |
|--------|-----------------|---------------|
| AIS/VMS | Every epoch (3h) | AIS disabled, spoofed position |
| SAR Satellite | Every 8 epochs (24h) | Cloud cover, missed detection |
| Catch Reports | Every epoch | Underreporting, false location |
| Oceanographic | Every epoch | Platform interference |
| eDNA | Every 56 epochs (7 days) | Low sensitivity, sparse |
| Electronic Monitoring | Every epoch (sampled) | Limited review rate |

## Adversary Model

- **Layer 1 — IUU Fishers**: Fish in MPA, disable AIS, spoof positions, underreport catch
- **Layer 2 — Gaming Fishers**: High-grade, misreport fine-scale location, small underreports
- **Layer 3 — Platform Interference**: Jam command links, foul sensors, induce data gaps

## Metrics

- IUU detection rate
- False boarding/inspection rate
- Patrol cost
- Dark-vessel detection latency
- Catch underreporting detection
- Stock assessment error (biomass vs. BMSY)
- Economic loss to IUU

## Integrated Mode (with TattleTots Agent Ecology)

```bash
uv run --no-sync --no-build coral-key sim --layer tattletots --config configs/tattletots_integration.json --output results.json --verbose
```

Legacy:

```bash
uv run --no-sync --no-build python scripts/run_with_tattletots.py \
    --config configs/tattletots_integration.json \
    --output results.json \
    --verbose
```

This produces unified JSON output (`tattletots.output_schema.SimulationOutput`) with consistent `ecology_metrics` and `cost_metrics` fields, enabling cross-domain comparison with the sibling repos ([Xylella_SPQR](https://github.com/bckirkup/Xylella_SPQR), [Scrapiron_and_the_Bear](https://github.com/bckirkup/Scrapiron_and_the_Bear)).

See [docs/COORDINATION.md](docs/COORDINATION.md) for full coordination guide, configuration reference, and comparison examples.

## Development

```bash
# Lint
uv run --no-sync --no-build ruff check src/ tests/
uv run --no-sync --no-build ruff format --check src/ tests/

# Type check
uv run --no-sync --no-build mypy src/

# Test
uv run --no-sync --no-build pytest                    # Full suite
uv run --no-sync --no-build pytest -m smoke           # Smoke tests only
uv run --no-sync --no-build pytest tests/test_ocean/  # Specific module
```

## Falsification Test

The BMA/TattleTots ecology must improve either:
1. IUU detection at equal or lower patrol cost, OR
2. Stock assessment accuracy at equal or lower monitoring cost,

compared to centralized AIS+SAR+catch+oceanography fusion (Architecture A3).

## License

Apache-2.0 — see [LICENSE](LICENSE).
