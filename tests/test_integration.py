"""Integration tests: run TattleTots engine with the ReefWatch adapter.

These verify that the DomainAdapter interface contract is fully satisfied
and that the ecology can evolve on Coral Key sensor streams.
"""

from __future__ import annotations

import numpy as np
import pytest

from coral_key.adapter import ReefWatchAdapter
from coral_key.config import ScenarioConfig


@pytest.mark.smoke
class TestTattleTotsIntegration:
    """Verify CK adapter works end-to-end with the TattleTots engine."""

    def test_adapter_runs_with_engine(self) -> None:
        """Full integration: TattleTots ecology evolves on ReefWatch data."""
        from tattletots.engine.config import SimulationConfig
        from tattletots.engine.world import World

        adapter = ReefWatchAdapter()
        config = SimulationConfig(initial_population=10, max_steps=50, seed=42)
        world = World(config=config)

        for stream in adapter.get_streams():
            world.add_stream(stream)
        for user in adapter.get_users():
            world.add_user(user)
        world.seed_population()

        for step in range(50):
            adapter.step(step)
            world.set_event_state(adapter.get_active_locations(step))
            world.step()

        # Ecology should survive 50 steps
        assert world.living_population > 0
        # Streams should include both domain + agent-created
        assert len(world.streams) >= len(adapter.get_streams())

    def test_agents_specialize_on_domain_streams(self) -> None:
        """Agents should attach to CK sensor streams and compress them."""
        from tattletots.engine.config import SimulationConfig
        from tattletots.engine.world import World

        adapter = ReefWatchAdapter()
        config = SimulationConfig(initial_population=15, max_steps=100, seed=123)
        world = World(config=config)

        for stream in adapter.get_streams():
            world.add_stream(stream)
        for user in adapter.get_users():
            world.add_user(user)
        world.seed_population()

        for step in range(100):
            adapter.step(step)
            world.set_event_state(adapter.get_active_locations(step))
            world.step()

        # After 100 steps, at least some agents should have input streams
        agents_with_inputs = sum(
            1 for a in world.agents.values() if a.is_alive and len(a.state.input_stream_ids) > 0
        )
        assert agents_with_inputs > 0

    def test_ground_truth_triggers_during_iuu(self) -> None:
        """Ground truth should be True when IUU is active."""
        from coral_key.config import AdversaryConfig, FleetConfig, OceanConfig

        config = ScenarioConfig(
            ocean=OceanConfig(n_zones_x=4, n_zones_y=4),
            fleet=FleetConfig(n_legal_vessels=3, n_gaming_vessels=1, n_iuu_vessels=3),
            adversary=AdversaryConfig(ais_disable_probability=0.9),
            total_epochs=50,
            seed=42,
        )
        adapter = ReefWatchAdapter(config=config)
        gt_true_count = 0
        for step in range(50):
            adapter.step(step)
            if adapter.get_ground_truth(step):
                gt_true_count += 1

        # With 3 IUU vessels, ground truth should be active in many epochs
        assert gt_true_count > 0

    def test_cost_model_produces_sensible_output(self) -> None:
        """Domain costs should be non-negative and proportional to activity."""
        adapter = ReefWatchAdapter()
        costs_low = adapter.compute_costs(
            n_escalations=2, n_correct=1, n_false_alarms=1, n_missed=0
        )
        costs_high = adapter.compute_costs(
            n_escalations=20, n_correct=10, n_false_alarms=10, n_missed=5
        )
        # All costs non-negative
        for v in costs_low.values():
            assert v >= 0
        for v in costs_high.values():
            assert v >= 0
        # More activity → higher total cost
        total_low = sum(costs_low.values())
        total_high = sum(costs_high.values())
        assert total_high > total_low

    def test_stream_dimensions_match_domain(self) -> None:
        """Verify all domain streams have consistent dimensionality."""
        adapter = ReefWatchAdapter()
        streams = adapter.get_streams()
        assert len(streams) == 6  # AIS, SAR, Catch, Ocean, eDNA, EM

        # Run one step so streams have data
        adapter.step(0)
        for s in streams:
            assert s.current_data is not None
            assert len(s.current_data) == s.dimensionality

    def test_relevance_scoring_differentiates_users(self) -> None:
        """Different users should get different relevance scores for same signal."""
        adapter = ReefWatchAdapter()
        users = adapter.get_users()
        streams = adapter.get_streams()
        total_dim = sum(s.dimensionality for s in streams)

        signal = np.ones(total_dim)
        scores = [adapter.score_relevance(signal, u) for u in users]
        # At least two users should differ in score
        assert len(set(f"{s:.4f}" for s in scores)) > 1
