"""Shared fixtures for Coral Key tests."""

from __future__ import annotations

import numpy as np
import pytest

from coral_key.config import ScenarioConfig
from coral_key.ocean.grid import OceanGrid


@pytest.fixture
def rng() -> np.random.Generator:
    """Deterministic RNG for reproducible tests."""
    return np.random.default_rng(42)


@pytest.fixture
def small_config() -> ScenarioConfig:
    """Small configuration for fast tests."""
    return ScenarioConfig(
        ocean=ScenarioConfig.model_fields["ocean"]
        .default_factory()
        .model_copy(  # type: ignore[union-attr]
            update={"n_zones_x": 4, "n_zones_y": 4, "n_ports": 2}
        ),
        fish=ScenarioConfig.model_fields["fish"]
        .default_factory()
        .model_copy(  # type: ignore[union-attr]
            update={"n_species": 2}
        ),
        fleet=ScenarioConfig.model_fields["fleet"]
        .default_factory()
        .model_copy(  # type: ignore[union-attr]
            update={"n_legal_vessels": 5, "n_gaming_vessels": 2, "n_iuu_vessels": 2}
        ),
        total_epochs=50,
        seed=42,
    )


@pytest.fixture
def small_grid(rng: np.random.Generator) -> OceanGrid:
    """4x4 ocean grid for testing."""
    return OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=2, rng=rng)
