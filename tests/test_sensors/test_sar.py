"""Tests for SAR satellite stream."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel, VesselPosition, VesselType
from coral_key.ocean.grid import OceanGrid
from coral_key.sensors.sar import SARStream


class TestSARStream:
    def test_dimensionality(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        sar = SARStream(grid=grid, rng=rng)
        assert sar.dimensionality == 16

    def test_no_observation_off_cycle(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        sar = SARStream(grid=grid, revisit_interval=8, rng=rng)
        vessels = [Vessel(vessel_type=VesselType.LEGAL, at_port=False)]
        obs = sar.observe(vessels, epoch=3)
        assert np.all(obs == -1.0)

    def test_detection_on_revisit(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        sar = SARStream(grid=grid, revisit_interval=8, detection_probability=1.0, rng=rng)
        vessel = Vessel(
            vessel_type=VesselType.IUU,
            position=VesselPosition(zone_x=2, zone_y=2),
            at_port=False,
        )
        obs = sar.observe([vessel], epoch=8)
        # Should detect vessel in zone (2, 2) = index 10
        assert obs[10] >= 1.0

    def test_cross_reference_finds_dark_vessels(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        sar = SARStream(grid=grid, rng=rng)

        # SAR sees a vessel in zone 5 but AIS shows nothing there
        sar_obs = np.zeros(16)
        sar_obs[5] = 1.0

        # Empty AIS (all zeros = no vessels reporting)
        ais_obs = np.zeros(10)  # 2 vessels * 5

        discrepancies = sar.cross_reference_ais(sar_obs, ais_obs, n_vessels=2)
        assert discrepancies >= 1
