"""Tests for fish stock dynamics (Schaefer model)."""

from __future__ import annotations

import numpy as np

from coral_key.ocean.fish_stock import FishStock, SpeciesState


class TestSpeciesState:
    def test_msy_calculation(self) -> None:
        sp = SpeciesState(
            name="test",
            biomass=500.0,
            carrying_capacity=1000.0,
            intrinsic_growth_rate=0.3,
            catchability=0.001,
            spatial_distribution=np.array([0.5, 0.5]),
        )
        assert sp.msy == 0.3 * 1000.0 / 4.0  # 75.0
        assert sp.b_msy == 500.0

    def test_overfished_flag(self) -> None:
        sp = SpeciesState(
            name="test",
            biomass=400.0,
            carrying_capacity=1000.0,
            intrinsic_growth_rate=0.3,
            catchability=0.001,
            spatial_distribution=np.array([1.0]),
        )
        assert sp.is_overfished is True

        sp.biomass = 600.0
        assert sp.is_overfished is False


class TestFishStock:
    def test_initialization(self, rng: np.random.Generator) -> None:
        stock = FishStock(n_species=3, n_zones=16, rng=rng)
        assert len(stock.species) == 3
        for sp in stock.species:
            assert sp.biomass > 0
            assert abs(sp.spatial_distribution.sum() - 1.0) < 1e-6

    def test_growth_without_catch(self, rng: np.random.Generator) -> None:
        stock = FishStock(
            n_species=1,
            n_zones=4,
            carrying_capacity=1000.0,
            intrinsic_growth_rate=0.3,
            rng=rng,
        )
        initial_biomass = stock.species[0].biomass
        habitat = np.ones(4) * 0.5

        # Step with zero catch
        stock.step(catches=np.array([0.0]), habitat_suitability=habitat)
        # Should grow (below K)
        assert stock.species[0].biomass > initial_biomass

    def test_overfishing_reduces_biomass(self, rng: np.random.Generator) -> None:
        stock = FishStock(
            n_species=1,
            n_zones=4,
            carrying_capacity=1000.0,
            intrinsic_growth_rate=0.1,
            rng=rng,
        )
        habitat = np.ones(4) * 0.5

        # Excessive catch
        for _ in range(20):
            stock.step(catches=np.array([100.0]), habitat_suitability=habitat)

        assert stock.species[0].biomass < 500.0

    def test_biomass_never_zero(self, rng: np.random.Generator) -> None:
        stock = FishStock(n_species=1, n_zones=4, rng=rng)
        habitat = np.ones(4) * 0.5

        # Massive overfishing
        for _ in range(100):
            stock.step(catches=np.array([5000.0]), habitat_suitability=habitat)

        # Biomass floored at 1.0
        assert stock.species[0].biomass >= 1.0

    def test_spatial_distribution_sums_to_one(self, rng: np.random.Generator) -> None:
        stock = FishStock(n_species=2, n_zones=8, rng=rng)
        habitat = rng.uniform(0.1, 1.0, 8)

        for _ in range(10):
            stock.step(catches=np.array([5.0, 3.0]), habitat_suitability=habitat)

        for sp in stock.species:
            assert abs(sp.spatial_distribution.sum() - 1.0) < 1e-6

    def test_cpue_positive(self, rng: np.random.Generator) -> None:
        stock = FishStock(n_species=2, n_zones=8, rng=rng)
        cpue = stock.get_cpue(species_idx=0, zone_idx=3, effort=1.0)
        assert cpue >= 0.0
