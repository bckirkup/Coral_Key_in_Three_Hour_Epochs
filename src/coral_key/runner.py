"""ReefWatch simulation runner — layer-agnostic single/batch entry points."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from domain_runner.batch import run_batch as execute_batch
from domain_runner.config import deep_merge, load_json
from domain_runner.layer import DomainOnlyLayer
from domain_runner.single import print_result_summary, run_simulation_timed
from domain_runner.types import RunContext, SimulationResult

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig

_DEFAULT_DOMAIN: dict[str, Any] = {"total_epochs": 200, "seed": 42}


class CoralDomainHooks:
    domain_name = "coral_key"
    default_config_path = "configs/default.json"

    def load_run_context(
        self,
        *,
        config_path: str | None = None,
        cli_overrides: dict[str, Any] | None = None,
    ) -> RunContext:
        raw: dict[str, Any] = {"domain": dict(_DEFAULT_DOMAIN), "layer": "domain_only"}
        if config_path:
            raw = deep_merge(raw, load_json(config_path))
        if cli_overrides:
            if "domain" in cli_overrides:
                raw["domain"] = deep_merge(raw.get("domain", {}), cli_overrides["domain"])
            for key in ("layer", "simulation", "output", "verbose"):
                if key in cli_overrides:
                    raw[key] = cli_overrides[key]

        domain_cfg = dict(raw.get("domain", {}))
        steps = int(
            domain_cfg.pop("total_epochs", domain_cfg.pop("steps", _DEFAULT_DOMAIN["total_epochs"]))
        )
        return RunContext(
            steps=steps,
            seed=int(domain_cfg.get("seed", 42)),
            domain_config=domain_cfg,
            layer=str(raw.get("layer", "domain_only")),
            simulation_config=dict(raw.get("simulation", {})),
            verbose=bool(raw.get("verbose", False)),
            output_path=Path(raw["output"]) if raw.get("output") else None,
        )

    def build_adapter(self, domain_config: dict[str, Any]) -> ReefWatchAdapter:
        config = ScenarioConfig.model_validate(domain_config)
        return ReefWatchAdapter(config=config)

    def print_header(self, adapter: ReefWatchAdapter, run: RunContext) -> None:
        cfg = adapter._config
        print(f"=== Coral Key ({run.layer}) ===")
        print(f"  Epochs: {run.steps}, Seed: {run.seed}")
        print(f"  Grid: {cfg.ocean.n_zones_x}x{cfg.ocean.n_zones_y}")
        print()

    def on_step(self, adapter: ReefWatchAdapter, step: int, layer_events: dict[str, Any]) -> None:
        return

    def should_stop(
        self, adapter: ReefWatchAdapter, step: int, layer_events: dict[str, Any]
    ) -> bool:
        return bool(layer_events.get("stop"))

    def print_step(
        self, adapter: ReefWatchAdapter, step: int, layer_events: dict[str, Any], *, verbose: bool
    ) -> None:
        if verbose and step % 50 == 0:
            biomass = adapter.fish_stock.get_total_biomass()
            print(f"  Epoch {step:4d}: biomass={biomass.sum():.0f}")

    def summarize(self, adapter: ReefWatchAdapter, layer_metrics: dict[str, Any]) -> dict[str, Any]:
        biomass = adapter.fish_stock.get_total_biomass()
        bmsy = np.array([sp.b_msy for sp in adapter.fish_stock.species])
        cumulative = adapter.metrics_collector.compute_cumulative(biomass, bmsy)
        summary = cumulative.model_dump()
        if "telemetry_summary" in layer_metrics:
            summary["ecology"] = layer_metrics["telemetry_summary"]
        return summary

    def write_output(self, result: SimulationResult, path: str) -> None:
        if "simulation_output" in result.layer_metrics:
            output = result.layer_metrics["simulation_output"]
            output.run_summary.wall_time_seconds = result.wall_time_seconds
            output.domain_metrics = result.domain_metrics
            output.write_json(path)
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)


def resolve_layer(name: str):
    if name in ("domain_only", "domain", "none"):
        return DomainOnlyLayer()
    if name in ("tattletots", "tots"):
        from tattletots.integration.tattletots_layer import TattleTotsLayer

        return TattleTotsLayer()
    raise ValueError(f"Unknown layer {name!r}")


def run_coral_simulation(run: RunContext) -> SimulationResult:
    hooks = CoralDomainHooks()
    result = run_simulation_timed(hooks, resolve_layer(run.layer), run)
    print_result_summary(result)
    return result


def run_coral_batch_entry(
    name: str, run_config: dict[str, Any], output_dir: Path, verbose: bool
) -> dict[str, Any]:
    layer_name = str(run_config.pop("_layer", "domain_only"))
    simulation_config = dict(run_config.pop("simulation", {}))
    steps = int(
        run_config.pop("total_epochs", run_config.pop("steps", _DEFAULT_DOMAIN["total_epochs"]))
    )
    run = RunContext(
        steps=steps,
        seed=int(run_config.get("seed", 42)),
        domain_config=run_config,
        layer=layer_name,
        simulation_config=simulation_config,
        verbose=verbose,
        output_path=output_dir / f"{name}_results.json",
    )
    start = time.time()
    try:
        result = run_coral_simulation(run)
        return {
            "status": "success",
            "layer": layer_name,
            "elapsed_seconds": time.time() - start,
            "metrics": result.domain_metrics,
        }
    except Exception as exc:
        return {"status": "failed", "layer": layer_name, "error": str(exc)}


def run_coral_batch(batch_config_path: Path, **kwargs: Any) -> dict[str, Any]:
    batch = load_json(batch_config_path)
    out = Path(kwargs.get("output_dir") or batch.get("output_directory", "batch_results"))
    return execute_batch(
        batch,
        run_coral_batch_entry,
        output_dir=out,
        default_config={"domain": dict(_DEFAULT_DOMAIN)},
        parallel=bool(kwargs.get("parallel")),
        workers=kwargs.get("workers"),
        verbose=bool(kwargs.get("verbose")),
    )
