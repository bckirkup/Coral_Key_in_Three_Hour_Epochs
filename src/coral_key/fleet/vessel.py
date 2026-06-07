"""Vessel models representing legal, gaming, and IUU fishing vessels."""

from __future__ import annotations

import enum
import uuid

import numpy as np
from pydantic import BaseModel, Field


class VesselType(enum.StrEnum):
    """Classification of vessel intent."""

    LEGAL = "legal"
    GAMING = "gaming"
    IUU = "iuu"


class VesselPosition(BaseModel):
    """Current spatial state of a vessel."""

    zone_x: int = Field(default=0, ge=0)
    zone_y: int = Field(default=0, ge=0)
    speed: float = Field(default=0.0, ge=0.0, description="Speed in knots")
    heading: float = Field(default=0.0, ge=0.0, lt=360.0, description="Heading in degrees")


class Vessel(BaseModel):
    """A fishing vessel with type, position, and operational state."""

    model_config = {"arbitrary_types_allowed": True}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vessel_type: VesselType = Field(default=VesselType.LEGAL)
    position: VesselPosition = Field(default_factory=VesselPosition)
    catch_this_epoch: np.ndarray = Field(
        default_factory=lambda: np.array([], dtype=np.float64),
        description="Catch per species this epoch",
    )
    total_catch: np.ndarray = Field(
        default_factory=lambda: np.array([], dtype=np.float64),
        description="Cumulative catch per species",
    )
    ais_enabled: bool = Field(default=True, description="Whether AIS transponder is active")
    reported_position: VesselPosition | None = Field(
        default=None, description="Position reported via AIS (may be spoofed)"
    )
    at_port: bool = Field(default=True, description="Whether vessel is currently at port")
    trip_duration: int = Field(default=0, ge=0, description="Epochs since last port departure")

    def depart_port(self, target_x: int, target_y: int) -> None:
        """Leave port and head to fishing grounds."""
        self.at_port = False
        self.trip_duration = 0
        self.position.zone_x = target_x
        self.position.zone_y = target_y

    def return_to_port(self, port_x: int, port_y: int) -> None:
        """Return to port, ending fishing trip."""
        self.at_port = True
        self.position.zone_x = port_x
        self.position.zone_y = port_y
        self.trip_duration = 0

    def record_catch(self, species_catches: np.ndarray) -> None:
        """Record catch from this epoch."""
        if self.catch_this_epoch.size == 0:
            self.catch_this_epoch = species_catches.copy()
            self.total_catch = species_catches.copy()
        else:
            self.catch_this_epoch = species_catches.copy()
            self.total_catch = self.total_catch + species_catches
