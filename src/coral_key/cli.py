"""CLI entry point for running ReefWatch simulations standalone."""

from __future__ import annotations

import argparse
import json

import numpy as np

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig


def main(argv: list[str] | None = None) -> None:
    """Run a ReefWatch simulation."""
    parser = argparse.ArgumentParser(
        description="Coral Key in Three Hour Epochs — ReefWatch fishery simulation"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Number of epochs to simulate (overrides config)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (overrides config)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print epoch-by-epoch summary",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write JSON results",
    )
    args = parser.parse_args(argv)

    # Load or create config
    if args.config:
        adapter = ReefWatchAdapter.from_config_file(args.config)
        config = adapter._config
    else:
        config = ScenarioConfig()
        if args.epochs:
            config.total_epochs = args.epochs
        if args.seed is not None:
            config.seed = args.seed
        adapter = ReefWatchAdapter(config=config)

    total_epochs = args.epochs or config.total_epochs

    print("=== Coral Key: ReefWatch Simulation ===")
    print(f"Epochs: {total_epochs} ({total_epochs * config.epoch_hours:.0f} hours)")
    print(f"Grid: {config.ocean.n_zones_x}x{config.ocean.n_zones_y}")
    print(f"Species: {config.fish.n_species}")
    print(
        f"Fleet: {config.fleet.n_legal_vessels}L / {config.fleet.n_gaming_vessels}G / {config.fleet.n_iuu_vessels}I"
    )
    print()

    # Run simulation
    for epoch in range(total_epochs):
        adapter.step(epoch)

        if args.verbose and epoch % 50 == 0:
            biomass = adapter.fish_stock.get_total_biomass()
            history = adapter.metrics_collector.epoch_history
            latest = history[-1] if history else None
            iuu_count = latest.iuu_vessels_active if latest else 0
            print(
                f"  Epoch {epoch:4d} | "
                f"Biomass: {biomass.sum():.0f} | "
                f"IUU active: {iuu_count} | "
                f"Dark vessels: {latest.dark_vessels_detected if latest else 0}"
            )

    # Final metrics
    biomass = adapter.fish_stock.get_total_biomass()
    bmsy = np.array([sp.b_msy for sp in adapter.fish_stock.species])
    cumulative = adapter.metrics_collector.compute_cumulative(biomass, bmsy)

    print("\n=== Final Metrics ===")
    print(f"Biomass/BMSY ratio: {cumulative.biomass_relative_to_bmsy:.2f}")
    print(f"Stock assessment error: {cumulative.stock_assessment_error:.3f}")
    print(f"Catch underreporting detection: {cumulative.catch_underreporting_detection:.3f}")
    print(f"Patrol cost: {cumulative.patrol_cost:.0f}")
    print(f"Economic loss to IUU: {cumulative.economic_loss_to_iuu:.1f}")

    # Write output
    if args.output:
        results = {
            "config": adapter.to_config(),
            "metrics": cumulative.model_dump(),
            "final_biomass": biomass.tolist(),
            "epochs_run": total_epochs,
        }
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
