"""Scenario configuration models for ReefWatch simulations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OceanConfig(BaseModel):
    """Spatial and oceanographic configuration."""

    n_zones_x: int = Field(default=8, ge=2, description="Grid width")
    n_zones_y: int = Field(default=8, ge=2, description="Grid height")
    mpa_fraction: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Fraction of zones designated MPA"
    )
    n_ports: int = Field(default=3, ge=1, description="Number of ports")
    sst_base: float = Field(default=26.0, description="Base SST in Celsius")
    sst_seasonal_amplitude: float = Field(default=3.0, ge=0.0)
    chlorophyll_base: float = Field(default=0.5, description="Base chlorophyll-a (mg/m^3)")


class FishStockConfig(BaseModel):
    """Fish stock dynamics (Schaefer logistic production model)."""

    n_species: int = Field(default=3, ge=1, le=10, description="Number of target species")
    carrying_capacity: float = Field(default=1000.0, gt=0.0, description="K per species")
    intrinsic_growth_rate: float = Field(default=0.3, gt=0.0, description="r parameter")
    catchability: float = Field(default=0.001, gt=0.0, description="q coefficient for CPUE")
    observation_noise_std: float = Field(
        default=0.2, ge=0.0, description="Log-normal obs noise for CPUE"
    )


class FleetConfig(BaseModel):
    """Fleet composition and behavior."""

    n_legal_vessels: int = Field(default=20, ge=1)
    n_gaming_vessels: int = Field(default=5, ge=0)
    n_iuu_vessels: int = Field(default=3, ge=0)
    enforcement_pressure: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Base enforcement probability"
    )
    underreport_fraction: float = Field(
        default=0.15, ge=0.0, le=1.0, description="IUU catch underreporting fraction"
    )


class SensorConfig(BaseModel):
    """Sensor/platform capabilities."""

    ais_update_interval: int = Field(default=1, ge=1, description="AIS epochs between updates")
    sar_revisit_interval: int = Field(
        default=8, ge=1, description="SAR satellite revisit in epochs (3h each)"
    )
    edna_sample_interval: int = Field(default=56, ge=1, description="eDNA sampling interval")
    em_review_rate: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Fraction of EM footage reviewed"
    )
    n_gliders: int = Field(default=2, ge=0)
    n_surface_vehicles: int = Field(default=1, ge=0)


class AdversaryConfig(BaseModel):
    """Adversarial behavior parameters."""

    ais_disable_probability: float = Field(
        default=0.7, ge=0.0, le=1.0, description="P(IUU disables AIS in MPA)"
    )
    spoof_probability: float = Field(
        default=0.3, ge=0.0, le=1.0, description="P(IUU spoofs position)"
    )
    platform_interference_rate: float = Field(
        default=0.05, ge=0.0, le=1.0, description="P(interference per platform per epoch)"
    )
    gaming_underreport_margin: float = Field(
        default=0.1, ge=0.0, le=0.5, description="Gaming vessel underreport fraction"
    )


class ScenarioConfig(BaseModel):
    """Top-level scenario configuration combining all sub-configs."""

    ocean: OceanConfig = Field(default_factory=OceanConfig)
    fish: FishStockConfig = Field(default_factory=FishStockConfig)
    fleet: FleetConfig = Field(default_factory=FleetConfig)
    sensors: SensorConfig = Field(default_factory=SensorConfig)
    adversary: AdversaryConfig = Field(default_factory=AdversaryConfig)
    total_epochs: int = Field(default=672, ge=1, description="Total simulation epochs (3h each)")
    seed: int = Field(default=42, description="Random seed for reproducibility")
    epoch_hours: float = Field(default=3.0, gt=0.0, description="Hours per epoch")
