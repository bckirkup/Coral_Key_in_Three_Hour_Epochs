"""AIS/VMS stream: vessel positions, speeds, and identity with failure modes."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel


class AISStream:
    """Generates AIS observation vectors from fleet state.

    Each vessel contributes a feature vector: [zone_x, zone_y, speed, heading, ais_on].
    Vessels with disabled AIS produce NaN entries (dark vessels).
    Spoofed positions inject false data.
    """

    def __init__(
        self, n_vessels: int, update_interval: int = 1, features_per_vessel: int = 5
    ) -> None:
        self._n_vessels = n_vessels
        self._update_interval = update_interval
        self._features_per_vessel = features_per_vessel
        self._dimensionality = n_vessels * features_per_vessel

    @property
    def dimensionality(self) -> int:
        return self._dimensionality

    @property
    def label(self) -> str:
        return "ais_vms"

    def observe(self, vessels: list[Vessel], epoch: int) -> np.ndarray:
        """Generate AIS observation vector.

        Returns flat array of shape (n_vessels * features_per_vessel,).
        Core features: [norm_x, norm_y, norm_speed, norm_heading, ais_flag].
        Additional slots (if features_per_vessel > 5) are zero-padded for future use.
        """
        if epoch % self._update_interval != 0:
            return np.full(self._dimensionality, np.nan)

        fpv = self._features_per_vessel
        data = np.zeros(self._dimensionality)
        for i, vessel in enumerate(vessels[: self._n_vessels]):
            offset = i * fpv
            if not vessel.ais_enabled:
                # Dark vessel — no AIS signal
                data[offset : offset + fpv] = np.nan
            elif vessel.reported_position is not None:
                # Spoofed position
                data[offset] = vessel.reported_position.zone_x / 10.0
                data[offset + 1] = vessel.reported_position.zone_y / 10.0
                data[offset + 2] = vessel.position.speed / 20.0
                data[offset + 3] = vessel.position.heading / 360.0
                data[offset + 4] = 1.0
            else:
                # Honest AIS
                data[offset] = vessel.position.zone_x / 10.0
                data[offset + 1] = vessel.position.zone_y / 10.0
                data[offset + 2] = vessel.position.speed / 20.0
                data[offset + 3] = vessel.position.heading / 360.0
                data[offset + 4] = 1.0

        return data

    def count_dark_vessels(self, observation: np.ndarray) -> int:
        """Count vessels with no AIS signal (NaN blocks)."""
        fpv = self._features_per_vessel
        count = 0
        for i in range(self._n_vessels):
            offset = i * fpv
            if np.isnan(observation[offset]):
                count += 1
        return count
