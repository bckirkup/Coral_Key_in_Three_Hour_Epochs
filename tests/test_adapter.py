"""Tests for the main ReefWatch domain adapter."""

from __future__ import annotations

import numpy as np

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig


class TestReefWatchAdapter:
    def test_construction(self) -> None:
        adapter = ReefWatchAdapter()
        assert adapter is not None

    def test_get_streams(self) -> None:
        adapter = ReefWatchAdapter()
        streams = adapter.get_streams()
        assert len(streams) == 6
        labels = {s.label for s in streams}
        assert "ais_vms" in labels
        assert "sar_satellite" in labels
        assert "catch_reports" in labels
        assert "oceanographic" in labels
        assert "edna_sampling" in labels
        assert "electronic_monitoring" in labels

    def test_get_users(self) -> None:
        adapter = ReefWatchAdapter()
        users = adapter.get_users()
        assert len(users) == 3
        names = {u.name for u in users}
        assert "Patrol Commander" in names
        assert "Stock Assessment Scientist" in names
        assert "Policy Director" in names

    def test_step_updates_streams(self) -> None:
        config = ScenarioConfig(
            ocean=ScenarioConfig.model_fields["ocean"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_zones_x": 4, "n_zones_y": 4}
            ),
            fleet=ScenarioConfig.model_fields["fleet"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_legal_vessels": 3, "n_gaming_vessels": 1, "n_iuu_vessels": 1}
            ),
            seed=123,
        )
        adapter = ReefWatchAdapter(config=config)
        adapter.step(0)

        # All streams should have non-empty data
        for stream in adapter.get_streams():
            assert stream.current_data.shape[-1] == stream.dimensionality

    def test_ground_truth_returns_bool(self) -> None:
        adapter = ReefWatchAdapter()
        result = adapter.get_ground_truth(0)
        assert isinstance(result, bool)

    def test_score_relevance(self) -> None:
        adapter = ReefWatchAdapter()
        users = adapter.get_users()
        signal = np.ones(adapter.get_streams()[0].dimensionality)
        # Should not crash even with mismatched dims
        score = adapter.score_relevance(signal, users[0])
        assert isinstance(score, float)

    def test_compute_costs(self) -> None:
        adapter = ReefWatchAdapter()
        costs = adapter.compute_costs(
            n_escalations=5,
            n_correct=3,
            n_false_alarms=2,
            n_missed=1,
        )
        assert "surveillance_cost" in costs
        assert "response_cost" in costs
        assert "damage_cost" in costs
        assert costs["surveillance_cost"] > 0
        assert costs["damage_cost"] > 0

    def test_multi_epoch_simulation(self) -> None:
        config = ScenarioConfig(
            ocean=ScenarioConfig.model_fields["ocean"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_zones_x": 4, "n_zones_y": 4}
            ),
            fleet=ScenarioConfig.model_fields["fleet"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_legal_vessels": 3, "n_gaming_vessels": 1, "n_iuu_vessels": 1}
            ),
            total_epochs=20,
            seed=42,
        )
        adapter = ReefWatchAdapter(config=config)

        for epoch in range(20):
            adapter.step(epoch)

        # Should have metrics for all epochs
        assert len(adapter.metrics_collector.epoch_history) == 20

    def test_to_from_config_roundtrip(self) -> None:
        config = ScenarioConfig(total_epochs=100, seed=99)
        adapter = ReefWatchAdapter(config=config)
        config_dict = adapter.to_config()
        adapter2 = ReefWatchAdapter.from_config(config_dict)
        assert adapter2._config.total_epochs == 100
        assert adapter2._config.seed == 99
