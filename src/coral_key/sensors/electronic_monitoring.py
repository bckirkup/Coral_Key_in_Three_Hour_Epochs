"""Electronic monitoring stream: on-vessel cameras for catch verification."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel, VesselType


class EMStream:
    """Electronic monitoring (EM) via on-vessel cameras.

    Provides sampled catch verification data. Review rate determines what fraction
    of EM footage is actually processed (cheaper than human observers).
    """

    def __init__(
        self,
        n_species: int,
        review_rate: float = 0.3,
        n_monitored_vessels: int = 10,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._n_species = n_species
        self._review_rate = review_rate
        self._n_monitored = n_monitored_vessels
        self._rng = rng or np.random.default_rng()

    @property
    def dimensionality(self) -> int:
        # Per monitored vessel: catch per species + discard flag + gear_deployed flag
        return self._n_monitored * (self._n_species + 2)

    @property
    def label(self) -> str:
        return "electronic_monitoring"

    def observe(self, vessels: list[Vessel]) -> np.ndarray:
        """Generate EM observation vector.

        Only vessels selected for review this epoch produce data.
        Returns array with -1 for unreviewed vessels.
        """
        data = np.full(self.dimensionality, -1.0)

        monitored = vessels[: self._n_monitored]
        for i, vessel in enumerate(monitored):
            # Randomly decide whether this vessel's footage is reviewed this epoch
            if self._rng.random() > self._review_rate:
                continue
            if vessel.at_port:
                continue

            offset = i * (self._n_species + 2)
            # Actual catch observed by camera (ground truth with small noise)
            if vessel.catch_this_epoch.size >= self._n_species:
                catch = vessel.catch_this_epoch[: self._n_species]
                noise = self._rng.normal(0, 0.05, self._n_species)
                data[offset : offset + self._n_species] = np.clip(catch + noise, 0.0, None)
            else:
                data[offset : offset + self._n_species] = 0.0

            # Discard indicator (gaming vessels high-grade)
            discard = 1.0 if vessel.vessel_type == VesselType.GAMING else 0.0
            data[offset + self._n_species] = discard

            # Gear deployed indicator
            data[offset + self._n_species + 1] = 0.0 if vessel.at_port else 1.0

        return data
