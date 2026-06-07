"""Oceanographic data stream: SST, chlorophyll, currents for sensor agents."""

from __future__ import annotations

import numpy as np

from coral_key.ocean.oceanography import OceanState


class OceanographicStream:
    """Generates observation vectors from oceanographic state.

    Concatenates SST, chlorophyll, and current magnitude into a single stream.
    """

    def __init__(self, n_zones: int) -> None:
        self._n_zones = n_zones

    @property
    def dimensionality(self) -> int:
        # SST + chlorophyll + current magnitude = 3 * n_zones
        return self._n_zones * 3

    @property
    def label(self) -> str:
        return "oceanographic"

    def observe(self, state: OceanState) -> np.ndarray:
        """Generate oceanographic observation vector.

        Returns flat array: [sst_normalized..., chl_normalized..., current_mag_normalized...]
        """
        # Normalize SST to [0, 1] range (assume 10-35C)
        sst_norm = (state.sst - 10.0) / 25.0

        # Normalize chlorophyll (log scale)
        chl_norm = np.log1p(state.chlorophyll) / np.log1p(5.0)

        # Current magnitude
        current_mag = np.sqrt(state.current_u**2 + state.current_v**2)
        current_norm = current_mag / 1.0  # Normalize by max expected ~1 m/s

        return np.concatenate(
            [
                np.clip(sst_norm, 0.0, 1.0),
                np.clip(chl_norm, 0.0, 1.0),
                np.clip(current_norm, 0.0, 1.0),
            ]
        )
