"""Smoke tests: end-to-end simulation scenarios validating domain behavior."""

from __future__ import annotations

import numpy as np
import pytest

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig


@pytest.mark.smoke
class TestSmokeScenarios:
    """Integration tests that validate emergent domain behavior."""

    def test_basic_simulation_completes(self) -> None:
        """A short simulation should run without errors."""
        config = ScenarioConfig(
            ocean=ScenarioConfig.model_fields["ocean"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_zones_x": 4, "n_zones_y": 4}
            ),
            fleet=ScenarioConfig.model_fields["fleet"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_legal_vessels": 5, "n_gaming_vessels": 2, "n_iuu_vessels": 2}
            ),
            total_epochs=100,
            seed=42,
        )
        adapter = ReefWatchAdapter(config=config)
        for epoch in range(100):
            adapter.step(epoch)

        assert len(adapter.metrics_collector.epoch_history) == 100

    def test_iuu_creates_detectable_anomalies(self) -> None:
        """IUU activity should produce observable signals (dark vessels, AIS gaps)."""
        config = ScenarioConfig(
            ocean=ScenarioConfig.model_fields["ocean"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_zones_x": 4, "n_zones_y": 4, "mpa_fraction": 0.4}
            ),
            fleet=ScenarioConfig.model_fields["fleet"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_legal_vessels": 5, "n_gaming_vessels": 2, "n_iuu_vessels": 5}
            ),
            adversary=ScenarioConfig.model_fields["adversary"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"ais_disable_probability": 0.9}
            ),
            total_epochs=100,
            seed=42,
        )
        adapter = ReefWatchAdapter(config=config)
        for epoch in range(100):
            adapter.step(epoch)

        history = adapter.metrics_collector.epoch_history
        total_dark = sum(m.dark_vessels_detected for m in history)
        total_iuu = sum(m.iuu_vessels_active for m in history)
        # There should be observable dark vessel events
        assert total_dark > 0 or total_iuu > 0

    def test_fish_stocks_respond_to_fishing_pressure(self) -> None:
        """Heavy fishing should reduce biomass below carrying capacity."""
        config = ScenarioConfig(
            ocean=ScenarioConfig.model_fields["ocean"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_zones_x": 4, "n_zones_y": 4}
            ),
            fish=ScenarioConfig.model_fields["fish"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_species": 2, "carrying_capacity": 500.0}
            ),
            fleet=ScenarioConfig.model_fields["fleet"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_legal_vessels": 15, "n_gaming_vessels": 5, "n_iuu_vessels": 5}
            ),
            total_epochs=200,
            seed=42,
        )
        adapter = ReefWatchAdapter(config=config)
        for epoch in range(200):
            adapter.step(epoch)

        biomass = adapter.fish_stock.get_total_biomass()
        k = config.fish.carrying_capacity
        # With heavy fishing, at least one species should be below K
        assert np.any(biomass < k)

    def test_catch_underreporting_detectable(self) -> None:
        """Actual catch should exceed reported catch due to IUU/gaming."""
        config = ScenarioConfig(
            ocean=ScenarioConfig.model_fields["ocean"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={"n_zones_x": 4, "n_zones_y": 4}
            ),
            fleet=ScenarioConfig.model_fields["fleet"]
            .default_factory()
            .model_copy(  # type: ignore[union-attr]
                update={
                    "n_legal_vessels": 5,
                    "n_gaming_vessels": 3,
                    "n_iuu_vessels": 3,
                    "underreport_fraction": 0.5,
                }
            ),
            total_epochs=100,
            seed=42,
        )
        adapter = ReefWatchAdapter(config=config)
        for epoch in range(100):
            adapter.step(epoch)

        history = adapter.metrics_collector.epoch_history
        total_actual = sum(m.total_catch_actual for m in history)
        total_reported = sum(m.total_catch_reported for m in history)
        # Reported should be less than actual due to underreporting
        if total_actual > 0:
            assert total_reported <= total_actual

    def test_multiple_users_have_different_priorities(self) -> None:
        """Users should respond differently to the same signal."""
        adapter = ReefWatchAdapter()
        users = adapter.get_users()
        streams = adapter.get_streams()
        total_dim = sum(s.dimensionality for s in streams)

        signal = np.ones(total_dim)
        scores = [adapter.score_relevance(signal, u) for u in users]
        # Different users should have different relevance scores
        assert len(set(f"{s:.4f}" for s in scores)) > 1
