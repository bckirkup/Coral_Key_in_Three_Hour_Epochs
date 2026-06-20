# Cross-Repository Coordination Guide

This document explains how Coral Key integrates with TattleTots and the sibling domain repos.

## Repository Ecosystem

| Repository | Role | Package |
|------------|------|---------|
| **domain-runner** | Layer-agnostic single/batch runners | *(library)* |
| **TattleTots** | Agent ecology engine (domain-agnostic) | `tattletots` |
| **Coral_Key_in_Three_Hour_Epochs** (this repo) | ReefWatch fishery domain adapter | `coral-key` |
| **Xylella_SPQR** | GrainGuard agriculture domain adapter | `grain-guard` |
| **Scrapiron_and_the_Bear** | FireEcology wildfire domain adapter | `fire-ecology` |

## How Coral Key Connects to TattleTots

Coral Key implements the `DomainAdapter` ABC from TattleTots:

```python
from tattletots.interface.domain_adapter import DomainAdapter

class ReefWatchAdapter(DomainAdapter):
    def get_streams(self) -> list[Stream]: ...      # AIS, SAR, catch, ocean, eDNA, EM
    def get_users(self) -> list[User]: ...          # Patrol, Scientist, Director
    def step(self, time_step: int) -> None: ...     # Advance ocean + fleet + sensors
    def get_ground_truth(self, time_step: int) -> bool: ...  # IUU active?
    def compute_costs(self, ...) -> dict[str, float]: ...    # Patrol + damage costs
```

## Installation for Coordinated Use

```bash
pip install -e /path/to/domain-runner[dev]
pip install -e /path/to/TattleTots[dev]   # only for --layer tattletots
pip install -e ".[dev]"
```

## Running Modes

### Domain only (no agent ecology)

```bash
coral-key sim --layer domain_only --epochs 200 --verbose --output standalone_results.json
coral-key batch --config configs/batch_example.json
```

### Integrated (domain + TattleTots agent ecology + COP dispatch)

COP fusion uses `adapter.score_relevance()` with band-aligned role weighting (see TattleTots `engine/relevance.py`). Requires a current TattleTots install.

```bash
coral-key sim --layer tattletots --config configs/tattletots_integration.json --output integrated_results.json --verbose

# Legacy
python scripts/run_with_tattletots.py \
    --config configs/tattletots_integration.json \
    --output integrated_results.json \
    --verbose
```

## Configuration

The integrated config (`configs/tattletots_integration.json`) has two sections:

- **`simulation`**: TattleTots engine params (population size, mutation rate, trust dynamics)
- **`domain`**: Coral Key params (ocean grid, fleet composition, sensor cadence, adversary behavior)

### Key Parameters to Tune

| Parameter | Section | Effect |
|-----------|---------|--------|
| `initial_population` | simulation | Number of starting Tot agents |
| `max_stream_dim` | simulation | Per-agent input cap (keep ≤30 for performance) |
| `total_epochs` | domain | Length of fishery simulation |
| `n_iuu_vessels` | domain.fleet | IUU threat intensity |
| `sar_revisit_interval` | domain.sensors | SAR satellite frequency (epochs) |
| `enforcement_pressure` | domain.fleet | Deterrence effectiveness |

## Output Format

Integrated runs produce unified JSON (see TattleTots `docs/COORDINATION.md` for full schema).

Domain-specific metrics in `domain_metrics`:

```json
{
  "iuu_detection_rate": 0.85,
  "false_boarding_rate": 0.12,
  "patrol_cost": 2400.0,
  "dark_vessel_detection_latency": 3.2,
  "catch_underreporting_detection": 0.45,
  "stock_assessment_error": 0.18,
  "biomass_relative_to_bmsy": 0.92,
  "economic_loss_to_iuu": 1500.0
}
```

## Cross-Domain Comparison

All domain repos produce the same top-level structure. Compare across domains:

```python
from tattletots.output_schema import SimulationOutput

coral = SimulationOutput.read_json("coral_results.json")
fire = SimulationOutput.read_json("fire_results.json")
grain = SimulationOutput.read_json("grain_results.json")

# Same metrics available for each
for r in [coral, fire, grain]:
    print(f"{r.run_summary.domain}: cost={r.cost_metrics.total_cost:.0f} "
          f"precision={r.ecology_metrics.precision:.2%}")
```

## Relationship to Sibling Repos

Each domain repo is structurally parallel:
- `src/<package>/adapter/` — DomainAdapter implementation
- `scripts/run_with_tattletots.py` — Integrated runner
- `configs/tattletots_integration.json` — Default integrated config
- `docs/COORDINATION.md` — This file

The domains share no code with each other — only with TattleTots via the `DomainAdapter` interface. This ensures each domain can evolve independently while maintaining compatible outputs.
