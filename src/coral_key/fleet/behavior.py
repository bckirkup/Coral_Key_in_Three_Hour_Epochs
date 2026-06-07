"""Fleet behavior: movement, fishing decisions, and trip management."""

from __future__ import annotations

import numpy as np

from coral_key.config import AdversaryConfig, FleetConfig
from coral_key.fleet.vessel import Vessel, VesselPosition, VesselType
from coral_key.ocean.grid import OceanGrid, Zone, ZoneType


class FleetManager:
    """Manages fleet lifecycle: trip initiation, movement, fishing, and port return."""

    def __init__(
        self,
        grid: OceanGrid,
        fleet_config: FleetConfig,
        adversary_config: AdversaryConfig,
        n_species: int,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._grid = grid
        self._fleet_cfg = fleet_config
        self._adv_cfg = adversary_config
        self._n_species = n_species
        self._rng = rng or np.random.default_rng()
        self.vessels: list[Vessel] = []
        self._initialize_fleet()

    def _initialize_fleet(self) -> None:
        """Create initial fleet at ports."""
        ports = self._grid.get_port_zones()
        if not ports:
            ports = [self._grid.zones[0]]

        for i in range(self._fleet_cfg.n_legal_vessels):
            port = ports[i % len(ports)]
            self.vessels.append(self._make_vessel(VesselType.LEGAL, port))

        for i in range(self._fleet_cfg.n_gaming_vessels):
            port = ports[i % len(ports)]
            self.vessels.append(self._make_vessel(VesselType.GAMING, port))

        for i in range(self._fleet_cfg.n_iuu_vessels):
            port = ports[i % len(ports)]
            self.vessels.append(self._make_vessel(VesselType.IUU, port))

    def _make_vessel(self, vtype: VesselType, port: Zone) -> Vessel:
        """Create a vessel at a given port."""
        return Vessel(
            vessel_type=vtype,
            position=VesselPosition(zone_x=port.x, zone_y=port.y),
            catch_this_epoch=np.zeros(self._n_species),
            total_catch=np.zeros(self._n_species),
            at_port=True,
            ais_enabled=True,
        )

    def step(
        self,
        epoch: int,
        fish_distribution: np.ndarray,
        enforcement_pressure: float,
    ) -> np.ndarray:
        """Advance fleet by one epoch; return total catch per species across all vessels.

        Args:
            epoch: Current simulation epoch.
            fish_distribution: Array (n_species, n_zones) — biomass fraction per zone.
            enforcement_pressure: Current enforcement level [0, 1].

        Returns:
            Total catch per species (n_species,).
        """
        total_catch = np.zeros(self._n_species)
        ports = self._grid.get_port_zones()
        if not ports:
            return total_catch

        # Reset per-epoch catch for all vessels
        for vessel in self.vessels:
            vessel.catch_this_epoch = np.zeros(self._n_species)

        for vessel in self.vessels:
            if vessel.at_port:
                # Decide whether to depart (random trip initiation)
                if self._rng.random() < 0.15:
                    target = self._choose_fishing_zone(vessel)
                    vessel.depart_port(target.x, target.y)
            else:
                vessel.trip_duration += 1
                # Fish at current location
                catch = self._fish(vessel, fish_distribution, enforcement_pressure)
                vessel.record_catch(catch)
                total_catch += catch

                # Maybe return to port
                if vessel.trip_duration > self._rng.integers(4, 20):
                    port = ports[int(self._rng.integers(0, len(ports)))]
                    vessel.return_to_port(port.x, port.y)

            # Handle AIS behavior
            self._update_ais(vessel, enforcement_pressure)

        return total_catch

    def _choose_fishing_zone(self, vessel: Vessel) -> Zone:
        """Choose a target zone based on vessel type."""
        if vessel.vessel_type == VesselType.IUU:
            # IUU prefers MPA zones (higher biomass)
            mpa_zones = self._grid.get_mpa_zones()
            if mpa_zones and self._rng.random() < 0.6:
                return mpa_zones[int(self._rng.integers(0, len(mpa_zones)))]
        # Legal and gaming choose from legal fishing zones
        fishing_zones = self._grid.get_fishing_zones()
        if not fishing_zones:
            return self._grid.zones[0]
        return fishing_zones[int(self._rng.integers(0, len(fishing_zones)))]

    def _fish(
        self,
        vessel: Vessel,
        fish_distribution: np.ndarray,
        enforcement_pressure: float,
    ) -> np.ndarray:
        """Compute catch for a vessel at its current zone."""
        zone_idx = vessel.position.zone_y * self._grid.nx + vessel.position.zone_x
        zone_idx = min(zone_idx, fish_distribution.shape[1] - 1)

        # Base effort depends on vessel type
        base_effort = 1.0
        if vessel.vessel_type == VesselType.IUU:
            # IUU fishes harder but may reduce effort under enforcement
            base_effort = 1.5 * (1.0 - 0.5 * enforcement_pressure)
        elif vessel.vessel_type == VesselType.GAMING:
            base_effort = 1.1

        # Catch per species proportional to local biomass fraction
        local_biomass_frac = fish_distribution[:, zone_idx]
        catch = base_effort * local_biomass_frac * self._rng.uniform(0.5, 2.0, self._n_species)
        return np.clip(catch, 0.0, None)

    def _update_ais(self, vessel: Vessel, enforcement_pressure: float) -> None:
        """Update AIS state based on vessel behavior and adversary config."""
        if vessel.vessel_type == VesselType.IUU and not vessel.at_port:
            zone = self._grid.get_zone(vessel.position.zone_x, vessel.position.zone_y)
            if zone.zone_type == ZoneType.MPA:
                # Disable AIS in MPA
                if self._rng.random() < self._adv_cfg.ais_disable_probability:
                    vessel.ais_enabled = False
                else:
                    vessel.ais_enabled = True
            elif self._rng.random() < self._adv_cfg.spoof_probability:
                # Spoof position elsewhere
                vessel.ais_enabled = True
                legal_zones = self._grid.get_fishing_zones()
                if legal_zones:
                    fake = legal_zones[int(self._rng.integers(0, len(legal_zones)))]
                    vessel.reported_position = VesselPosition(zone_x=fake.x, zone_y=fake.y)
            else:
                vessel.ais_enabled = True
                vessel.reported_position = None
        else:
            vessel.ais_enabled = True
            vessel.reported_position = None

    def get_reported_catches(self) -> np.ndarray:
        """Get catch as reported by vessels (may be underreported).

        Returns:
            Reported catch per species (n_species,).
        """
        reported = np.zeros(self._n_species)
        for vessel in self.vessels:
            if vessel.catch_this_epoch.size == 0:
                continue
            if vessel.vessel_type == VesselType.IUU:
                reported += vessel.catch_this_epoch * (1.0 - self._fleet_cfg.underreport_fraction)
            elif vessel.vessel_type == VesselType.GAMING:
                reported += vessel.catch_this_epoch * (
                    1.0 - self._adv_cfg.gaming_underreport_margin
                )
            else:
                reported += vessel.catch_this_epoch
        return reported
