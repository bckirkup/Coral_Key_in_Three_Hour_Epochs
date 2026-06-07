"""Tests for AIS sensor stream."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel, VesselPosition, VesselType
from coral_key.sensors.ais import AISStream


class TestAISStream:
    def test_dimensionality(self) -> None:
        ais = AISStream(n_vessels=10)
        assert ais.dimensionality == 50  # 10 * 5

    def test_observe_honest_vessel(self) -> None:
        ais = AISStream(n_vessels=1)
        vessel = Vessel(
            vessel_type=VesselType.LEGAL,
            position=VesselPosition(zone_x=3, zone_y=5, speed=10.0, heading=90.0),
            ais_enabled=True,
            at_port=False,
        )
        obs = ais.observe([vessel], epoch=0)
        assert obs.shape == (5,)
        assert obs[0] == 3.0 / 10.0  # normalized x
        assert obs[1] == 5.0 / 10.0  # normalized y
        assert not np.any(np.isnan(obs))

    def test_observe_dark_vessel(self) -> None:
        ais = AISStream(n_vessels=1)
        vessel = Vessel(
            vessel_type=VesselType.IUU,
            position=VesselPosition(zone_x=2, zone_y=2),
            ais_enabled=False,
            at_port=False,
        )
        obs = ais.observe([vessel], epoch=0)
        assert np.all(np.isnan(obs))

    def test_observe_spoofed_vessel(self) -> None:
        ais = AISStream(n_vessels=1)
        vessel = Vessel(
            vessel_type=VesselType.IUU,
            position=VesselPosition(zone_x=5, zone_y=5),
            ais_enabled=True,
            reported_position=VesselPosition(zone_x=1, zone_y=1),
            at_port=False,
        )
        obs = ais.observe([vessel], epoch=0)
        # Should show spoofed position, not actual
        assert obs[0] == 1.0 / 10.0
        assert obs[1] == 1.0 / 10.0

    def test_count_dark_vessels(self) -> None:
        ais = AISStream(n_vessels=3)
        vessels = [
            Vessel(vessel_type=VesselType.LEGAL, ais_enabled=True, at_port=False),
            Vessel(vessel_type=VesselType.IUU, ais_enabled=False, at_port=False),
            Vessel(vessel_type=VesselType.IUU, ais_enabled=False, at_port=False),
        ]
        obs = ais.observe(vessels, epoch=0)
        assert ais.count_dark_vessels(obs) == 2

    def test_update_interval(self) -> None:
        ais = AISStream(n_vessels=2, update_interval=3)
        vessels = [
            Vessel(vessel_type=VesselType.LEGAL, ais_enabled=True, at_port=False),
            Vessel(vessel_type=VesselType.LEGAL, ais_enabled=True, at_port=False),
        ]
        # Non-update epoch returns NaN
        obs = ais.observe(vessels, epoch=1)
        assert np.all(np.isnan(obs))

        # Update epoch returns data
        obs = ais.observe(vessels, epoch=3)
        assert not np.all(np.isnan(obs))
