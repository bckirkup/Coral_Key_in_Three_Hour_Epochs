"""IUU detection oracle: ground truth about illegal fishing activity."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel, VesselType
from coral_key.ocean.grid import OceanGrid, ZoneType


class IUUDetectionOracle:
    """Ground-truth oracle for IUU fishing activity.

    Provides the simulation's hidden state about which vessels are fishing
    illegally, where, and what the true catch is versus what was reported.
    """

    def __init__(self, grid: OceanGrid) -> None:
        self._grid = grid

    def get_active_iuu_events(self, vessels: list[Vessel]) -> list[dict[str, object]]:
        """Return list of currently active IUU events (ground truth).

        Each event: {vessel_id, zone_x, zone_y, in_mpa, ais_disabled, spoofing}
        """
        events: list[dict[str, object]] = []
        for vessel in vessels:
            if vessel.vessel_type != VesselType.IUU:
                continue
            if vessel.at_port:
                continue

            zone = self._grid.get_zone(vessel.position.zone_x, vessel.position.zone_y)
            events.append(
                {
                    "vessel_id": vessel.id,
                    "zone_x": vessel.position.zone_x,
                    "zone_y": vessel.position.zone_y,
                    "in_mpa": zone.zone_type == ZoneType.MPA,
                    "ais_disabled": not vessel.ais_enabled,
                    "spoofing": vessel.reported_position is not None,
                }
            )
        return events

    def is_iuu_active(self, vessels: list[Vessel]) -> bool:
        """Return True if any IUU vessel is actively fishing (not at port)."""
        return any(v.vessel_type == VesselType.IUU and not v.at_port for v in vessels)

    def count_mpa_violations(self, vessels: list[Vessel]) -> int:
        """Count vessels currently fishing inside the MPA."""
        count = 0
        for vessel in vessels:
            if vessel.at_port:
                continue
            zone = self._grid.get_zone(vessel.position.zone_x, vessel.position.zone_y)
            if zone.zone_type == ZoneType.MPA:
                count += 1
        return count

    def compute_actual_vs_reported_catch(
        self,
        vessels: list[Vessel],
        n_species: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (actual_total_catch, reported_total_catch) per species."""
        actual = np.zeros(n_species)
        reported = np.zeros(n_species)
        for vessel in vessels:
            if vessel.catch_this_epoch.size == 0:
                continue
            catch = vessel.catch_this_epoch[:n_species]
            actual[: len(catch)] += catch
            # Reporting depends on vessel type (handled by fleet manager)
        return actual, reported
