"""eDNA sampling stream: sparse, delayed species presence/abundance signals."""

from __future__ import annotations

import numpy as np

from coral_key.ocean.fish_stock import FishStock


class EDNAStream:
    """Environmental DNA sampling providing species presence signals.

    Sparse and delayed but provides ground-truth-adjacent stock distribution data.
    """

    def __init__(
        self,
        n_species: int,
        n_sample_zones: int = 4,
        sample_interval: int = 56,
        detection_sensitivity: float = 0.7,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._n_species = n_species
        self._n_sample_zones = n_sample_zones
        self._sample_interval = sample_interval
        self._sensitivity = detection_sensitivity
        self._rng = rng or np.random.default_rng()

    @property
    def dimensionality(self) -> int:
        return self._n_species * self._n_sample_zones

    @property
    def label(self) -> str:
        return "edna_sampling"

    def observe(self, fish_stock: FishStock, epoch: int, n_zones: int) -> np.ndarray:
        """Generate eDNA observation.

        Returns array of shape (n_species * n_sample_zones,).
        Only produces real data on sample epochs; otherwise returns -1 (no data).
        """
        if epoch % self._sample_interval != 0:
            return np.full(self.dimensionality, -1.0)

        # Select random sample zones
        sample_zones = self._rng.integers(0, n_zones, size=self._n_sample_zones)

        data = np.zeros(self.dimensionality)
        for i, sp in enumerate(fish_stock.species[: self._n_species]):
            for j, zone_idx in enumerate(sample_zones):
                local_abundance = sp.spatial_distribution[zone_idx] * sp.biomass
                # Detection probability depends on abundance and sensitivity
                if self._rng.random() < self._sensitivity:
                    # Noisy relative abundance signal
                    signal = local_abundance / sp.carrying_capacity
                    noise = self._rng.normal(0, 0.1)
                    data[i * self._n_sample_zones + j] = max(0.0, signal + noise)

        return data
