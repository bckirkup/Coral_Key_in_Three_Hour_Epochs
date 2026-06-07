"""Catch report stream: self-reported catch data with potential falsification."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel, VesselType


class CatchReportStream:
    """Generates catch report observation vectors.

    Aggregates reported catch per species. Legal vessels report honestly,
    gaming vessels underreport slightly, IUU vessels heavily underreport.
    """

    def __init__(
        self,
        n_species: int,
        underreport_fraction_iuu: float = 0.15,
        underreport_fraction_gaming: float = 0.1,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._n_species = n_species
        self._underreport_iuu = underreport_fraction_iuu
        self._underreport_gaming = underreport_fraction_gaming
        self._rng = rng or np.random.default_rng()

    @property
    def dimensionality(self) -> int:
        return self._n_species

    @property
    def label(self) -> str:
        return "catch_reports"

    def observe(self, vessels: list[Vessel]) -> np.ndarray:
        """Generate catch report observation: reported catch per species.

        Returns array of shape (n_species,).
        """
        reported = np.zeros(self._n_species)
        for vessel in vessels:
            if vessel.catch_this_epoch.size == 0:
                continue
            catch = vessel.catch_this_epoch[: self._n_species]
            if vessel.vessel_type == VesselType.IUU:
                # IUU heavily underreports
                noise = self._rng.uniform(0.0, self._underreport_iuu, len(catch))
                reported[: len(catch)] += catch * (1.0 - self._underreport_iuu - noise)
            elif vessel.vessel_type == VesselType.GAMING:
                noise = self._rng.uniform(0.0, self._underreport_gaming / 2, len(catch))
                reported[: len(catch)] += catch * (1.0 - self._underreport_gaming + noise)
            else:
                # Small random reporting error for legal vessels
                noise = self._rng.normal(0, 0.02, len(catch))
                reported[: len(catch)] += catch * (1.0 + noise)

        return np.clip(reported, 0.0, None)

    def compute_underreport_ratio(
        self,
        reported: np.ndarray,
        actual: np.ndarray,
    ) -> np.ndarray:
        """Compute underreporting ratio per species (actual - reported) / actual."""
        safe_actual = np.where(actual > 0, actual, 1.0)
        result: np.ndarray = np.clip((actual - reported) / safe_actual, 0.0, 1.0)
        return result
