#!/usr/bin/env python3
"""Grade the Coral Key evidence-only reporter through the ordinary economy."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from tattletots.engine.config import SimulationConfig
from tattletots.engine.world import World
from tattletots.interface.instrument import validate_instrument
from tattletots.interface.reporter_policy import (
    ReporterDecision,
    ReporterPolicyContext,
    register_reporter_policy,
)

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig
from coral_key.reporter_policy import CORAL_REPORTER_POLICY_NAME

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPORTER_FRACTION = 0.15
_ORACLE_POLICY_NAME = "coral_oracle_diagnostic_upper_bound"


@dataclass
class _OracleDiagnosticPolicy:
    """Harness-local oracle; never ship or use as a designed reporter."""

    active_locations: tuple[tuple[int, int], ...] = ()

    def decide(self, context: ReporterPolicyContext) -> ReporterDecision:
        if not self.active_locations:
            return ReporterDecision(escalate=False)
        return ReporterDecision(escalate=True, location=self.active_locations[0])


register_reporter_policy(_ORACLE_POLICY_NAME, _OracleDiagnosticPolicy)


def _build_world(seed: int, epochs: int) -> tuple[ReefWatchAdapter, World]:
    adapter = ReefWatchAdapter(config=ScenarioConfig(seed=seed, total_epochs=epochs))
    config = SimulationConfig(
        initial_population=20,
        max_population=60,
        max_steps=epochs,
        seed=seed,
        mutation_rate=0.1,
        recombination_probability=0.3,
        false_alarm_penalty=0.4,
        trust_delta_neg=0.2,
        trust_delta_pos=0.05,
        trust_delta_miss=0.15,
        subsidy_rate=0.1,
        max_stream_dim=30,
    )
    world = World(config=config)
    for stream in adapter.get_streams():
        world.add_stream(stream)
    for user in adapter.get_users():
        world.add_user(user)
    world.seed_population()
    world.set_location_inference(adapter.infer_report_location)
    world.set_dim_to_location(adapter.dim_index_to_location)
    return adapter, world


def _tag_population(world: World, arm: str) -> None:
    agents = list(world.agents.values())
    if arm == "ordinary":
        return
    if arm == "all_designed":
        selected = agents
        policy_name = CORAL_REPORTER_POLICY_NAME
    elif arm == "invasion":
        count = max(1, int(round(len(agents) * _REPORTER_FRACTION)))
        selected = agents[:count]
        policy_name = CORAL_REPORTER_POLICY_NAME
    elif arm == "oracle_upper_bound":
        selected = agents
        policy_name = _ORACLE_POLICY_NAME
    else:
        raise ValueError(f"Unknown arm {arm!r}")

    for agent in selected:
        agent.genome.reporter_policy = policy_name
        world._init_agent_model(agent)


def _set_oracle_locations(
    world: World,
    active_locations: list[tuple[int, int]],
) -> None:
    locations = tuple(active_locations)
    for policy in world.reporter_policies.values():
        if isinstance(policy, _OracleDiagnosticPolicy):
            policy.active_locations = locations


def _policy_evidence_rates(world: World) -> dict[str, float]:
    policies = [
        policy
        for policy in world.reporter_policies.values()
        if isinstance(policy, _OracleDiagnosticPolicy) is False
        and hasattr(policy, "decision_steps")
    ]
    decisions = sum(int(policy.decision_steps) for policy in policies)
    ais = sum(int(policy.ais_evidence_steps) for policy in policies)
    sar = sum(int(policy.sar_evidence_steps) for policy in policies)
    either = sum(int(policy.ais_or_sar_evidence_steps) for policy in policies)
    denominator = max(decisions, 1)
    return {
        "adult_designed_steps": float(decisions),
        "ais_evidence_rate": ais / denominator,
        "sar_evidence_rate": sar / denominator,
        "ais_or_sar_evidence_rate": either / denominator,
    }


def _arm_run(seed: int, epochs: int, arm: str) -> dict[str, Any]:
    adapter, world = _build_world(seed, epochs)
    _tag_population(world, arm)
    for epoch in range(epochs):
        adapter.step(epoch)
        active_locations = adapter.get_active_locations(epoch)
        world.set_event_state(active_locations)
        _set_oracle_locations(world, active_locations)
        world.step()

    series = world.telemetry.ecology_time_series()
    designed_reports = int(sum(series["designed_reports"]))
    ordinary_reports = int(sum(series["ordinary_reports"]))
    designed_correct = int(sum(series["designed_correct_reports"]))
    ordinary_correct = int(sum(series["ordinary_correct_reports"]))
    reports = sum(record.reports_issued for record in world.telemetry.history)
    correct = sum(record.correct_reports for record in world.telemetry.history)
    if arm == "oracle_upper_bound":
        return {
            "seed": seed,
            "arm": arm,
            "oracle_reports": reports,
            "oracle_correct_reports": correct,
            "oracle_precision": correct / max(reports, 1),
            "population_share_trajectory": series["designed_population_share"],
        }

    return {
        "seed": seed,
        "arm": arm,
        "designed_reports": designed_reports,
        "ordinary_reports": ordinary_reports,
        "designed_correct_reports": designed_correct,
        "ordinary_correct_reports": ordinary_correct,
        "designed_precision": designed_correct / max(designed_reports, 1),
        "ordinary_precision": ordinary_correct / max(ordinary_reports, 1),
        "population_share_trajectory": series["designed_population_share"],
        "evidence_rates": _policy_evidence_rates(world),
    }


def _null_measurements(seeds: list[int], epochs: int) -> dict[str, Any]:
    del seeds
    validation_seed = 42
    adapter = ReefWatchAdapter(config=ScenarioConfig(seed=validation_seed, total_epochs=epochs))
    report = validate_instrument(adapter, steps=epochs)
    static_prior = report.static_prior_baseline
    uniform = report.chance_baseline
    if abs(static_prior - 0.148) > 0.03 or abs(uniform - 0.016) > 0.005:
        raise RuntimeError(
            "Coral nulls disagree materially with the established references: "
            f"static_prior={static_prior:.4f}, uniform={uniform:.4f}"
        )
    return {
        "validation_seed": validation_seed,
        "candidate_locations": len(report.candidate_locations),
        "inferability_precision": report.inferability_precision,
        "mean_static_prior_precision": static_prior,
        "mean_uniform_precision": uniform,
    }


def _summarize_arms(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for arm, runs in results.items():
        if arm == "oracle_upper_bound":
            reports = sum(int(run["oracle_reports"]) for run in runs)
            correct = sum(int(run["oracle_correct_reports"]) for run in runs)
            summary[arm] = {
                "reports": reports,
                "correct_reports": correct,
                "precision": correct / max(reports, 1),
            }
            continue
        designed_reports = sum(int(run["designed_reports"]) for run in runs)
        ordinary_reports = sum(int(run["ordinary_reports"]) for run in runs)
        designed_correct = sum(int(run["designed_correct_reports"]) for run in runs)
        ordinary_correct = sum(int(run["ordinary_correct_reports"]) for run in runs)
        trajectories = [run["population_share_trajectory"] for run in runs]
        evidence = [run["evidence_rates"] for run in runs]
        summary[arm] = {
            "designed_reports": designed_reports,
            "ordinary_reports": ordinary_reports,
            "designed_correct_reports": designed_correct,
            "ordinary_correct_reports": ordinary_correct,
            "designed_precision": designed_correct / max(designed_reports, 1),
            "ordinary_precision": ordinary_correct / max(ordinary_reports, 1),
            "mean_final_designed_population_share": float(
                np.mean([trajectory[-1] for trajectory in trajectories])
            ),
            "mean_ais_evidence_rate": float(
                np.mean([item["ais_evidence_rate"] for item in evidence])
            ),
            "mean_sar_evidence_rate": float(
                np.mean([item["sar_evidence_rate"] for item in evidence])
            ),
            "mean_ais_or_sar_evidence_rate": float(
                np.mean([item["ais_or_sar_evidence_rate"] for item in evidence])
            ),
        }
    return summary


def _markdown(results: dict[str, Any]) -> str:
    lines = [
        "# Coral Key designed reporter measurement",
        "",
        "The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.",
        "The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.",
        "",
        f"- Seeds: `{', '.join(str(seed) for seed in results['seeds'])}`",
        f"- Epochs per run: `{results['epochs']}`",
        f"- Mean static-prior precision: **{results['nulls']['mean_static_prior_precision']:.2%}**",
        f"- Mean uniform precision: **{results['nulls']['mean_uniform_precision']:.2%}**",
        "",
        "| Arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ("ordinary", "all_designed", "invasion"):
        item = results["summary"][arm]
        lines.append(
            f"| {arm} | {item['designed_precision']:.2%} | "
            f"{item['ordinary_precision']:.2%} | {item['designed_reports']} | "
            f"{item['ordinary_reports']} | {item['mean_final_designed_population_share']:.2%} | "
            f"{item['mean_ais_evidence_rate']:.2%} | {item['mean_sar_evidence_rate']:.2%} | "
            f"{item['mean_ais_or_sar_evidence_rate']:.2%} |"
        )
    oracle = results["summary"]["oracle_upper_bound"]
    lines.extend(
        [
            f"| oracle diagnostic upper bound | {oracle['precision']:.2%} | — | "
            f"{oracle['reports']} | — | — | — | — | — |",
            "",
            "Precision is computed from report and correct-report counts in the time series.",
            "A zero-report group is shown as 0% by the denominator convention, not interpreted as poor precision.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "docs" / "designed_reporter_measurement.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=_REPO_ROOT / "docs" / "designed_reporter_measurement.md",
    )
    args = parser.parse_args()

    results: dict[str, Any] = {
        "seeds": args.seeds,
        "epochs": args.epochs,
        "nulls": _null_measurements(args.seeds, args.epochs),
        "runs": {},
    }
    for arm in ("ordinary", "all_designed", "invasion", "oracle_upper_bound"):
        results["runs"][arm] = [_arm_run(seed, args.epochs, arm) for seed in args.seeds]
    results["summary"] = _summarize_arms(results["runs"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(_markdown(results), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
