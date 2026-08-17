"""Tests for the designed-reporter measurement harness in `scripts/`."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from tattletots.engine.config import SimulationConfig

_GROUNDED_KNOBS = (
    "grounded_input_fraction",
    "grounded_attractiveness_multiplier",
    "max_input_streams",
)

requires_grounded_knobs = pytest.mark.skipif(
    not all(knob in SimulationConfig.model_fields for knob in _GROUNDED_KNOBS),
    reason="installed tattletots build has no grounded raw-stream access knobs",
)

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "run_designed_reporter_experiment.py"
)


@lru_cache(maxsize=1)
def _experiment() -> ModuleType:
    """Load the measurement script as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("designed_reporter_experiment", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class _FakeState:
    parent_ids: list[str] = field(default_factory=list)


@dataclass
class _FakeAgent:
    id: str
    state: _FakeState


@dataclass
class _FakeWorld:
    agents: dict[str, _FakeAgent]


def _world_from_pedigree(pedigree: dict[str, list[str]]) -> Any:
    agents = {
        agent_id: _FakeAgent(id=agent_id, state=_FakeState(parent_ids=list(parents)))
        for agent_id, parents in pedigree.items()
    }
    return _FakeWorld(agents=agents)


class TestGroundedArmParsing:
    def test_fraction_only_defaults_to_legacy_behavior(self) -> None:
        arm = _experiment().parse_grounded_arm("0.0")
        assert arm.fraction == pytest.approx(0.0)
        assert arm.multiplier == pytest.approx(1.0)
        assert arm.max_input_streams == 3

    def test_fraction_multiplier_and_slots_are_read_in_order(self) -> None:
        arm = _experiment().parse_grounded_arm("0.67, 3.0, 4")
        assert arm.fraction == pytest.approx(0.67)
        assert arm.multiplier == pytest.approx(3.0)
        assert arm.max_input_streams == 4

    def test_distinct_specifications_get_distinct_labels(self) -> None:
        specs = ["0.0", "0.34", "0.67", "0.0,3.0", "0.0,1.0,4"]
        labels = {_experiment().parse_grounded_arm(spec).label for spec in specs}
        assert len(labels) == len(specs)

    def test_labels_are_filename_safe(self) -> None:
        label = _experiment().parse_grounded_arm("0.34,2.5").label
        assert "." not in label
        assert "/" not in label

    @pytest.mark.parametrize("spec", ["", "0.1,1.0,3,9", "abc"])
    def test_malformed_specifications_are_rejected(self, spec: str) -> None:
        parse = _experiment().parse_grounded_arm
        with pytest.raises(ValueError):
            parse(spec)


class TestSafeDocsPath:
    def test_valid_names_resolve_under_docs(self) -> None:
        path = _experiment()._safe_docs_path("grounded_access", "arm.json")
        assert path.parent.name == "grounded_access"
        assert path.parent.parent.name == "docs"
        assert path.name == "arm.json"

    @pytest.mark.parametrize("name", ["..", "../secrets", "/etc/passwd", "a/b", "", ".hidden"])
    def test_traversal_and_separators_are_rejected(self, name: str) -> None:
        safe_docs_path = _experiment()._safe_docs_path
        with pytest.raises(ValueError):
            safe_docs_path(name)


@requires_grounded_knobs
class TestGroundedKnobsReachTheEngine:
    @pytest.mark.parametrize(
        ("fraction", "multiplier"),
        [(0.0, 1.0), (0.34, 1.0), (0.67, 2.0)],
    )
    def test_config_carries_the_arm_values(self, fraction: float, multiplier: float) -> None:
        module = _experiment()
        arm = module.GroundedArm(fraction=fraction, multiplier=multiplier, max_input_streams=3)
        _adapter, world = module._build_world(42, 5, "invasion", arm)
        assert world.config.grounded_input_fraction == pytest.approx(fraction)
        assert world.config.grounded_attractiveness_multiplier == pytest.approx(multiplier)
        assert world.config.max_input_streams == 3

    def test_input_slot_count_is_configurable(self) -> None:
        module = _experiment()
        arm = module.GroundedArm(max_input_streams=5)
        _adapter, world = module._build_world(42, 5, "invasion", arm)
        assert world.config.max_input_streams == 5


class TestParentChildReproductiveCorrelation:
    def test_too_few_pairs_is_undefined(self) -> None:
        world = _world_from_pedigree({"a": [], "b": ["a"], "c": ["a"]})
        assert _experiment()._parent_child_reproductive_correlation(world) is None

    def test_uniform_offspring_counts_are_undefined(self) -> None:
        pedigree: dict[str, list[str]] = {"root": []}
        for index in range(6):
            pedigree[f"child{index}"] = ["root"]
        assert (
            _experiment()._parent_child_reproductive_correlation(_world_from_pedigree(pedigree))
            is None
        )

    def test_high_and_low_fecundity_lineages_give_a_positive_correlation(self) -> None:
        pedigree: dict[str, list[str]] = {"prolific": [], "sparse": []}
        for index in range(4):
            pedigree[f"prolific_child{index}"] = ["prolific"]
            for grandchild in range(4):
                pedigree[f"prolific_grandchild{index}_{grandchild}"] = [f"prolific_child{index}"]
        pedigree["sparse_child"] = ["sparse"]
        correlation = _experiment()._parent_child_reproductive_correlation(
            _world_from_pedigree(pedigree)
        )
        assert correlation is not None
        assert correlation > 0.0

    def test_correlation_stays_in_the_pearson_range(self) -> None:
        pedigree: dict[str, list[str]] = {"a": [], "b": ["a"], "c": ["a"], "d": ["b"], "e": ["b"]}
        pedigree["f"] = ["c"]
        correlation = _experiment()._parent_child_reproductive_correlation(
            _world_from_pedigree(pedigree)
        )
        assert correlation is not None
        assert -1.0 <= correlation <= 1.0


class TestPooledTimeSeries:
    def _runs(self) -> list[dict[str, Any]]:
        return [
            {
                "time_series": {
                    "population": [10, 12],
                    "reports_issued": [1, 2],
                    "grounded_yield_share": [0.2, 0.4],
                }
            },
            {
                "time_series": {
                    "population": [20, 30],
                    "reports_issued": [3, 4],
                    "grounded_yield_share": [0.4, 0.8],
                }
            },
        ]

    def test_counts_are_summed_across_seeds(self) -> None:
        pooled = _experiment()._pooled_time_series(self._runs())
        assert pooled["population"] == [30, 42]
        assert pooled["reports_issued"] == [4, 6]

    def test_rates_are_averaged_across_seeds(self) -> None:
        pooled = _experiment()._pooled_time_series(self._runs())
        assert pooled["grounded_yield_share"] == pytest.approx([0.3, 0.6])

    def test_pooling_truncates_to_the_shortest_run(self) -> None:
        runs = self._runs()
        runs[1]["time_series"] = {key: value[:1] for key, value in runs[1]["time_series"].items()}
        pooled = _experiment()._pooled_time_series(runs)
        assert len(pooled["population"]) == 1


class TestEcologySummary:
    def _runs(self, shares: list[float], correlations: list[float | None]) -> list[dict[str, Any]]:
        return [
            {
                "ecology": {
                    "attention_solvent_fraction": 0.5,
                    "mean_attention_carrying_capacity": 2.0,
                    "grounded_yield_share": share,
                    "effective_grounded_yield_share": share,
                    "max_trophic_depth": 1.0,
                    "final_population": 10,
                    "total_births": 3,
                    "total_deaths": 2,
                    "initiation_is_degenerate": share < 0.5,
                    "initiation_degeneracy_reasons": [],
                },
                "parent_child_reproductive_correlation": correlation,
            }
            for share, correlation in zip(shares, correlations, strict=True)
        ]

    def test_means_track_the_inputs(self) -> None:
        summary = _experiment()._ecology_summary(self._runs([0.2, 0.8], [0.1, 0.3]))
        assert summary["mean_grounded_yield_share"] == pytest.approx(0.5)
        assert summary["mean_parent_child_reproductive_correlation"] == pytest.approx(0.2)
        assert summary["total_births"] == 6

    def test_undefined_correlations_are_excluded_not_zeroed(self) -> None:
        summary = _experiment()._ecology_summary(self._runs([0.6, 0.6], [0.4, None]))
        assert summary["mean_parent_child_reproductive_correlation"] == pytest.approx(0.4)
        assert summary["n_runs_with_reproductive_correlation"] == 1

    def test_all_undefined_correlations_stay_undefined(self) -> None:
        summary = _experiment()._ecology_summary(self._runs([0.6, 0.6], [None, None]))
        assert summary["mean_parent_child_reproductive_correlation"] is None

    def test_degenerate_runs_are_counted(self) -> None:
        summary = _experiment()._ecology_summary(self._runs([0.2, 0.8], [0.1, 0.1]))
        assert summary["n_degenerate_runs"] == 1


_LEVER_KNOBS = (
    "correct_report_attention_value",
    "reproduction_merit_ordering",
    "escalation_calibration_in_score_units",
    "false_alarm_break_even_precision",
    "reproduction_correctness_weight",
)

requires_payoff_levers = pytest.mark.skipif(
    not all(knob in SimulationConfig.model_fields for knob in _LEVER_KNOBS),
    reason="installed tattletots build has no payoff levers",
)


def _clause_run(slope: float, correlation: float) -> dict[str, Any]:
    return {
        "clause_metrics": {
            "n_adults": 12,
            "correct_report_rate": 0.2,
            "clause_one_slope": slope,
            "generations_observed": 5,
            "clause_two_correlation": correlation,
            "n_parent_child_pairs": 40,
            "parent_child_precision_correlation": 0.1,
            "reports_per_adult_lifetime": 4.0,
            "silent_adult_share": 0.1,
            "eligible_share": 0.6,
            "population_capped_step_share": 0.3,
            "correct_group_mean_offspring": 1.2,
            "never_correct_group_mean_offspring": 1.1,
            "silent_mean_offspring": 0.8,
        }
    }


class TestPayoffLevers:
    def test_levers_are_off_by_default(self) -> None:
        levers = _experiment().PayoffLevers()
        assert levers.config_overrides() == {}
        assert levers.gene_pool() is None
        assert levers.label == "levers_off"

    def test_only_the_correctness_weight_varies_between_lever_arms(self) -> None:
        module = _experiment()
        arms = [
            module.PayoffLevers(enabled=True, correctness_weight=weight)
            for weight in (0.0, 0.5, 1.0)
        ]
        overrides = [dict(arm.config_overrides()) for arm in arms]
        weights = [override.pop("reproduction_correctness_weight") for override in overrides]
        assert weights == [0.0, 0.5, 1.0]
        assert overrides[0] == overrides[1] == overrides[2]

    def test_lever_arms_get_distinct_filename_safe_labels(self) -> None:
        module = _experiment()
        labels = [
            module.PayoffLevers(enabled=True, correctness_weight=weight).label
            for weight in (0.0, 0.25, 1.0)
        ]
        assert len(set(labels)) == 3
        assert all("." not in label for label in labels)
        assert all("/" not in label for label in labels)

    def test_artifact_names_separate_lever_arms_from_the_committed_run(self) -> None:
        module = _experiment()
        default = module._artifact_names(module.PayoffLevers())
        treatment = module._artifact_names(
            module.PayoffLevers(enabled=True, correctness_weight=1.0)
        )
        control = module._artifact_names(module.PayoffLevers(enabled=True, correctness_weight=0.0))
        assert default == (
            module._RESULTS_JSON_NAME,
            module._REPORT_NAME,
            module._SIMULATION_OUTPUT_DIR,
        )
        assert len({default, treatment, control}) == 3


@requires_payoff_levers
class TestPayoffLeversReachTheEngine:
    def test_levers_off_leaves_the_engine_defaults(self) -> None:
        module = _experiment()
        _adapter, world = module._build_world(42, 5, "ordinary", module.GroundedArm())
        defaults = SimulationConfig()
        for knob in _LEVER_KNOBS:
            assert getattr(world.config, knob) == getattr(defaults, knob)
        assert world.gene_pool is None

    @pytest.mark.parametrize("weight", [0.0, 0.5, 1.0])
    def test_enabled_levers_set_exactly_the_measured_values(self, weight: float) -> None:
        module = _experiment()
        levers = module.PayoffLevers(enabled=True, correctness_weight=weight)
        _adapter, world = module._build_world(42, 5, "ordinary", module.GroundedArm(), levers)
        assert world.config.correct_report_attention_value == pytest.approx(8.0)
        assert world.config.reproduction_merit_ordering is True
        assert world.config.escalation_calibration_in_score_units is True
        assert world.config.false_alarm_break_even_precision == pytest.approx(0.2)
        assert world.config.reproduction_correctness_weight == pytest.approx(weight)
        assert world.gene_pool is not None
        assert world.gene_pool.escalation_threshold_range == (0.05, 0.3)


class TestClauseSummary:
    def test_unmeasured_runs_have_no_clause_block(self) -> None:
        assert _experiment()._clause_summary([{"seed": 1}]) is None

    def test_rising_and_cleared_seed_counts_track_the_per_seed_values(self) -> None:
        runs = [
            _clause_run(0.01, 0.05),
            _clause_run(0.002, 0.35),
            _clause_run(-0.004, 0.9),
            _clause_run(0.0, 0.2),
        ]
        summary = _experiment()._clause_summary(runs)
        assert summary is not None
        assert summary["n_runs"] == 4
        assert summary["n_seeds_clause_one_rising"] == 2
        assert summary["n_seeds_clause_two_cleared"] == 2

    def test_means_average_the_per_seed_values(self) -> None:
        summary = _experiment()._clause_summary([_clause_run(0.02, 0.1), _clause_run(0.0, 0.3)])
        assert summary is not None
        assert summary["mean_clause_one_slope"] == pytest.approx(0.01)
        assert summary["mean_clause_two_correlation"] == pytest.approx(0.2)


@pytest.mark.smoke
@requires_payoff_levers
class TestClauseMetricsFromARun:
    def test_measured_clause_metrics_stay_in_range(self) -> None:
        module = _experiment()
        levers = module.PayoffLevers(enabled=True, correctness_weight=1.0)
        run = module._arm_run(42, 20, "ordinary", module.GroundedArm(fraction=0.67), levers)
        clause = run["clause_metrics"]
        assert clause["n_adults"] > 0
        assert 0.0 <= clause["correct_report_rate"] <= 1.0
        assert 0.0 <= clause["silent_adult_share"] <= 1.0
        assert 0.0 <= clause["population_capped_step_share"] <= 1.0
        assert -1.0 <= clause["clause_two_correlation"] <= 1.0
        assert run["payoff_levers"]["reproduction_correctness_weight"] == pytest.approx(1.0)

    def test_levers_off_runs_carry_no_clause_block(self) -> None:
        module = _experiment()
        run = module._arm_run(42, 20, "ordinary", module.GroundedArm(fraction=0.67))
        assert "clause_metrics" not in run


@pytest.mark.smoke
@requires_grounded_knobs
class TestGroundedAccessChangesEvidenceExposure:
    def test_reserved_grounded_slots_raise_the_evidence_rate(self) -> None:
        module = _experiment()
        baseline = module._arm_run(42, 12, "invasion", module.GroundedArm(fraction=0.0))
        grounded = module._arm_run(42, 12, "invasion", module.GroundedArm(fraction=0.67))
        baseline_rate = baseline["evidence_rates"]["ais_or_sar_evidence_rate"]
        grounded_rate = grounded["evidence_rates"]["ais_or_sar_evidence_rate"]
        assert grounded_rate > baseline_rate

    def test_evidence_rates_stay_probabilities(self) -> None:
        module = _experiment()
        run = module._arm_run(42, 12, "invasion", module.GroundedArm(fraction=0.34))
        for key in ("ais_evidence_rate", "sar_evidence_rate", "ais_or_sar_evidence_rate"):
            assert 0.0 <= run["evidence_rates"][key] <= 1.0
