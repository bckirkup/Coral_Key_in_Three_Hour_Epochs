#!/usr/bin/env python3
"""Grade the Coral Key evidence-only reporter through the ordinary economy."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
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
from tattletots.models.genome import Genome
from tattletots.output_schema import (
    EcologyMetrics,
    RunSummary,
    SimulationOutput,
    TimeSeries,
)

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig
from coral_key.reporter_policy import CORAL_REPORTER_POLICY_NAME

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPORTER_FRACTION = 0.15
_MAX_STREAM_DIM = 48
_ORACLE_POLICY_NAME = "coral_oracle_diagnostic_upper_bound"
_POLICY_ARMS = ("ordinary", "all_designed_seed", "invasion", "oracle_upper_bound")
_DEFAULT_SEEDS = [
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    61,
]


@dataclass(frozen=True)
class GroundedArm:
    """Grounded raw-stream access knobs for one measurement arm."""

    fraction: float = 0.0
    multiplier: float = 1.0
    max_input_streams: int = 3

    @property
    def label(self) -> str:
        """Stable arm label used in output keys and file names."""
        return f"f{self.fraction:g}_m{self.multiplier:g}_k{self.max_input_streams}".replace(
            ".", "p"
        )


def parse_grounded_arm(spec: str) -> GroundedArm:
    """Parse a `fraction[,multiplier[,max_input_streams]]` arm specification."""
    parts = [part.strip() for part in spec.split(",") if part.strip()]
    if not parts or len(parts) > 3:
        raise ValueError(f"Invalid grounded arm specification: {spec!r}")
    fraction = float(parts[0])
    multiplier = float(parts[1]) if len(parts) > 1 else 1.0
    max_inputs = int(parts[2]) if len(parts) > 2 else 3
    return GroundedArm(fraction=fraction, multiplier=multiplier, max_input_streams=max_inputs)


@dataclass
class _OracleDiagnosticPolicy:
    """Harness-local oracle; never ship or use as a designed reporter."""

    active_locations: tuple[tuple[int, int], ...] = ()

    def decide(self, _context: ReporterPolicyContext) -> ReporterDecision:
        if not self.active_locations:
            return ReporterDecision(escalate=False)
        return ReporterDecision(escalate=True, location=self.active_locations[0])


register_reporter_policy(_ORACLE_POLICY_NAME, _OracleDiagnosticPolicy)


def _build_world(
    seed: int,
    epochs: int,
    arm: str,
    grounded: GroundedArm,
) -> tuple[ReefWatchAdapter, World]:
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
        max_stream_dim=_MAX_STREAM_DIM,
        max_input_streams=grounded.max_input_streams,
        grounded_input_fraction=grounded.fraction,
        grounded_attractiveness_multiplier=grounded.multiplier,
    )
    world = World(config=config)
    for stream in adapter.get_streams():
        world.add_stream(stream)
    for user in adapter.get_users():
        world.add_user(user)
    genomes = [
        Genome.random_genome(
            world.rng,
            n_streams=max(len(world.streams), 1),
            n_users=max(len(world.users), 1),
            gene_pool=world.gene_pool,
        )
        for _ in range(config.initial_population)
    ]
    if arm == "all_designed_seed":
        selected = range(len(genomes))
        policy_name = CORAL_REPORTER_POLICY_NAME
    elif arm == "invasion":
        selected = range(max(1, int(round(len(genomes) * _REPORTER_FRACTION))))
        policy_name = CORAL_REPORTER_POLICY_NAME
    elif arm == "oracle_upper_bound":
        selected = range(len(genomes))
        policy_name = _ORACLE_POLICY_NAME
    elif arm == "ordinary":
        selected = ()
        policy_name = None
    else:
        raise ValueError(f"Unknown arm {arm!r}")
    for index in selected:
        genomes[index].reporter_policy = policy_name
    world.seed_population(genomes=genomes)
    world.set_location_inference(adapter.infer_report_location)
    world.set_dim_to_location(adapter.dim_index_to_location)
    return adapter, world


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


def _parent_child_reproductive_correlation(world: World) -> float | None:
    """Pearson correlation between a parent's and its child's offspring counts."""
    offspring: Counter[str] = Counter()
    for agent in world.agents.values():
        for parent_id in agent.state.parent_ids:
            offspring[parent_id] += 1
    parents: list[float] = []
    children: list[float] = []
    for agent in world.agents.values():
        for parent_id in agent.state.parent_ids:
            if parent_id not in world.agents:
                continue
            parents.append(float(offspring[parent_id]))
            children.append(float(offspring[agent.id]))
    if len(parents) < 3:
        return None
    parent_counts = np.asarray(parents, dtype=np.float64)
    child_counts = np.asarray(children, dtype=np.float64)
    if parent_counts.std() == 0.0 or child_counts.std() == 0.0:
        return None
    return float(np.corrcoef(parent_counts, child_counts)[0, 1])


def _arm_run(seed: int, epochs: int, arm: str, grounded: GroundedArm) -> dict[str, Any]:
    adapter, world = _build_world(seed, epochs, arm, grounded)
    dead_designed_reports = 0
    for epoch in range(epochs):
        adapter.step(epoch)
        active_locations = adapter.get_active_locations(epoch)
        world.set_event_state(active_locations)
        _set_oracle_locations(world, active_locations)
        designed_ids_before_step = {
            agent.id
            for agent in world.agents.values()
            if agent.is_alive and agent.genome.reporter_policy == CORAL_REPORTER_POLICY_NAME
        }
        world.step()
        dead_designed_reports += sum(
            1
            for report in world.last_reports
            if report.agent_id in designed_ids_before_step
            and (report.agent_id not in world.agents or not world.agents[report.agent_id].is_alive)
        )

    series = world.telemetry.ecology_time_series()
    designed_reports = int(sum(series["designed_reports"]))
    ordinary_reports = int(sum(series["ordinary_reports"]))
    designed_correct = int(sum(series["designed_correct_reports"]))
    ordinary_correct = int(sum(series["ordinary_correct_reports"]))
    reports = sum(record.reports_issued for record in world.telemetry.history)
    correct = sum(record.correct_reports for record in world.telemetry.history)
    summary = world.telemetry.summary()
    ecology = {
        "attention_solvent_fraction": float(summary["attention_solvent_fraction"]),
        "mean_attention_carrying_capacity": float(summary["mean_attention_carrying_capacity"]),
        "grounded_yield_share": float(summary["grounded_yield_share"]),
        "effective_grounded_yield_share": float(summary["effective_grounded_yield_share"]),
        "max_trophic_depth": float(summary["max_trophic_depth"]),
        "final_population": int(summary["final_population"]),
        "peak_population": int(summary["peak_population"]),
        "total_births": int(summary["total_births"]),
        "total_deaths": int(summary["total_deaths"]),
        "initiation_is_degenerate": bool(summary["initiation_is_degenerate"]),
        "initiation_degeneracy_reasons": list(summary["initiation_degeneracy_reasons"]),
    }
    shared = {
        "seed": seed,
        "arm": arm,
        "grounded_arm": grounded.label,
        "ecology": ecology,
        "parent_child_reproductive_correlation": _parent_child_reproductive_correlation(world),
        "time_series": series,
    }
    if arm == "oracle_upper_bound":
        return {
            **shared,
            "oracle_reports": reports,
            "oracle_correct_reports": correct,
            "oracle_precision": correct / max(reports, 1),
            "population_share_trajectory": series["designed_population_share"],
        }

    return {
        **shared,
        "designed_reports": designed_reports,
        "ordinary_reports": ordinary_reports,
        "designed_correct_reports": designed_correct,
        "ordinary_correct_reports": ordinary_correct,
        "designed_precision": designed_correct / max(designed_reports, 1),
        "ordinary_precision": ordinary_correct / max(ordinary_reports, 1),
        "population_share_trajectory": series["designed_population_share"],
        "evidence_rates": _policy_evidence_rates(world),
        "designed_reports_classified_ordinary_after_death": dead_designed_reports,
    }


def _null_measurements(seeds: list[int], epochs: int) -> dict[str, Any]:
    del seeds
    validation_seed = 42
    adapter = ReefWatchAdapter(config=ScenarioConfig(seed=validation_seed, total_epochs=epochs))
    report = validate_instrument(adapter, steps=epochs)
    static_prior = report.static_prior_baseline
    uniform = report.chance_baseline
    if epochs == 200 and (abs(static_prior - 0.148) > 0.03 or abs(uniform - 0.016) > 0.005):
        raise RuntimeError(
            "Coral nulls disagree materially with the established references at the "
            f"default window: static_prior={static_prior:.4f}, uniform={uniform:.4f}"
        )
    if epochs != 200 and (abs(static_prior - 0.148) > 0.03 or abs(uniform - 0.016) > 0.005):
        print(
            "WARNING: Coral nulls differ from the 200-step references at this measured "
            f"window ({epochs} steps): static_prior={static_prior:.4f}, uniform={uniform:.4f}"
        )
    return {
        "validation_seed": validation_seed,
        "candidate_locations": len(report.candidate_locations),
        "inferability_precision": report.inferability_precision,
        "mean_static_prior_precision": static_prior,
        "mean_uniform_precision": uniform,
    }


def _ecology_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-arm means of the solvency, grounded-yield and heritability metrics."""
    correlations = [
        float(run["parent_child_reproductive_correlation"])
        for run in runs
        if run["parent_child_reproductive_correlation"] is not None
    ]

    def mean_of(key: str) -> float:
        return float(np.mean([run["ecology"][key] for run in runs]))

    return {
        "mean_attention_solvent_fraction": mean_of("attention_solvent_fraction"),
        "mean_attention_carrying_capacity": mean_of("mean_attention_carrying_capacity"),
        "mean_grounded_yield_share": mean_of("grounded_yield_share"),
        "mean_effective_grounded_yield_share": mean_of("effective_grounded_yield_share"),
        "mean_max_trophic_depth": mean_of("max_trophic_depth"),
        "mean_final_population": mean_of("final_population"),
        "total_births": sum(int(run["ecology"]["total_births"]) for run in runs),
        "total_deaths": sum(int(run["ecology"]["total_deaths"]) for run in runs),
        "n_degenerate_runs": sum(1 for run in runs if run["ecology"]["initiation_is_degenerate"]),
        "mean_parent_child_reproductive_correlation": (
            float(np.mean(correlations)) if correlations else None
        ),
        "n_runs_with_reproductive_correlation": len(correlations),
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
                "ecology": _ecology_summary(runs),
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
            "designed_reports_classified_ordinary_after_death": sum(
                int(run["designed_reports_classified_ordinary_after_death"]) for run in runs
            ),
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
            "ecology": _ecology_summary(runs),
        }
    return summary


def _busiest_invasion_seed(invasion_runs: list[dict[str, Any]]) -> dict[str, Any]:
    return max(invasion_runs, key=lambda run: int(run["designed_reports"]))


_SERIES_SUM_KEYS = frozenset(
    {
        "population",
        "reports_issued",
        "correct_reports",
        "false_alarms",
        "missed_events",
        "responses_dispatched",
        "responses_judged_necessary",
        "responses_judged_unnecessary",
        "n_attention_solvent_agents",
        "n_attention_eligible_agents",
        "births",
        "deaths",
        "n_compression_types",
        "designed_reports",
        "ordinary_reports",
        "designed_correct_reports",
        "ordinary_correct_reports",
    }
)

_PROVENANCE_LINES = [
    "",
    "## Superseded provenance",
    "",
    "The pre-grounding-fix measurement recorded here previously reported, at the same",
    "20 seeds, 200 epochs and `max_stream_dim=48`, against a 14.84% static-prior null",
    "and a 1.56% uniform null:",
    "",
    "| Superseded arm | Designed precision | Ordinary precision | Designed reports | AIS/SAR evidence |",
    "|---|---:|---:|---:|---:|",
    "| ordinary | 0.00% | 3.11% | 0 | 0.00% |",
    "| all-designed seed | 26.16% | 0.00% | 474 | 1.49% |",
    "| invasion | 32.79% | 2.66% | 61 | 1.41% |",
    "",
    "Those numbers were measured against the `tattletots` revision pinned in this",
    "repository's lockfile at the time. The arms in this document were measured",
    "against the grounded-access branch build of `tattletots`, which also carries",
    "engine changes unrelated to the grounded knobs, so the 0.0 arm here is the",
    "correct baseline for the comparison and is not run-for-run comparable to the",
    "superseded table. The superseded numbers are kept as provenance only.",
    "",
    "The earlier artifact measured at `max_stream_dim=30`, under which 18 of the 48",
    "declared oceanographic features reached no agent, remains superseded for the",
    "same reason: the agents' input space differs.",
]


def _pooled_time_series(runs: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """Pool per-seed series: counts are summed, rates are averaged, step by step."""
    length = min(len(run["time_series"]["population"]) for run in runs)
    pooled: dict[str, list[Any]] = {}
    for key in runs[0]["time_series"]:
        stacked = np.asarray(
            [run["time_series"][key][:length] for run in runs],
            dtype=np.float64,
        )
        if key in _SERIES_SUM_KEYS:
            pooled[key] = [int(value) for value in stacked.sum(axis=0)]
        else:
            pooled[key] = [float(value) for value in stacked.mean(axis=0)]
    return pooled


def _pooled_ecology_metrics(
    policy_arm: str,
    arm_summary: dict[str, Any],
    series: dict[str, list[Any]],
    nulls: dict[str, Any],
) -> EcologyMetrics:
    ecology = arm_summary["ecology"]
    reports = int(sum(series["reports_issued"]))
    correct = int(sum(series["correct_reports"]))
    designed_share = (
        0.0
        if policy_arm == "oracle_upper_bound"
        else float(arm_summary["mean_final_designed_population_share"])
    )
    designed_precision = (
        float(arm_summary["precision"])
        if policy_arm == "oracle_upper_bound"
        else float(arm_summary["designed_precision"])
    )
    ordinary_precision = (
        0.0 if policy_arm == "oracle_upper_bound" else float(arm_summary["ordinary_precision"])
    )
    return EcologyMetrics(
        final_population=int(round(ecology["mean_final_population"])),
        total_births=int(ecology["total_births"]),
        total_deaths=int(ecology["total_deaths"]),
        total_reports=reports,
        precision=correct / max(reports, 1),
        chance_precision=float(nulls["mean_uniform_precision"]),
        static_prior_precision=float(nulls["mean_static_prior_precision"]),
        location_support_size=int(nulls["candidate_locations"]),
        grounded_yield_share=float(ecology["mean_grounded_yield_share"]),
        effective_grounded_yield_share=float(ecology["mean_effective_grounded_yield_share"]),
        attention_solvent_fraction=float(ecology["mean_attention_solvent_fraction"]),
        mean_attention_carrying_capacity=float(ecology["mean_attention_carrying_capacity"]),
        max_trophic_depth=float(ecology["mean_max_trophic_depth"]),
        designed_population_share=designed_share,
        designed_precision=designed_precision,
        ordinary_precision=ordinary_precision,
    )


def _simulation_output(
    grounded: GroundedArm,
    policy_arm: str,
    runs: list[dict[str, Any]],
    arm_summary: dict[str, Any],
    results: dict[str, Any],
) -> SimulationOutput:
    """Build a seed-pooled SimulationOutput record for one grounded/policy arm."""
    series = _pooled_time_series(runs)
    return SimulationOutput(
        run_summary=RunSummary(
            domain="coral_key",
            steps_completed=int(results["epochs"]),
            seed=None,
        ),
        simulation_config={
            "max_stream_dim": _MAX_STREAM_DIM,
            "max_input_streams": grounded.max_input_streams,
            "grounded_input_fraction": grounded.fraction,
            "grounded_attractiveness_multiplier": grounded.multiplier,
            "initial_population": 20,
            "max_population": 60,
            "max_steps": int(results["epochs"]),
            "seeds": list(results["seeds"]),
        },
        domain_config={
            "total_epochs": int(results["epochs"]),
            "seeds": list(results["seeds"]),
            "policy_arm": policy_arm,
        },
        ecology_metrics=_pooled_ecology_metrics(policy_arm, arm_summary, series, results["nulls"]),
        domain_metrics={
            "policy_arm": policy_arm,
            "grounded_arm": {
                "label": grounded.label,
                "grounded_input_fraction": grounded.fraction,
                "grounded_attractiveness_multiplier": grounded.multiplier,
                "max_input_streams": grounded.max_input_streams,
            },
            "nulls": results["nulls"],
            "arm_summary": arm_summary,
            "per_seed": [
                {key: value for key, value in run.items() if key != "time_series"} for run in runs
            ],
            "pooling": "counts summed across seeds; rates averaged across seeds",
        },
        time_series=TimeSeries(**series),
    )


def _markdown_header(results: dict[str, Any]) -> list[str]:
    nulls = results["nulls"]
    lines = [
        "# Coral Key designed reporter measurement",
        "",
        "The designed policy uses only published AIS metadata/status and fresh SAR metadata/data.",
        "The oracle row is a harness-local diagnostic upper bound and is not a shipped policy.",
        "",
        f"- Seeds: `{', '.join(str(seed) for seed in results['seeds'])}`",
        f"- Epochs per run: `{results['epochs']}`",
        f"- Per-agent input cap (`max_stream_dim`): `{results['max_stream_dim']}`",
        f"- Mean static-prior precision (null): **{nulls['mean_static_prior_precision']:.2%}**",
        f"- Mean uniform precision (null): **{nulls['mean_uniform_precision']:.2%}**",
        "",
        "Grounded raw-stream access arms (`SimulationConfig.grounded_input_fraction`,",
        "`grounded_attractiveness_multiplier`, `max_input_streams`):",
        "",
        "| Grounded arm | Reserved grounded fraction | Raw attractiveness multiplier | Input slots |",
        "|---|---:|---:|---:|",
    ]
    for spec in results["grounded_arms"]:
        lines.append(
            f"| `{spec['label']}` | {spec['fraction']:.2f} | "
            f"{spec['multiplier']:.2f} | {spec['max_input_streams']} |"
        )
    lines.extend(
        [
            "",
            "The `fraction 0.00, multiplier 1.00` arm is the baseline: at those values the",
            "engine's stream attachment and its random-number consumption are identical to",
            "unreserved attachment.",
        ]
    )
    return lines


def _arm_table(summary: dict[str, Any]) -> list[str]:
    lines = [
        "| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ("ordinary", "all_designed_seed", "invasion"):
        item = summary[arm]
        label = "all-designed seed" if arm == "all_designed_seed" else arm
        lines.append(
            f"| {label} | {item['designed_precision']:.2%} | "
            f"{item['ordinary_precision']:.2%} | {item['designed_reports']} | "
            f"{item['ordinary_reports']} | {item['mean_final_designed_population_share']:.2%} | "
            f"{item['mean_ais_evidence_rate']:.2%} | {item['mean_sar_evidence_rate']:.2%} | "
            f"{item['mean_ais_or_sar_evidence_rate']:.2%} |"
        )
    oracle = summary["oracle_upper_bound"]
    lines.append(
        f"| oracle diagnostic upper bound | {oracle['precision']:.2%} | — | "
        f"{oracle['reports']} | — | — | — | — | — |"
    )
    return lines


def _ecology_table(summary: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "| Policy arm | Attention solvency | Grounded yield share | Effective grounded yield share | Parent–child reproductive r | Runs with r | Mean final population |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ("ordinary", "all_designed_seed", "invasion", "oracle_upper_bound"):
        ecology = summary[arm]["ecology"]
        correlation = ecology["mean_parent_child_reproductive_correlation"]
        rendered = "—" if correlation is None else f"{correlation:+.3f}"
        lines.append(
            f"| {arm} | {ecology['mean_attention_solvent_fraction']:.2%} | "
            f"{ecology['mean_grounded_yield_share']:.2%} | "
            f"{ecology['mean_effective_grounded_yield_share']:.2%} | {rendered} | "
            f"{ecology['n_runs_with_reproductive_correlation']} | "
            f"{ecology['mean_final_population']:.1f} |"
        )
    return lines


def _per_seed_table(invasion_runs: list[dict[str, Any]]) -> list[str]:
    lines = [
        "",
        "Invasion per-seed report counts:",
        "",
        "| Seed | Designed reports | Designed correct reports | Designed precision |",
        "|---:|---:|---:|---:|",
    ]
    for run in invasion_runs:
        lines.append(
            f"| {run['seed']} | {run['designed_reports']} | "
            f"{run['designed_correct_reports']} | {run['designed_precision']:.2%} |"
        )
    return lines


def _arm_section(results: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    arm = results["arms"][spec["label"]]
    heading = (
        f"## Grounded arm `{spec['label']}` — fraction {spec['fraction']:.2f}, "
        f"multiplier {spec['multiplier']:.2f}, {spec['max_input_streams']} input slots"
    )
    lines = ["", heading, ""]
    lines.extend(_arm_table(arm["summary"]))
    lines.extend(_ecology_table(arm["summary"]))
    lines.extend(_per_seed_table(arm["runs"]["invasion"]))
    return lines


def _cross_arm_section(results: dict[str, Any]) -> list[str]:
    nulls = results["nulls"]
    lines = [
        "",
        "## Grounded access comparison",
        "",
        f"Nulls for every row: static prior {nulls['mean_static_prior_precision']:.2%}, "
        f"uniform {nulls['mean_uniform_precision']:.2%}.",
        "",
        "| Grounded fraction | Invasion AIS∨SAR evidence | All-designed AIS∨SAR evidence | Invasion designed precision | Invasion ordinary precision | All-designed designed precision | Invasion solvency | Invasion grounded yield share |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for spec in results["grounded_arms"]:
        summary = results["arms"][spec["label"]]["summary"]
        invasion = summary["invasion"]
        designed = summary["all_designed_seed"]
        lines.append(
            f"| {spec['fraction']:.2f} (×{spec['multiplier']:.2f}) | "
            f"{invasion['mean_ais_or_sar_evidence_rate']:.2%} | "
            f"{designed['mean_ais_or_sar_evidence_rate']:.2%} | "
            f"{invasion['designed_precision']:.2%} | "
            f"{invasion['ordinary_precision']:.2%} | "
            f"{designed['designed_precision']:.2%} | "
            f"{invasion['ecology']['mean_attention_solvent_fraction']:.2%} | "
            f"{invasion['ecology']['mean_grounded_yield_share']:.2%} |"
        )
    return lines


def _evidence_delta_lines(results: dict[str, Any]) -> list[str]:
    baseline_label = results["grounded_arms"][0]["label"]
    baseline = results["arms"][baseline_label]["summary"]
    baseline_rate = float(baseline["invasion"]["mean_ais_or_sar_evidence_rate"])
    lines = []
    for spec in results["grounded_arms"][1:]:
        summary = results["arms"][spec["label"]]["summary"]
        rate = float(summary["invasion"]["mean_ais_or_sar_evidence_rate"])
        ratio = rate / baseline_rate if baseline_rate > 0 else float("inf")
        lines.append(
            f"- Grounded fraction {spec['fraction']:.2f} (multiplier "
            f"{spec['multiplier']:.2f}): invasion AIS∨SAR evidence "
            f"{rate:.2%} versus the {baseline_rate:.2%} baseline "
            f"({ratio:.2f}× baseline); invasion designed precision "
            f"{summary['invasion']['designed_precision']:.2%}, invasion ordinary "
            f"precision {summary['invasion']['ordinary_precision']:.2%}."
        )
    return lines


def _interpretation(results: dict[str, Any]) -> list[str]:
    baseline_label = results["grounded_arms"][0]["label"]
    baseline = results["arms"][baseline_label]["summary"]
    invasion_runs = results["arms"][baseline_label]["runs"]["invasion"]
    nulls = results["nulls"]
    lines = [
        "",
        "## Interpretation",
        "",
        "Every precision below is read against the same two nulls: a "
        f"{nulls['mean_static_prior_precision']:.2%} static-prior precision and a "
        f"{nulls['mean_uniform_precision']:.2%} uniform precision.",
        "",
        "At the baseline grounded fraction the designed reporter sees AIS and/or SAR "
        f"evidence on {baseline['invasion']['mean_ais_or_sar_evidence_rate']:.2%} of adult "
        "designed-agent steps in the invasion arm and "
        f"{baseline['all_designed_seed']['mean_ais_or_sar_evidence_rate']:.2%} in the "
        "all-designed arm, because the available inputs are drawn from a pool "
        "dominated by peer residual streams.",
        "",
    ]
    lines.extend(_evidence_delta_lines(results))
    lines.extend(
        [
            "",
            "The per-agent input cap is set to the widest stream ReefWatch declares, so "
            "every declared oceanographic feature can reach an agent.",
            "",
            "The all-designed-seed arm begins with every seeded genome tagged, and the "
            "reporter-group telemetry resolves each report through its author's genome "
            "even when that author dies during the same step. The diagnostic found "
            f"{baseline['all_designed_seed']['designed_reports_classified_ordinary_after_death']} "
            "such reports in the baseline arm; they remain credited to the designed group.",
            "",
            f"The baseline invasion arm has {baseline['invasion']['designed_reports']} "
            "designed reports in total, of which the busiest single seed (seed "
            f"{_busiest_invasion_seed(invasion_runs)['seed']}) contributes "
            f"{_busiest_invasion_seed(invasion_runs)['designed_reports']}, and "
            f"{sum(1 for run in invasion_runs if run['designed_reports'] == 0)} of "
            f"{len(invasion_runs)} seeds produce no designed reports at all. Pooled "
            "invasion precision is therefore a statement about the handful of lineages "
            "that happened to be attached to vessel streams, not about the typical "
            "lineage. The per-seed tables are the relevant visibility into that spread, "
            "and the same caveat applies to every grounded arm.",
            "",
            "The parent–child reproductive correlation is the Pearson correlation between "
            "a parent's offspring count and its child's offspring count over all "
            "parent-child pairs in a run, averaged over the runs where both series vary.",
            "",
            "The oracle row is a harness-local diagnostic upper bound only.",
            "Precision is computed from report and correct-report counts in the time series.",
            "A zero-report group is shown as 0% by the denominator convention, not interpreted as poor precision.",
        ]
    )
    return lines


def _markdown(results: dict[str, Any]) -> str:
    lines = _markdown_header(results)
    for spec in results["grounded_arms"]:
        lines.extend(_arm_section(results, spec))
    lines.extend(_cross_arm_section(results))
    lines.extend(_interpretation(results))
    lines.extend(_PROVENANCE_LINES)
    return "\n".join(lines) + "\n"


def _run_task(task: tuple[int, int, str, GroundedArm]) -> dict[str, Any]:
    seed, epochs, policy_arm, grounded = task
    return _arm_run(seed, epochs, policy_arm, grounded)


def _run_arms(
    seeds: Sequence[int],
    epochs: int,
    grounded_arms: Sequence[GroundedArm],
    jobs: int,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    tasks = [
        (seed, epochs, policy_arm, grounded)
        for grounded in grounded_arms
        for policy_arm in _POLICY_ARMS
        for seed in seeds
    ]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            completed = list(pool.map(_run_task, tasks))
    else:
        completed = [_run_task(task) for task in tasks]
    runs: dict[str, dict[str, list[dict[str, Any]]]] = {
        grounded.label: {policy_arm: [] for policy_arm in _POLICY_ARMS}
        for grounded in grounded_arms
    }
    for task, result in zip(tasks, completed, strict=True):
        _, _, policy_arm, grounded = task
        runs[grounded.label][policy_arm].append(result)
    return runs


def _resolve_within_docs(path: Path) -> Path:
    docs_dir = (_REPO_ROOT / "docs").resolve()
    resolved = (path if path.is_absolute() else Path.cwd() / path).resolve()
    if not resolved.is_relative_to(docs_dir):
        raise ValueError(f"Output path escapes allowed directory: {path}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _strip_series(results: dict[str, Any]) -> dict[str, Any]:
    """Drop per-run time series from the raw JSON; they live in the SimulationOutputs."""
    trimmed = dict(results)
    trimmed["arms"] = {
        label: {
            "grounded": arm["grounded"],
            "summary": arm["summary"],
            "runs": {
                policy_arm: [
                    {key: value for key, value in run.items() if key != "time_series"}
                    for run in policy_runs
                ]
                for policy_arm, policy_runs in arm["runs"].items()
            },
        }
        for label, arm in results["arms"].items()
    }
    return trimmed


def _write_simulation_outputs(results: dict[str, Any], directory: Path) -> list[Path]:
    written: list[Path] = []
    for spec in results["grounded_arms"]:
        grounded = GroundedArm(
            fraction=spec["fraction"],
            multiplier=spec["multiplier"],
            max_input_streams=spec["max_input_streams"],
        )
        arm = results["arms"][spec["label"]]
        for policy_arm, policy_runs in arm["runs"].items():
            output = _simulation_output(
                grounded,
                policy_arm,
                policy_runs,
                arm["summary"][policy_arm],
                results,
            )
            path = _resolve_within_docs(directory / f"{spec['label']}__{policy_arm}.json")
            output.write_json(path)
            written.append(path)
    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--seeds", type=int, nargs="+", default=_DEFAULT_SEEDS)
    parser.add_argument(
        "--grounded-arm",
        action="append",
        dest="grounded_arms",
        metavar="FRACTION[,MULTIPLIER[,MAX_INPUT_STREAMS]]",
        help=(
            "Grounded raw-stream access arm to measure; repeatable. "
            "Defaults to the legacy baseline 0.0,1.0,3."
        ),
    )
    parser.add_argument("--jobs", type=int, default=1)
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
    parser.add_argument(
        "--simulation-output-dir",
        type=Path,
        default=_REPO_ROOT / "docs" / "grounded_access",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    specs = [parse_grounded_arm(spec) for spec in (args.grounded_arms or ["0.0"])]
    runs = _run_arms(args.seeds, args.epochs, specs, max(args.jobs, 1))
    results: dict[str, Any] = {
        "seeds": args.seeds,
        "epochs": args.epochs,
        "max_stream_dim": _MAX_STREAM_DIM,
        "nulls": _null_measurements(args.seeds, args.epochs),
        "grounded_arms": [
            {
                "label": grounded.label,
                "fraction": grounded.fraction,
                "multiplier": grounded.multiplier,
                "max_input_streams": grounded.max_input_streams,
            }
            for grounded in specs
        ],
        "arms": {},
    }
    for grounded in specs:
        results["arms"][grounded.label] = {
            "grounded": {
                "fraction": grounded.fraction,
                "multiplier": grounded.multiplier,
                "max_input_streams": grounded.max_input_streams,
            },
            "runs": runs[grounded.label],
            "summary": _summarize_arms(runs[grounded.label]),
        }

    output_path = _resolve_within_docs(args.output)
    output_path.write_text(json.dumps(_strip_series(results), indent=2) + "\n", encoding="utf-8")
    report_path = _resolve_within_docs(args.report)
    report_path.write_text(_markdown(results), encoding="utf-8")
    written = _write_simulation_outputs(results, args.simulation_output_dir)
    print(f"Wrote {output_path}")
    print(f"Wrote {report_path}")
    for path in written:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
