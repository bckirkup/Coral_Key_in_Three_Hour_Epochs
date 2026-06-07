"""Tests for oceanographic state model."""

from __future__ import annotations

import numpy as np

from coral_key.ocean.grid import OceanGrid
from coral_key.ocean.oceanography import Oceanography


class TestOceanography:
    def test_compute_state_returns_correct_shape(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        ocean = Oceanography(grid=grid, rng=rng)
        state = ocean.compute_state(epoch=0)

        assert state.n_zones == 16
        assert len(state.sst) == 16
        assert len(state.chlorophyll) == 16
        assert len(state.current_u) == 16
        assert len(state.current_v) == 16

    def test_seasonal_variation(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        ocean = Oceanography(grid=grid, sst_amplitude=3.0, rng=rng)

        # Summer vs winter (half year apart = ~1460 epochs at 3h)
        state_summer = ocean.compute_state(epoch=730)
        state_winter = ocean.compute_state(epoch=2190)

        # Mean SST should differ between seasons
        assert abs(state_summer.sst.mean() - state_winter.sst.mean()) > 1.0

    def test_chlorophyll_always_positive(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        ocean = Oceanography(grid=grid, rng=rng)

        for epoch in range(0, 100, 10):
            state = ocean.compute_state(epoch=epoch)
            assert np.all(state.chlorophyll > 0)

    def test_habitat_suitability_in_range(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        ocean = Oceanography(grid=grid, rng=rng)
        state = ocean.compute_state(epoch=50)
        suitability = ocean.compute_fish_habitat_suitability(state)

        assert suitability.shape == (16,)
        assert np.all(suitability >= 0.0)
        assert np.all(suitability <= 1.0)
