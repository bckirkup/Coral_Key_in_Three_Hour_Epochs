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
        with pytest.raises(ValueError):
            _experiment().parse_grounded_arm(spec)


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


@pytest.mark.smoke
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
