#!/usr/bin/env python3
"""Run Coral Key with TattleTots layer (thin wrapper — prefer `coral-key sim --layer tattletots`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from coral_key.runner import CoralDomainHooks, run_coral_simulation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coral Key + TattleTots integration")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--population", type=int, default=20)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    hooks = CoralDomainHooks()
    run = hooks.load_run_context(
        config_path=str(args.config) if args.config else None,
        cli_overrides={
            "layer": "tattletots",
            "verbose": args.verbose,
            "domain": {"total_epochs": args.epochs, "seed": args.seed},
            "simulation": {"initial_population": args.population, "max_steps": args.epochs, "seed": args.seed},
            "output": str(args.output) if args.output else None,
        },
    )
    run_coral_simulation(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
