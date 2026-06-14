#!/usr/bin/env python3
"""Run Coral Key (ReefWatch) simulation integrated with the TattleTots engine.

This script plugs the ReefWatch domain adapter into the full TattleTots
agent ecology — agents compress sensor streams, evolve, form trophic
hierarchies, and escalate anomalies to human users.

Usage:
    python scripts/run_with_tattletots.py --config configs/tattletots_integration.json --output results.json
    python scripts/run_with_tattletots.py --epochs 200 --seed 7 --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from tattletots.engine.config import SimulationConfig
from tattletots.engine.world import World
from tattletots.output_schema import (
    CostMetrics,
    EcologyMetrics,
    RunSummary,
    SimulationOutput,
    TimeSeries,
)
from tattletots.telemetry.cost_accounting import CostAccumulator

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig


def main(argv: list[str] | None = None) -> int:
    """Run integrated Coral Key + TattleTots simulation."""
    parser = argparse.ArgumentParser(
        prog="run_with_tattletots",
        description="Coral Key: ReefWatch integrated with TattleTots agent ecology",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to JSON config file (contains 'simulation' and 'domain' sections)",
    )
    parser.add_argument("--epochs", type=int, default=200, help="Simulation epochs (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--population", type=int, default=20, help="Initial agent population")
    parser.add_argument("--output", type=Path, help="Path to write unified JSON results")
    parser.add_argument("--verbose", action="store_true", help="Print epoch-by-epoch progress")
    args = parser.parse_args(argv)

    # Load configuration
    if args.config:
        with open(args.config) as f:
            raw = json.load(f)
        sim_config = SimulationConfig(**raw.get("simulation", {}))
        domain_config = raw.get("domain", {})
        scenario_config = ScenarioConfig.model_validate(domain_config)
        epochs = raw.get("domain", {}).get("total_epochs", args.epochs)
    else:
        sim_config = SimulationConfig(
            initial_population=args.population,
            max_steps=args.epochs,
            seed=args.seed,
        )
        scenario_config = ScenarioConfig(total_epochs=args.epochs, seed=args.seed)
        epochs = args.epochs

    # Build domain adapter
    adapter = ReefWatchAdapter(config=scenario_config)

    # Build TattleTots world
    world = World(config=sim_config)
    for stream in adapter.get_streams():
        world.add_stream(stream)
    for user in adapter.get_users():
        world.add_user(user)
    world.seed_population()

    # Run simulation
    cost_accumulator = CostAccumulator()
    start_time = time.time()

    print("=== Coral Key + TattleTots Integration ===")
    print(f"  Epochs: {epochs}, Population: {sim_config.initial_population}, Seed: {args.seed}")
    print()

    for epoch in range(epochs):
        # Advance domain
        adapter.step(epoch)
        world.set_ground_truth(adapter.get_ground_truth(epoch))

        # Advance agent ecology
        record = world.step()

        if args.verbose and epoch % 50 == 0:
            print(
                f"  Epoch {epoch:4d}: pop={record.population:3d} "
                f"births={record.births} deaths={record.deaths} "
                f"reports={record.reports_issued} "
                f"trophic={record.max_trophic_level:.1f}"
            )

        # Cost accounting
        cost_dict = adapter.compute_costs(
            n_escalations=record.reports_issued,
            n_correct=record.correct_reports,
            n_false_alarms=record.false_alarms,
            n_missed=record.missed_events,
        )
        cost_accumulator.record_from_dict(record.time_step, cost_dict)

        if record.population == 0:
            print("  ** Total extinction **")
            break

    wall_time = time.time() - start_time

    # Gather results
    summary = world.telemetry.summary()
    cost_summary = cost_accumulator.summary()

    print()
    print("=== Simulation Complete ===")
    print(f"  Final population: {summary['final_population']}")
    print(f"  Precision:        {summary['precision']:.2%}")
    print(f"  Total cost:       {cost_summary['total_cost']:.2f}")
    print(f"  Wall time:        {wall_time:.1f}s")

    # Build unified output
    biomass = adapter.fish_stock.get_total_biomass()
    bmsy = np.array([sp.b_msy for sp in adapter.fish_stock.species])
    cumulative = adapter.metrics_collector.compute_cumulative(biomass, bmsy)

    output = SimulationOutput(
        run_summary=RunSummary(
            domain="coral_key",
            steps_completed=world.telemetry.total_steps,
            seed=args.seed,
            wall_time_seconds=wall_time,
        ),
        simulation_config=sim_config.model_dump(),
        domain_config=scenario_config.model_dump(),
        ecology_metrics=EcologyMetrics(
            final_population=int(summary["final_population"]),
            peak_population=int(summary["peak_population"]),
            total_births=int(summary["total_births"]),
            total_deaths=int(summary["total_deaths"]),
            total_reports=int(summary["total_reports"]),
            precision=float(summary["precision"]),
            max_trophic_depth=float(summary["max_trophic_depth"]),
            reached_equilibrium=bool(summary["reached_equilibrium"]),
        ),
        cost_metrics=CostMetrics(
            total_surveillance_cost=cost_summary["total_surveillance_cost"],
            total_response_cost=cost_summary["total_response_cost"],
            total_damage_cost=cost_summary["total_damage_cost"],
            total_cost=cost_summary["total_cost"],
            mean_cost_per_step=cost_summary["mean_cost_per_step"],
        ),
        domain_metrics=cumulative.model_dump(),
        time_series=TimeSeries(
            population=world.telemetry.population_history(),
            cost_per_step=cost_accumulator.cost_history(),
        ),
    )

    if args.output:
        output.write_json(args.output)
        print(f"\n  Results written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
