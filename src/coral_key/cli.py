"""CLI entry point for running ReefWatch simulations standalone."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from coral_key.runner import (
    CoralDomainHooks,
    _safe_path_under_base,
    run_coral_batch,
    run_coral_simulation,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Coral Key in Three Hour Epochs — ReefWatch fishery simulation"
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    sim_parser = subparsers.add_parser("sim", help="Run a single simulation")
    sim_parser.add_argument("--config", type=str)
    sim_parser.add_argument("--epochs", type=int)
    sim_parser.add_argument("--seed", type=int)
    sim_parser.add_argument("--layer", default="domain_only", choices=["domain_only", "tattletots"])
    sim_parser.add_argument("--verbose", action="store_true")
    sim_parser.add_argument("--output", type=str)

    batch_parser = subparsers.add_parser("batch", help="Run batch simulations")
    batch_parser.add_argument("--config", type=str, required=True)
    batch_parser.add_argument("--output-dir", type=Path)
    batch_parser.add_argument("--parallel", action="store_true")
    batch_parser.add_argument("--workers", type=int)
    batch_parser.add_argument("--verbose", action="store_true")

    effective = argv if argv is not None else sys.argv[1:]
    if effective and effective[0] not in ("sim", "batch", "-h", "--help"):
        effective = ["sim", *effective]
    elif not effective:
        effective = ["sim"]

    args = parser.parse_args(effective)

    if args.command == "batch":
        run_coral_batch(
            _safe_path_under_base(args.config),
            output_dir=_safe_path_under_base(args.output_dir) if args.output_dir else None,
            parallel=args.parallel,
            workers=args.workers,
            verbose=args.verbose,
        )
        return

    hooks = CoralDomainHooks()
    overrides: dict[str, Any] = {"verbose": args.verbose, "layer": args.layer}
    if args.epochs:
        overrides.setdefault("domain", {})["total_epochs"] = args.epochs
    if args.seed is not None:
        overrides.setdefault("domain", {})["seed"] = args.seed
    if args.output:
        overrides["output"] = str(_safe_path_under_base(args.output))

    run = hooks.load_run_context(config_path=args.config, cli_overrides=overrides)
    result = run_coral_simulation(run)
    if args.output and not _safe_path_under_base(args.output).exists():
        hooks.write_output(result, args.output)


if __name__ == "__main__":
    main()
