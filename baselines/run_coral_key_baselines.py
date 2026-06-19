#!/usr/bin/env python3
"""Parameter Scan Runner for Coral Key Baselines (Without TattleTots).

Run from the workspace root (parent of all repos):

    python Coral_Key_in_Three_Hour_Epochs/baselines/run_coral_key_baselines.py --smoke-test
    python Coral_Key_in_Three_Hour_Epochs/baselines/run_coral_key_baselines.py --workers 8
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from coral_key.adapter import ReefWatchAdapter
from coral_key.baselines.architectures import run_baseline_comparison
from coral_key.config import ScenarioConfig

_SCRIPT_DIR = Path(__file__).resolve().parent
for _parent in [_SCRIPT_DIR, *_SCRIPT_DIR.parents]:
    _large_experiments = _parent / "TattleTots" / "Large Experiments"
    if (_large_experiments / "baseline_parallel.py").is_file():
        sys.path.insert(0, str(_large_experiments))
        break
else:
    sys.exit(
        "[-] Error: Could not find TattleTots/Large Experiments/baseline_parallel.py.\n"
        "    Ensure all repos are cloned as siblings under a common workspace root."
    )

from baseline_parallel import resolve_worker_count, run_process_pool


def run_single_simulation(
    run_name: str,
    epochs: int,
    seed: int,
    iuu_vessels: int,
    sar_revisit: int,
    adv_params: dict[str, float],
) -> dict[str, Any]:
    """Runs a single Coral Key simulation and evaluates all 4 baseline architectures."""
    start_time = time.time()

    config = ScenarioConfig()
    config.total_epochs = epochs
    config.seed = seed
    config.fleet.n_iuu_vessels = iuu_vessels
    config.sensors.sar_revisit_interval = sar_revisit
    config.adversary.ais_disable_probability = adv_params["ais_disable_probability"]
    config.adversary.spoof_probability = adv_params["spoof_probability"]
    config.fleet.underreport_fraction = adv_params["underreport_fraction"]
    config.adversary.platform_interference_rate = adv_params["platform_interference_rate"]

    adapter = ReefWatchAdapter(config=config)
    for epoch in range(epochs):
        adapter.step(epoch)

    biomass = adapter.fish_stock.get_total_biomass()
    bmsy = np.array([sp.b_msy for sp in adapter.fish_stock.species])
    cumulative = adapter.metrics_collector.compute_cumulative(biomass, bmsy)

    epoch_dicts = [m.model_dump() for m in adapter.metrics_collector.epoch_history]
    baselines = run_baseline_comparison(epoch_dicts)

    elapsed_time = time.time() - start_time
    baseline_results = {b.architecture: b.model_dump() for b in baselines}

    return {
        "status": "success",
        "elapsed_seconds": elapsed_time,
        "config": {
            "epochs": epochs,
            "seed": seed,
            "iuu_vessels": iuu_vessels,
            "sar_revisit_interval": sar_revisit,
            "adversary_params": adv_params,
        },
        "cumulative_metrics": cumulative.model_dump(),
        "baselines": baseline_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parameter Scan Runner for Coral Key Baselines")
    parser.add_argument(
        "--config",
        type=Path,
        default=_SCRIPT_DIR / "coral_key_baselines_config.json",
        help="Path to parameter scan config JSON file",
    )
    parser.add_argument("--smoke-test", action="store_true", help="Run a fast smoke test")
    parser.add_argument("--parallel", action="store_true", default=True)
    parser.add_argument("--no-parallel", action="store_false", dest="parallel")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel worker processes (default: min(CPU count, job count))",
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"[-] Error: Config file not found at {args.config}")
        return 1

    with open(args.config) as f:
        config_data = json.load(f)

    output_dir_name = (
        "coral_key_baselines_smoke_results"
        if args.smoke_test
        else config_data.get("output_directory", "coral_key_baselines_results")
    )
    output_dir = Path(output_dir_name).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    epochs = 5 if args.smoke_test else config_data.get("epochs", 800)
    seeds = [42] if args.smoke_test else config_data.get("seeds", [42, 43, 44])
    factors = config_data.get("factors", {})

    iuu_levels = [3] if args.smoke_test else factors.get("iuu_vessel_count", [3])
    adv_levels = ["medium"] if args.smoke_test else factors.get("adversary_level", ["medium"])
    sar_levels = [8] if args.smoke_test else factors.get("sar_revisit_interval", [8])

    runs_to_execute: list[dict[str, Any]] = []
    for iuu in iuu_levels:
        for adv in adv_levels:
            for sar in sar_levels:
                for seed in seeds:
                    run_name = f"ck_baselines_iuu{iuu}_adv{adv}_sar{sar}_s{seed}"
                    adv_params = config_data["adversary_levels"][adv]
                    runs_to_execute.append(
                        {
                            "name": run_name,
                            "epochs": epochs,
                            "seed": seed,
                            "iuu_vessels": iuu,
                            "sar_revisit": sar,
                            "adv_params": adv_params,
                            "metadata": {
                                "iuu_vessel_count": iuu,
                                "adversary_level": adv,
                                "sar_revisit_interval": sar,
                            },
                        }
                    )

    n_jobs = len(runs_to_execute)
    worker_count = resolve_worker_count(args.workers, n_jobs)

    print(f"[*] Results will be saved to: {output_dir}")
    print(f"[*] Generated {n_jobs} total run configurations.")
    if args.parallel:
        print(
            f"[*] Execution mode: PARALLEL (ProcessPoolExecutor, "
            f"{worker_count} worker process{'es' if worker_count != 1 else ''}, "
            f"PID {os.getpid()} parent)"
        )
    else:
        print(f"[*] Execution mode: SEQUENTIAL (single process, PID {os.getpid()})")
    print("=" * 60)

    results_key: dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "is_smoke_test": args.smoke_test,
        "output_directory": str(output_dir),
        "runs": {},
    }

    start_time = time.time()
    all_results: dict[str, Any] = {}
    logs: list[str] = []

    def _store_success(run: dict[str, Any], res: dict[str, Any]) -> None:
        name = run["name"]
        results_key["runs"][name] = {
            "status": res["status"],
            "elapsed_seconds": res["elapsed_seconds"],
            "metadata": run["metadata"],
            "baselines_summary": {
                b_name: {
                    "detection_rate": b_data["detection_rate"],
                    "false_alarm_rate": b_data["false_alarm_rate"],
                    "patrol_cost": b_data["patrol_cost"],
                }
                for b_name, b_data in res["baselines"].items()
            },
        }
        all_results[name] = res.copy()
        logs.append(f"[+] Completed: {name} in {res['elapsed_seconds']:.2f}s")

    def _store_failure(run: dict[str, Any], exc: Exception) -> None:
        results_key["runs"][run["name"]] = {"status": "failed", "error": str(exc)}

    job_args = [
        (
            run["name"],
            run["epochs"],
            run["seed"],
            run["iuu_vessels"],
            run["sar_revisit"],
            run["adv_params"],
        )
        for run in runs_to_execute
    ]

    if args.parallel:
        run_process_pool(
            run_single_simulation,
            job_args,
            runs_to_execute,
            max_workers=worker_count,
            on_success=_store_success,
            on_failure=_store_failure,
        )
    else:
        for run, kwargs in zip(runs_to_execute, job_args, strict=True):
            name = run["name"]
            try:
                _store_success(run, run_single_simulation(*kwargs))
                print(f"[+] Completed: {name}")
            except Exception as e:
                _store_failure(run, e)
                print(f"[-] Run '{name}' failed: {e}")

    total_elapsed = time.time() - start_time
    print("=" * 60)
    print(f"[+] All runs finished in {total_elapsed:.1f}s.")

    key_file_path = output_dir / "key.json"
    with open(key_file_path, "w") as f:
        json.dump(results_key, f, indent=2)
    print(f"[+] Parameter scan summary key written to: {key_file_path}")

    results_file_path = output_dir / "results.json"
    with open(results_file_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"[+] Consolidated results written to: {results_file_path}")

    log_file_path = output_dir / "all_runs.log"
    with open(log_file_path, "w") as f:
        f.write("=== Parameter Scan Execution Log ===\n")
        f.write(f"Timestamp: {datetime.datetime.now(datetime.UTC).isoformat()}\n")
        f.write(f"Total Runs: {len(runs_to_execute)}\n")
        f.write(f"Total Elapsed Time: {total_elapsed:.1f}s\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n".join(logs))
    print(f"[+] Consolidated logs written to: {log_file_path}")

    print("\n=== Coral Key Baselines Parameter Scan Summary ===")
    print(
        f"{'Run Name':<45} | {'Status':<10} | {'Time (s)':<8} | "
        f"{'A3 Det Rate':<12} | {'A3 FA Rate':<12}"
    )
    print("-" * 98)
    for name, run_res in results_key["runs"].items():
        if run_res.get("status") == "success":
            status = "success"
            elapsed = f"{run_res.get('elapsed_seconds', 0.0):.1f}"
            a3_summary = run_res["baselines_summary"].get("A3_Full_Centralized", {})
            a3_det = f"{a3_summary.get('detection_rate', 0.0):.1%}"
            a3_fa = f"{a3_summary.get('false_alarm_rate', 0.0):.1%}"
        else:
            status = "failed"
            elapsed = "N/A"
            a3_det = "N/A"
            a3_fa = "N/A"
        print(f"{name:<45} | {status:<10} | {elapsed:<8} | {a3_det:<12} | {a3_fa:<12}")
    print("=" * 98)

    any_failed = any(r.get("status") == "failed" for r in results_key["runs"].values())
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
