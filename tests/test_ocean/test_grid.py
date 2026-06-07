"""Tests for ocean grid generation and zone management."""

from __future__ import annotations

import numpy as np

from coral_key.ocean.grid import OceanGrid, ZoneType


class TestOceanGrid:
    def test_generate_correct_size(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=8, ny=8, mpa_fraction=0.2, n_ports=3, rng=rng)
        assert grid.nx == 8
        assert grid.ny == 8
        assert len(grid.zones) == 64

    def test_mpa_fraction_respected(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=10, ny=10, mpa_fraction=0.3, n_ports=2, rng=rng)
        mpa_count = sum(1 for z in grid.zones if z.zone_type == ZoneType.MPA)
        assert mpa_count == 30

    def test_ports_created(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=6, ny=6, mpa_fraction=0.1, n_ports=4, rng=rng)
        port_count = sum(1 for z in grid.zones if z.zone_type == ZoneType.PORT)
        assert port_count == 4

    def test_get_zone_by_coords(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.2, n_ports=1, rng=rng)
        zone = grid.get_zone(2, 3)
        assert zone.x == 2
        assert zone.y == 3

    def test_zone_fishing_allowed(self) -> None:
        from coral_key.ocean.grid import Zone

        open_zone = Zone(x=0, y=0, zone_type=ZoneType.OPEN)
        mpa_zone = Zone(x=1, y=1, zone_type=ZoneType.MPA)
        port_zone = Zone(x=2, y=2, zone_type=ZoneType.PORT)
        shelf_zone = Zone(x=3, y=3, zone_type=ZoneType.SHELF)

        assert open_zone.is_fishing_allowed is True
        assert mpa_zone.is_fishing_allowed is False
        assert port_zone.is_fishing_allowed is False
        assert shelf_zone.is_fishing_allowed is True

    def test_distance_to_port_computed(self, rng: np.random.Generator) -> None:
        grid = OceanGrid.generate(nx=4, ny=4, mpa_fraction=0.1, n_ports=1, rng=rng)
        ports = grid.get_port_zones()
        assert len(ports) >= 1
        # Port itself has distance 0
        port = ports[0]
        assert grid.get_zone(port.x, port.y).distance_to_port == 0.0

    def test_get_mpa_zones(self, small_grid: OceanGrid) -> None:
        mpa = small_grid.get_mpa_zones()
        assert all(z.zone_type == ZoneType.MPA for z in mpa)

    def test_get_fishing_zones(self, small_grid: OceanGrid) -> None:
        fishing = small_grid.get_fishing_zones()
        assert all(z.is_fishing_allowed for z in fishing)
