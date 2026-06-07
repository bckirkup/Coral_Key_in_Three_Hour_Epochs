"""Spatial grid of ocean zones with habitat types and jurisdictions."""

from __future__ import annotations

import enum

import numpy as np
from pydantic import BaseModel, Field


class ZoneType(enum.StrEnum):
    """Zone classification."""

    OPEN = "open"
    MPA = "mpa"
    PORT = "port"
    SHELF = "shelf"


class Zone(BaseModel):
    """A single spatial zone in the ocean grid."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    zone_type: ZoneType = Field(default=ZoneType.OPEN)
    depth: float = Field(default=50.0, ge=0.0, description="Depth in meters")
    distance_to_port: float = Field(default=10.0, ge=0.0, description="Distance to nearest port")
    habitat_quality: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Habitat suitability index"
    )

    @property
    def is_fishing_allowed(self) -> bool:
        """Legal fishing is allowed in OPEN and SHELF zones."""
        return self.zone_type in (ZoneType.OPEN, ZoneType.SHELF)


class OceanGrid(BaseModel):
    """2D grid of ocean zones with MPA designations and ports."""

    model_config = {"arbitrary_types_allowed": True}

    nx: int = Field(ge=2)
    ny: int = Field(ge=2)
    zones: list[Zone] = Field(default_factory=list)

    @classmethod
    def generate(
        cls,
        nx: int,
        ny: int,
        mpa_fraction: float,
        n_ports: int,
        rng: np.random.Generator,
    ) -> OceanGrid:
        """Generate a grid with random MPA placement and ports."""
        total = nx * ny
        n_mpa = max(1, int(total * mpa_fraction))
        n_ports_actual = min(n_ports, total - n_mpa)

        indices = np.arange(total)
        rng.shuffle(indices)
        mpa_indices = set(indices[:n_mpa].tolist())
        port_indices = set(indices[n_mpa : n_mpa + n_ports_actual].tolist())

        zones: list[Zone] = []
        for idx in range(total):
            x, y = idx % nx, idx // nx
            if idx in mpa_indices:
                zone_type = ZoneType.MPA
            elif idx in port_indices:
                zone_type = ZoneType.PORT
            else:
                zone_type = ZoneType.OPEN

            depth = float(rng.uniform(10.0, 200.0))
            habitat_quality = float(rng.uniform(0.2, 1.0))
            zones.append(
                Zone(
                    x=x,
                    y=y,
                    zone_type=zone_type,
                    depth=depth,
                    habitat_quality=habitat_quality,
                )
            )

        # Compute distance to nearest port for each zone
        port_coords = [(z.x, z.y) for z in zones if z.zone_type == ZoneType.PORT]
        for zone in zones:
            if port_coords:
                dists = [np.sqrt((zone.x - px) ** 2 + (zone.y - py) ** 2) for px, py in port_coords]
                zone.distance_to_port = float(min(dists))
            else:
                zone.distance_to_port = float(nx + ny)

        return cls(nx=nx, ny=ny, zones=zones)

    def get_zone(self, x: int, y: int) -> Zone:
        """Look up a zone by coordinates."""
        idx = y * self.nx + x
        return self.zones[idx]

    def get_mpa_zones(self) -> list[Zone]:
        """Return all MPA zones."""
        return [z for z in self.zones if z.zone_type == ZoneType.MPA]

    def get_fishing_zones(self) -> list[Zone]:
        """Return all zones where legal fishing is allowed."""
        return [z for z in self.zones if z.is_fishing_allowed]

    def get_port_zones(self) -> list[Zone]:
        """Return port zones."""
        return [z for z in self.zones if z.zone_type == ZoneType.PORT]
