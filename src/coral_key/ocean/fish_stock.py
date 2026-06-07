"""Fish stock dynamics: Schaefer logistic production model with spatial distribution."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field


class SpeciesState(BaseModel):
    """State of a single fish species."""

    model_config = {"arbitrary_types_allowed": True}

    name: str = Field(default="species_0")
    biomass: float = Field(gt=0.0, description="Total biomass")
    carrying_capacity: float = Field(gt=0.0, description="K parameter")
    intrinsic_growth_rate: float = Field(gt=0.0, description="r parameter")
    catchability: float = Field(gt=0.0, description="q coefficient")
    spatial_distribution: np.ndarray = Field(
        description="Fraction of biomass in each zone (sums to 1)"
    )

    @property
    def msy(self) -> float:
        """Maximum sustainable yield = rK/4."""
        return self.intrinsic_growth_rate * self.carrying_capacity / 4.0

    @property
    def b_msy(self) -> float:
        """Biomass at MSY = K/2."""
        return self.carrying_capacity / 2.0

    @property
    def is_overfished(self) -> bool:
        """Stock is overfished if biomass < B_MSY."""
        return self.biomass < self.b_msy


class FishStock:
    """Multi-species fish stock using Schaefer production model.

    B_{t+1} = B_t + r * B_t * (1 - B_t/K) - C_t

    Spatial distribution is driven by habitat suitability from oceanographic state.
    """

    def __init__(
        self,
        n_species: int,
        n_zones: int,
        carrying_capacity: float = 1000.0,
        intrinsic_growth_rate: float = 0.3,
        catchability: float = 0.001,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._rng = rng or np.random.default_rng()
        self._n_zones = n_zones

        species_names = ["grouper", "snapper", "lobster", "tuna", "mahi"]
        self.species: list[SpeciesState] = []
        for i in range(n_species):
            name = species_names[i] if i < len(species_names) else f"species_{i}"
            # Start near carrying capacity
            initial_biomass = carrying_capacity * self._rng.uniform(0.6, 0.9)
            dist = self._rng.dirichlet(np.ones(n_zones))
            self.species.append(
                SpeciesState(
                    name=name,
                    biomass=initial_biomass,
                    carrying_capacity=carrying_capacity,
                    intrinsic_growth_rate=intrinsic_growth_rate,
                    catchability=catchability,
                    spatial_distribution=dist,
                )
            )

    def step(self, catches: np.ndarray, habitat_suitability: np.ndarray) -> None:
        """Advance fish stock by one epoch.

        Args:
            catches: Array of shape (n_species,) — total catch per species this epoch.
            habitat_suitability: Array of shape (n_zones,) — relative habitat quality.
        """
        for i, sp in enumerate(self.species):
            catch = catches[i] if i < len(catches) else 0.0
            # Schaefer logistic growth
            growth = (
                sp.intrinsic_growth_rate * sp.biomass * (1.0 - sp.biomass / sp.carrying_capacity)
            )
            new_biomass = sp.biomass + growth - catch
            sp.biomass = max(1.0, new_biomass)  # prevent extinction to zero

            # Update spatial distribution based on habitat suitability
            self._redistribute(sp, habitat_suitability)

    def _redistribute(self, species: SpeciesState, suitability: np.ndarray) -> None:
        """Redistribute biomass spatially based on habitat suitability + inertia."""
        # Mix current distribution with habitat-driven target (inertia = 0.9)
        target = suitability / (suitability.sum() + 1e-10)
        species.spatial_distribution = 0.9 * species.spatial_distribution + 0.1 * target
        # Renormalize
        total = species.spatial_distribution.sum()
        if total > 0:
            species.spatial_distribution /= total

    def get_cpue(
        self,
        species_idx: int,
        zone_idx: int,
        effort: float,
        obs_noise_std: float = 0.2,
    ) -> float:
        """Compute observed CPUE for a species in a zone.

        CPUE = q * B_zone + lognormal noise
        """
        sp = self.species[species_idx]
        local_biomass = sp.biomass * sp.spatial_distribution[zone_idx]
        expected_cpue = sp.catchability * local_biomass * effort
        noise = float(self._rng.lognormal(0, obs_noise_std))
        return float(expected_cpue * noise)

    def get_total_biomass(self) -> np.ndarray:
        """Return total biomass per species."""
        return np.array([sp.biomass for sp in self.species])
