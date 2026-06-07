"""Platform interference: Layer 3 adversary attacking sensor platforms."""

from __future__ import annotations

import numpy as np


class PlatformInterference:
    """Simulates adversarial interference with monitoring platforms.

    Includes jamming/spoofing command links, physically fouling sensors,
    and inducing data gaps that mimic natural comms failures.
    """

    def __init__(
        self,
        interference_rate: float = 0.05,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._rate = interference_rate
        self._rng = rng or np.random.default_rng()

    def apply_interference(self, sensor_data: np.ndarray) -> tuple[np.ndarray, bool]:
        """Potentially corrupt sensor data with interference.

        Args:
            sensor_data: Clean sensor observation vector.

        Returns:
            Tuple of (possibly corrupted data, was_interfered).
        """
        if self._rng.random() < self._rate:
            corrupted = sensor_data.copy()
            # Random subset of dimensions get nulled or corrupted
            n_corrupt = max(1, int(len(corrupted) * self._rng.uniform(0.1, 0.5)))
            indices = self._rng.choice(len(corrupted), size=n_corrupt, replace=False)
            # Mix of NaN (data gap) and noise injection
            for idx in indices:
                if self._rng.random() < 0.5:
                    corrupted[idx] = np.nan
                else:
                    corrupted[idx] += self._rng.normal(0, 2.0)
            return corrupted, True
        return sensor_data, False

    def is_platform_compromised(self) -> bool:
        """Roll whether a platform is compromised this epoch."""
        return bool(self._rng.random() < self._rate)
