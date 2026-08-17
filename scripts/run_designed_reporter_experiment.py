#!/usr/bin/env python3
"""Grade the Coral Key evidence-only reporter through the ordinary economy."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from tattletots.engine.config import GenePoolConfig, SimulationConfig
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
from tattletots.telemetry.payoff_ledger import PayoffLedger

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig
from coral_key.reporter_policy import CORAL_REPORTER_POLICY_NAME

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPORTER_FRACTION = 0.15
_MAX_STREAM_DIM = 48
_ORACLE_POLICY_NAME = "coral_oracle_diagnostic_upper_bound"
_POLICY_ARMS = ("ordinary", "all_designed_seed", "invasion", "oracle_upper_bound")
_DESIGNED_ARMS = ("ordinary", "all_designed_seed", "invasion")
_CLAUSE_ROWS = (
    ("Adult correct-report rate", "mean_correct_report_rate", "{:.2%}"),
    ("Clause 1 slope per generation", "mean_clause_one_slope", "{:+.4f}"),
    ("Generations observed", "mean_generations_observed", "{:.1f}"),
    ("Clause 2 parent–child offspring r", "mean_clause_two_correlation", "{:+.3f}"),
    ("Parent–child precision r", "mean_parent_child_precision_correlation", "{:+.3f}"),
    ("Reports per adult lifetime", "mean_reports_per_adult_lifetime", "{:.2f}"),
    ("Share of adults that never report", "mean_silent_adult_share", "{:.2%}"),
    ("Eligible-to-reproduce share", "mean_eligible_share", "{:.2%}"),
    ("Steps where the population cap binds", "mean_population_capped_step_share", "{:.2%}"),
    ("Mean offspring, ever-correct adults", "mean_correct_group_mean_offspring", "{:.3f}"),
    ("Mean offspring, never-correct adults", "mean_never_correct_group_mean_offspring", "{:.3f}"),
    ("Mean offspring, silent adults", "mean_silent_mean_offspring", "{:.3f}"),
)
_CLAUSE_COUNT_ROWS = (
    ("Seeds with a rising correct-report rate", "n_seeds_clause_one_rising"),
    ("Seeds with clause 2 r above 0.2", "n_seeds_clause_two_cleared"),
)
_SAFE_PATH_COMPONENT = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_RESULTS_JSON_NAME = "designed_reporter_measurement.json"
_REPORT_NAME = "designed_reporter_measurement.md"
_SIMULATION_OUTPUT_DIR = "grounded_access"
_STD_EPSILON = 1e-12
_CLAUSE_TWO_THRESHOLD = 0.2
_LEVER_CORRECT_REPORT_VALUE = 8.0
_LEVER_BREAK_EVEN_PRECISION = 0.2
_LEVER_ESCALATION_THRESHOLD_RANGE = (0.05, 0.3)
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
class PayoffLevers:
    """Config-gated payoff levers measured in TattleTots; off by default.

    When enabled, levers 1-4 are held at their measured settings and
    `correctness_weight` is the only quantity that varies between arms: it is the
    share of reproductive merit carried by rank in verified correctness rather than
    rank in reserve sufficiency. Nothing here subsidizes, protects or floors any
    agent; the population cap, the solvency requirement and the eligibility rule are
    untouched.
    """

    enabled: bool = False
    correctness_weight: float = 0.0

    @property
    def label(self) -> str:
        """Stable arm label used in output keys and file names."""
        if not self.enabled:
            return "levers_off"
        return f"levers_w{self.correctness_weight:g}".replace(".", "p")

    def config_overrides(self) -> dict[str, Any]:
        """`SimulationConfig` fields this arm sets, empty when the levers are off."""
        if not self.enabled:
            return {}
        return {
            "correct_report_attention_value": _LEVER_CORRECT_REPORT_VALUE,
            "reproduction_merit_ordering": True,
            "escalation_calibration_in_score_units": True,
            "false_alarm_break_even_precision": _LEVER_BREAK_EVEN_PRECISION,
            "reproduction_correctness_weight": self.correctness_weight,
        }

    def gene_pool(self) -> GenePoolConfig | None:
        """Starting gene pool for this arm; `None` keeps the engine defaults."""
        if not self.enabled:
            return None
        return GenePoolConfig(escalation_threshold_range=_LEVER_ESCALATION_THRESHOLD_RANGE)

    def as_dict(self) -> dict[str, Any]:
        """Serializable description of the arm, for the output artifacts."""
        record: dict[str, Any] = {"label": self.label, "enabled": self.enabled}
        record.update(self.config_overrides())
        if self.enabled:
            record["gene_pool_escalation_threshold_range"] = list(_LEVER_ESCALATION_THRESHOLD_RANGE)
        return record


_LEVERS_OFF = PayoffLevers()


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
    levers: PayoffLevers = _LEVERS_OFF,
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
        **levers.config_overrides(),
    )
    world = World(config=config, gene_pool=levers.gene_pool())
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
    if parent_counts.std() <= _STD_EPSILON or child_counts.std() <= _STD_EPSILON:
        return None
    return float(np.corrcoef(parent_counts, child_counts)[0, 1])


def _clause_metrics(ledger: PayoffLedger) -> dict[str, Any]:
    """The falsification-clause and reporting-economics block for one run."""
    coupling = ledger.coupling_summary()
    if not coupling.get("n_adults"):
        return {"n_adults": 0}
    gate = coupling["reproduction_gate"]
    return {
        "n_adults": int(coupling["n_adults"]),
        "correct_report_rate": _adult_correct_report_rate(ledger),
        "clause_one_slope": float(coupling["precision_generation_slope"]),
        "generations_observed": int(coupling["generations_observed"]),
        "clause_two_correlation": float(coupling["corr_parent_child_offspring"]),
        "n_parent_child_pairs": int(coupling["n_parent_child_pairs"]),
        "parent_child_precision_correlation": float(coupling["corr_parent_child_precision"]),
        "reports_per_adult_lifetime": float(coupling["mean_reports_per_adult"]),
        "silent_adult_share": float(coupling["silent_adult_share"]),
        "eligible_share": float(gate["eligible_share"]),
        "population_capped_step_share": float(gate["population_capped_step_share"]),
        "correct_group_mean_offspring": float(coupling["correct_group_mean_offspring"]),
        "never_correct_group_mean_offspring": float(coupling["never_correct_group_mean_offspring"]),
        "silent_mean_offspring": float(coupling["silent_mean_offspring"]),
    }


def _adult_correct_report_rate(ledger: PayoffLedger) -> float:
    """Pooled correct-report rate over every adult the run produced."""
    adults = [record for record in ledger.records if record.adult_steps > 0]
    reports = sum(record.reports_issued for record in adults)
    correct = sum(record.correct_reports for record in adults)
    return correct / reports if reports else 0.0


def _arm_run(
    seed: int,
    epochs: int,
    arm: str,
    grounded: GroundedArm,
    levers: PayoffLevers = _LEVERS_OFF,
) -> dict[str, Any]:
    adapter, world = _build_world(seed, epochs, arm, grounded, levers)
    ledger = PayoffLedger() if levers.enabled else None
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
        if ledger is not None:
            ledger.observe(world)
    if ledger is not None:
        ledger.finalize(world)

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
    shared: dict[str, Any] = {
        "seed": seed,
        "arm": arm,
        "grounded_arm": grounded.label,
        "ecology": ecology,
        "parent_child_reproductive_correlation": _parent_child_reproductive_correlation(world),
        "time_series": series,
    }
    if ledger is not None:
        shared["payoff_levers"] = levers.as_dict()
        shared["clause_metrics"] = _clause_metrics(ledger)
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


def _clause_summary(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Per-arm means and per-seed clause counts, or `None` when unmeasured."""
    blocks = [
        run["clause_metrics"]
        for run in runs
        if int(run.get("clause_metrics", {}).get("n_adults", 0)) > 0
    ]
    if not blocks:
        return None
    keys = [
        key
        for key, value in blocks[0].items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    summary: dict[str, Any] = {
        f"mean_{key}": float(np.mean([float(block[key]) for block in blocks])) for key in keys
    }
    slopes = [float(block["clause_one_slope"]) for block in blocks]
    correlations = [float(block["clause_two_correlation"]) for block in blocks]
    summary["n_runs"] = len(blocks)
    summary["n_seeds_clause_one_rising"] = sum(1 for slope in slopes if slope > 0.0)
    summary["n_seeds_clause_two_cleared"] = sum(
        1 for correlation in correlations if correlation > _CLAUSE_TWO_THRESHOLD
    )
    summary["clause_two_threshold"] = _CLAUSE_TWO_THRESHOLD
    return summary


def _summarize_arms(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for arm, runs in results.items():
        clause = _clause_summary(runs)
        if arm == "oracle_upper_bound":
            reports = sum(int(run["oracle_reports"]) for run in runs)
            correct = sum(int(run["oracle_correct_reports"]) for run in runs)
            summary[arm] = {
                "reports": reports,
                "correct_reports": correct,
                "precision": correct / max(reports, 1),
                "ecology": _ecology_summary(runs),
            }
            if clause is not None:
                summary[arm]["clause_metrics"] = clause
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
        if clause is not None:
            summary[arm]["clause_metrics"] = clause
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
    lines.extend(_lever_lines(results.get("payoff_levers", {})))
    return lines


def _lever_lines(levers: dict[str, Any]) -> list[str]:
    """Describe the payoff-lever arm this artifact was measured under."""
    if not levers.get("enabled"):
        return []
    return [
        "",
        f"Payoff levers (`{levers['label']}`), the only engine settings that differ from",
        "the default-off measurement:",
        "",
        *[
            f"- `{key}`: `{value}`"
            for key, value in levers.items()
            if key not in {"label", "enabled"}
        ],
    ]


def _arm_table(summary: dict[str, Any]) -> list[str]:
    lines = [
        "| Policy arm | Designed precision | Ordinary precision | Designed reports | Ordinary reports | Mean final designed share | AIS evidence | SAR evidence | Either |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in _DESIGNED_ARMS:
        if arm not in summary:
            continue
        item = summary[arm]
        label = "all-designed seed" if arm == "all_designed_seed" else arm
        lines.append(
            f"| {label} | {item['designed_precision']:.2%} | "
            f"{item['ordinary_precision']:.2%} | {item['designed_reports']} | "
            f"{item['ordinary_reports']} | {item['mean_final_designed_population_share']:.2%} | "
            f"{item['mean_ais_evidence_rate']:.2%} | {item['mean_sar_evidence_rate']:.2%} | "
            f"{item['mean_ais_or_sar_evidence_rate']:.2%} |"
        )
    oracle = summary.get("oracle_upper_bound")
    if oracle is not None:
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
    for arm in _POLICY_ARMS:
        if arm not in summary:
            continue
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


def _clause_table(summary: dict[str, Any]) -> list[str]:
    """Falsification-clause and reporting-economics rows, one column per policy arm."""
    measured = [arm for arm in _POLICY_ARMS if "clause_metrics" in summary.get(arm, {})]
    if not measured:
        return []
    lines = [
        "",
        "Falsification clauses and reporting economics (payoff levers on):",
        "",
        "| Quantity | " + " | ".join(f"`{arm}`" for arm in measured) + " |",
        "|---" * (len(measured) + 1) + "|",
    ]
    for label, key, fmt in _CLAUSE_ROWS:
        cells = " | ".join(fmt.format(summary[arm]["clause_metrics"][key]) for arm in measured)
        lines.append(f"| {label} | {cells} |")
    for label, key in _CLAUSE_COUNT_ROWS:
        cells = " | ".join(
            f"{summary[arm]['clause_metrics'][key]}/{summary[arm]['clause_metrics']['n_runs']}"
            for arm in measured
        )
        lines.append(f"| {label} | {cells} |")
    return lines


def _clause_per_seed_table(policy_arm: str, runs: list[dict[str, Any]]) -> list[str]:
    """Per-seed clause metrics for one policy arm."""
    measured = [run for run in runs if int(run.get("clause_metrics", {}).get("n_adults", 0)) > 0]
    if not measured:
        return []
    lines = [
        "",
        f"Per-seed clause metrics, `{policy_arm}` arm:",
        "",
        "| Seed | Correct-report rate | Clause 1 slope/generation | Generations | "
        "Clause 2 r | Reports/adult | Silent adults | Cap binds |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in measured:
        clause = run["clause_metrics"]
        lines.append(
            f"| {run['seed']} | {clause['correct_report_rate']:.2%} | "
            f"{clause['clause_one_slope']:+.4f} | {clause['generations_observed']} | "
            f"{clause['clause_two_correlation']:+.3f} | "
            f"{clause['reports_per_adult_lifetime']:.2f} | "
            f"{clause['silent_adult_share']:.2%} | "
            f"{clause['population_capped_step_share']:.2%} |"
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
    if "invasion" in arm["runs"]:
        lines.extend(_per_seed_table(arm["runs"]["invasion"]))
    lines.extend(_clause_table(arm["summary"]))
    for policy_arm, policy_runs in arm["runs"].items():
        lines.extend(_clause_per_seed_table(policy_arm, policy_runs))
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


def _has_designed_comparison(results: dict[str, Any]) -> bool:
    """True when every grounded arm carries both designed policy arms."""
    return all(
        {"invasion", "all_designed_seed"} <= set(arm["summary"]) for arm in results["arms"].values()
    )


def _markdown(results: dict[str, Any]) -> str:
    lines = _markdown_header(results)
    for spec in results["grounded_arms"]:
        lines.extend(_arm_section(results, spec))
    if _has_designed_comparison(results):
        lines.extend(_cross_arm_section(results))
        lines.extend(_interpretation(results))
        lines.extend(_PROVENANCE_LINES)
    return "\n".join(lines) + "\n"


def _run_task(task: tuple[int, int, str, GroundedArm, PayoffLevers]) -> dict[str, Any]:
    seed, epochs, policy_arm, grounded, levers = task
    return _arm_run(seed, epochs, policy_arm, grounded, levers)


def _run_arms(
    seeds: Sequence[int],
    epochs: int,
    grounded_arms: Sequence[GroundedArm],
    jobs: int,
    policy_arms: Sequence[str] = _POLICY_ARMS,
    levers: PayoffLevers = _LEVERS_OFF,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    tasks = [
        (seed, epochs, policy_arm, grounded, levers)
        for grounded in grounded_arms
        for policy_arm in policy_arms
        for seed in seeds
    ]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            completed = list(pool.map(_run_task, tasks))
    else:
        completed = [_run_task(task) for task in tasks]
    runs: dict[str, dict[str, list[dict[str, Any]]]] = {
        grounded.label: {policy_arm: [] for policy_arm in policy_arms} for grounded in grounded_arms
    }
    for task, result in zip(tasks, completed, strict=True):
        policy_arm, grounded = task[2], task[3]
        runs[grounded.label][policy_arm].append(result)
    return runs


def _safe_docs_path(*names: str) -> Path:
    """Build a path under `docs/` from name components validated against a whitelist."""
    resolved = _REPO_ROOT / "docs"
    for name in names:
        if _SAFE_PATH_COMPONENT.fullmatch(name) is None:
            raise ValueError(f"Unsafe output path component: {name!r}")
        resolved = resolved / name
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


def _write_simulation_outputs(results: dict[str, Any], parts: tuple[str, ...]) -> list[Path]:
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
            path = _safe_docs_path(*parts, f"{spec['label']}__{policy_arm}.json")
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
        "--policy-arm",
        action="append",
        dest="policy_arms",
        choices=_POLICY_ARMS,
        help="Policy arm to measure; repeatable. Defaults to all four arms.",
    )
    parser.add_argument(
        "--payoff-levers",
        action="store_true",
        help=(
            "Enable the measured TattleTots payoff levers (correct-report attention "
            "income, merit-ordered rationing at the cap, false-alarm pricing at "
            "reachable precision, score-unit escalation calibration). Off by default."
        ),
    )
    parser.add_argument(
        "--correctness-weight",
        type=float,
        nargs="+",
        default=[0.0],
        metavar="W",
        help=(
            "Response-gate weight(s) `reproduction_correctness_weight`; one full "
            "measurement is written per value. Requires --payoff-levers."
        ),
    )
    parser.add_argument(
        "--docs-dir",
        default=None,
        metavar="NAME",
        help="Write artifacts to `docs/NAME/` instead of `docs/`, for scratch runs.",
    )
    return parser.parse_args()


def _measure(
    seeds: Sequence[int],
    epochs: int,
    specs: Sequence[GroundedArm],
    jobs: int,
    policy_arms: Sequence[str],
    levers: PayoffLevers,
) -> dict[str, Any]:
    """Run every requested arm and assemble the results record."""
    runs = _run_arms(seeds, epochs, specs, jobs, policy_arms, levers)
    results: dict[str, Any] = {
        "seeds": list(seeds),
        "epochs": epochs,
        "max_stream_dim": _MAX_STREAM_DIM,
        "policy_arms": list(policy_arms),
        "payoff_levers": levers.as_dict(),
        "nulls": _null_measurements(seeds, epochs),
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
    return results


def _artifact_names(levers: PayoffLevers) -> tuple[str, str, str]:
    """Raw-JSON, Markdown and `SimulationOutput` directory names for one lever arm."""
    if not levers.enabled:
        return _RESULTS_JSON_NAME, _REPORT_NAME, _SIMULATION_OUTPUT_DIR
    return (
        f"designed_reporter_measurement__{levers.label}.json",
        f"designed_reporter_measurement__{levers.label}.md",
        f"{_SIMULATION_OUTPUT_DIR}__{levers.label}",
    )


def _write_artifacts(
    results: dict[str, Any], levers: PayoffLevers, docs_dir: str | None
) -> list[Path]:
    """Write the raw JSON, the Markdown report and the per-arm `SimulationOutput`s."""
    prefix: tuple[str, ...] = () if docs_dir is None else (docs_dir,)
    json_name, report_name, output_dir = _artifact_names(levers)
    json_path = _safe_docs_path(*prefix, json_name)
    json_path.write_text(json.dumps(_strip_series(results), indent=2) + "\n", encoding="utf-8")
    report_path = _safe_docs_path(*prefix, report_name)
    report_path.write_text(_markdown(results), encoding="utf-8")
    return [
        json_path,
        report_path,
        *_write_simulation_outputs(results, (*prefix, output_dir)),
    ]


def main() -> int:
    args = _parse_args()
    epochs = int(args.epochs)
    seeds = [int(seed) for seed in args.seeds]
    jobs = max(int(args.jobs), 1)
    policy_arms = list(args.policy_arms or _POLICY_ARMS)
    specs = [parse_grounded_arm(str(spec)) for spec in (args.grounded_arms or ["0.0"])]
    weights = [float(weight) for weight in args.correctness_weight]
    if not args.payoff_levers and weights != [0.0]:
        raise SystemExit("--correctness-weight requires --payoff-levers")
    lever_arms = (
        [PayoffLevers(enabled=True, correctness_weight=weight) for weight in weights]
        if args.payoff_levers
        else [PayoffLevers()]
    )
    for levers in lever_arms:
        results = _measure(seeds, epochs, specs, jobs, policy_arms, levers)
        for path in _write_artifacts(results, levers, args.docs_dir):
            print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
