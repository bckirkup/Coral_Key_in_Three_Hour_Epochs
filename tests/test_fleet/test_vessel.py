"""Tests for vessel models."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel, VesselPosition, VesselType


class TestVessel:
    def test_default_vessel_at_port(self) -> None:
        vessel = Vessel(vessel_type=VesselType.LEGAL)
        assert vessel.at_port is True
        assert vessel.ais_enabled is True
        assert vessel.trip_duration == 0

    def test_depart_and_return(self) -> None:
        vessel = Vessel(vessel_type=VesselType.LEGAL)
        vessel.depart_port(target_x=3, target_y=5)
        assert vessel.at_port is False
        assert vessel.position.zone_x == 3
        assert vessel.position.zone_y == 5

        vessel.return_to_port(port_x=0, port_y=0)
        assert vessel.at_port is True
        assert vessel.trip_duration == 0

    def test_record_catch(self) -> None:
        vessel = Vessel(
            vessel_type=VesselType.LEGAL,
            catch_this_epoch=np.zeros(3),
            total_catch=np.zeros(3),
        )
        catch = np.array([10.0, 5.0, 2.0])
        vessel.record_catch(catch)

        np.testing.assert_array_equal(vessel.catch_this_epoch, catch)
        np.testing.assert_array_equal(vessel.total_catch, catch)

        # Second catch accumulates
        vessel.record_catch(catch)
        np.testing.assert_array_equal(vessel.total_catch, catch * 2)

    def test_vessel_types(self) -> None:
        assert VesselType.LEGAL == "legal"
        assert VesselType.GAMING == "gaming"
        assert VesselType.IUU == "iuu"

    def test_position_model(self) -> None:
        pos = VesselPosition(zone_x=5, zone_y=3, speed=8.5, heading=270.0)
        assert pos.zone_x == 5
        assert pos.speed == 8.5
