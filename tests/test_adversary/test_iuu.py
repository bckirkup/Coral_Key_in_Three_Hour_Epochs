"""Tests for IUU detection oracle."""

from __future__ import annotations

import numpy as np

from coral_key.adversary.iuu import IUUDetectionOracle
from coral_key.fleet.vessel import Vessel, VesselPosition, VesselType
from coral_key.ocean.grid import OceanGrid


class TestIUUDetectionOracle:
    def test_detects_active_iuu(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.5, n_ports=1, rng=rng)
        oracle = IUUDetectionOracle(grid=grid)

        vessels = [
            Vessel(
                vessel_type=VesselType.IUU,
                position=VesselPosition(zone_x=0, zone_y=0),
                at_port=False,
                ais_enabled=False,
            ),
            Vessel(vessel_type=VesselType.LEGAL, at_port=True),
        ]
        assert oracle.is_iuu_active(vessels) is True

    def test_no_iuu_when_all_at_port(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        oracle = IUUDetectionOracle(grid=grid)

        vessels = [
            Vessel(vessel_type=VesselType.IUU, at_port=True),
            Vessel(vessel_type=VesselType.LEGAL, at_port=True),
        ]
        assert oracle.is_iuu_active(vessels) is False

    def test_get_active_iuu_events(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.5, n_ports=1, rng=rng)
        oracle = IUUDetectionOracle(grid=grid)

        vessels = [
            Vessel(
                vessel_type=VesselType.IUU,
                position=VesselPosition(zone_x=1, zone_y=1),
                at_port=False,
                ais_enabled=False,
            ),
            Vessel(vessel_type=VesselType.LEGAL, at_port=False),
        ]
        events = oracle.get_active_iuu_events(vessels)
        assert len(events) == 1
        assert events[0]["ais_disabled"] is True

    def test_count_mpa_violations(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.5, n_ports=1, rng=rng)
        oracle = IUUDetectionOracle(grid=grid)

        # Put vessel in a known MPA zone
        mpa_zones = grid.get_mpa_zones()
        if mpa_zones:
            zone = mpa_zones[0]
            vessels = [
                Vessel(
                    vessel_type=VesselType.IUU,
                    position=VesselPosition(zone_x=zone.x, zone_y=zone.y),
                    at_port=False,
                ),
            ]
            violations = oracle.count_mpa_violations(vessels)
            assert violations >= 1
