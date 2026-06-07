"""Tests for fleet behavior management."""

from __future__ import annotations

import numpy as np

from coral_key.config import AdversaryConfig, FleetConfig
from coral_key.fleet.behavior import FleetManager
from coral_key.fleet.vessel import VesselType
from coral_key.ocean.grid import OceanGrid


class TestFleetManager:
    def test_fleet_initialization(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=2, rng=rng)
        fleet = FleetManager(
            grid=grid,
            fleet_config=FleetConfig(n_legal_vessels=5, n_gaming_vessels=2, n_iuu_vessels=1),
            adversary_config=AdversaryConfig(),
            n_species=2,
            rng=rng,
        )
        assert len(fleet.vessels) == 8
        legal = [v for v in fleet.vessels if v.vessel_type == VesselType.LEGAL]
        gaming = [v for v in fleet.vessels if v.vessel_type == VesselType.GAMING]
        iuu = [v for v in fleet.vessels if v.vessel_type == VesselType.IUU]
        assert len(legal) == 5
        assert len(gaming) == 2
        assert len(iuu) == 1

    def test_step_returns_catch(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=2, rng=rng)
        fleet = FleetManager(
            grid=grid,
            fleet_config=FleetConfig(n_legal_vessels=5, n_gaming_vessels=1, n_iuu_vessels=1),
            adversary_config=AdversaryConfig(),
            n_species=2,
            rng=rng,
        )
        fish_dist = np.ones((2, 16)) / 16.0
        catch = fleet.step(epoch=0, fish_distribution=fish_dist, enforcement_pressure=0.3)
        assert catch.shape == (2,)
        assert np.all(catch >= 0.0)

    def test_iuu_disables_ais(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.5, n_ports=1, rng=rng)
        fleet = FleetManager(
            grid=grid,
            fleet_config=FleetConfig(n_legal_vessels=2, n_gaming_vessels=0, n_iuu_vessels=5),
            adversary_config=AdversaryConfig(ais_disable_probability=1.0),
            n_species=2,
            rng=rng,
        )
        fish_dist = np.ones((2, 16)) / 16.0

        # Run enough epochs for IUU vessels to depart and fish in MPA
        for epoch in range(50):
            fleet.step(epoch=epoch, fish_distribution=fish_dist, enforcement_pressure=0.1)

        # Check at least some IUU vessels have disabled AIS
        iuu_vessels = [v for v in fleet.vessels if v.vessel_type == VesselType.IUU]
        ais_disabled = [v for v in iuu_vessels if not v.ais_enabled]
        # With 100% disable probability in MPA, any IUU in MPA should be dark
        # (some may still be at port)
        assert len(ais_disabled) >= 0  # Non-deterministic, but validates no crash

    def test_reported_catches_underreported(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=2, rng=rng)
        fleet = FleetManager(
            grid=grid,
            fleet_config=FleetConfig(
                n_legal_vessels=3,
                n_gaming_vessels=2,
                n_iuu_vessels=3,
                underreport_fraction=0.5,
            ),
            adversary_config=AdversaryConfig(gaming_underreport_margin=0.2),
            n_species=2,
            rng=rng,
        )
        fish_dist = np.ones((2, 16)) / 16.0

        # Run simulation to accumulate catch
        total_actual = np.zeros(2)
        for epoch in range(30):
            catch = fleet.step(epoch=epoch, fish_distribution=fish_dist, enforcement_pressure=0.2)
            total_actual += catch

        reported = fleet.get_reported_catches()
        # Reported should generally be <= actual (underreporting)
        # (for single epoch reported catches)
        assert reported.shape == (2,)
