"""Oceanographic state: SST, chlorophyll-a, currents, and seasonal cycles."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from coral_key.ocean.grid import OceanGrid


class OceanState(BaseModel):
    """Snapshot of oceanographic conditions across the grid."""

    model_config = {"arbitrary_types_allowed": True}

    sst: np.ndarray = Field(description="Sea surface temperature per zone")
    chlorophyll: np.ndarray = Field(description="Chlorophyll-a concentration per zone")
    current_u: np.ndarray = Field(description="East-west current component per zone")
    current_v: np.ndarray = Field(description="North-south current component per zone")

    @property
    def n_zones(self) -> int:
        return len(self.sst)


class Oceanography:
    """Seasonal oceanographic model driving fish distribution and sensor data."""

    def __init__(
        self,
        grid: OceanGrid,
        sst_base: float = 26.0,
        sst_amplitude: float = 3.0,
        chlorophyll_base: float = 0.5,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._grid = grid
        self._sst_base = sst_base
        self._sst_amplitude = sst_amplitude
        self._chlorophyll_base = chlorophyll_base
        self._rng = rng or np.random.default_rng()
        self._n_zones = grid.nx * grid.ny

    def compute_state(self, epoch: int, epoch_hours: float = 3.0) -> OceanState:
        """Compute oceanographic state at a given epoch.

        Seasonal cycle assumes ~2920 epochs/year at 3h per epoch.
        """
        epochs_per_year = 365.25 * 24.0 / epoch_hours
        season_phase = 2.0 * np.pi * epoch / epochs_per_year

        # SST: seasonal + spatial gradient (deeper zones cooler) + noise
        depths = np.array([z.depth for z in self._grid.zones])
        depth_effect = -0.02 * depths
        sst = (
            self._sst_base
            + self._sst_amplitude * np.sin(season_phase)
            + depth_effect
            + self._rng.normal(0, 0.3, self._n_zones)
        )

        # Chlorophyll: inversely correlated with SST (upwelling in cooler regions)
        chl_seasonal = self._chlorophyll_base * (1.0 + 0.5 * np.cos(season_phase))
        habitat = np.array([z.habitat_quality for z in self._grid.zones])
        chlorophyll = chl_seasonal * habitat + self._rng.exponential(0.1, self._n_zones)
        chlorophyll = np.clip(chlorophyll, 0.01, 5.0)

        # Currents: simple seasonal rotation + noise
        base_u = 0.2 * np.cos(season_phase)
        base_v = 0.2 * np.sin(season_phase)
        current_u = base_u + self._rng.normal(0, 0.05, self._n_zones)
        current_v = base_v + self._rng.normal(0, 0.05, self._n_zones)

        return OceanState(
            sst=sst,
            chlorophyll=chlorophyll,
            current_u=current_u,
            current_v=current_v,
        )

    def compute_fish_habitat_suitability(self, state: OceanState) -> np.ndarray:
        """Compute per-zone habitat suitability from oceanographic state.

        Higher chlorophyll and moderate SST produce better habitat.
        Returns array of shape (n_zones,) with values in [0, 1].
        """
        # Optimal SST around 24-28C
        sst_score = np.exp(-0.1 * (state.sst - 26.0) ** 2)
        # Higher chlorophyll = more productive
        chl_score = np.tanh(state.chlorophyll / self._chlorophyll_base)
        # Combine
        suitability = 0.6 * chl_score + 0.4 * sst_score
        return np.clip(suitability, 0.0, 1.0)
