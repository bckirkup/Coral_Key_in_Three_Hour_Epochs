"""SAR/optical satellite vessel detection: independent, periodic observations."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel
from coral_key.ocean.grid import OceanGrid


class SARStream:
    """Synthetic aperture radar / optical satellite vessel detection.

    Produces periodic vessel-presence maps independent of AIS.
    Works through cloud/night (SAR) but has revisit delays.
    """

    def __init__(
        self,
        grid: OceanGrid,
        revisit_interval: int = 8,
        detection_probability: float = 0.85,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._grid = grid
        self._revisit_interval = revisit_interval
        self._detection_prob = detection_probability
        self._rng = rng or np.random.default_rng()
        self._n_zones = grid.nx * grid.ny

    @property
    def dimensionality(self) -> int:
        return self._n_zones

    @property
    def label(self) -> str:
        return "sar_satellite"

    def observe(self, vessels: list[Vessel], epoch: int) -> np.ndarray:
        """Generate SAR observation: vessel count per zone.

        Returns array of shape (n_zones,) — detected vessel count per zone.
        Only produces data on revisit epochs; otherwise returns zeros.
        """
        if epoch % self._revisit_interval != 0:
            return np.full(self._n_zones, -1.0)  # -1 indicates no observation

        detections = np.zeros(self._n_zones)
        for vessel in vessels:
            if vessel.at_port:
                continue
            zone_idx = vessel.position.zone_y * self._grid.nx + vessel.position.zone_x
            zone_idx = min(zone_idx, self._n_zones - 1)
            # Probabilistic detection
            if self._rng.random() < self._detection_prob:
                detections[zone_idx] += 1.0

        return detections

    def cross_reference_ais(
        self,
        sar_obs: np.ndarray,
        ais_obs: np.ndarray,
        n_vessels: int,
    ) -> int:
        """Count discrepancies between SAR detections and AIS positions.

        Returns number of zones with SAR detections but no corresponding AIS position.
        """
        if np.all(sar_obs < 0):
            return 0  # No SAR observation this epoch

        ais_positions = np.zeros(self._n_zones)
        for i in range(n_vessels):
            offset = i * 5
            if offset + 4 >= len(ais_obs):
                break
            if not np.isnan(ais_obs[offset]):
                # Reconstruct zone from normalized coords
                zx = int(ais_obs[offset] * 10.0)
                zy = int(ais_obs[offset + 1] * 10.0)
                zone_idx = zy * self._grid.nx + zx
                if 0 <= zone_idx < self._n_zones:
                    ais_positions[zone_idx] += 1.0

        # Zones with SAR detections but no AIS = dark vessels
        discrepancies = int(np.sum((sar_obs > 0) & (ais_positions == 0)))
        return discrepancies
