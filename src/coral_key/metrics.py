"""Domain-specific metrics for ReefWatch fishery monitoring."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field


class EpochMetrics(BaseModel):
    """Metrics recorded at each epoch."""

    epoch: int = Field(ge=0)
    iuu_vessels_active: int = Field(default=0, ge=0)
    mpa_violations: int = Field(default=0, ge=0)
    dark_vessels_detected: int = Field(default=0, ge=0)
    sar_ais_discrepancies: int = Field(default=0, ge=0)
    total_catch_actual: float = Field(default=0.0, ge=0.0)
    total_catch_reported: float = Field(default=0.0, ge=0.0)
    platform_interference_events: int = Field(default=0, ge=0)


class CumulativeMetrics(BaseModel):
    """Cumulative metrics for scoring the simulation run."""

    model_config = {"arbitrary_types_allowed": True}

    iuu_detection_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    false_boarding_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    patrol_cost: float = Field(default=0.0, ge=0.0)
    dark_vessel_detection_latency: float = Field(default=0.0, ge=0.0)
    catch_underreporting_detection: float = Field(default=0.0, ge=0.0, le=1.0)
    stock_assessment_error: float = Field(default=0.0, ge=0.0)
    biomass_relative_to_bmsy: float = Field(default=1.0, ge=0.0)
    economic_loss_to_iuu: float = Field(default=0.0, ge=0.0)
    total_responses_judged_necessary: int = Field(default=0, ge=0)
    total_responses_judged_unnecessary: int = Field(default=0, ge=0)
    unnecessary_boarding_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class MetricsCollector:
    """Collects and computes domain metrics over the simulation."""

    def __init__(self, n_species: int) -> None:
        self._n_species = n_species
        self._epoch_history: list[EpochMetrics] = []
        self._iuu_active_epochs: int = 0
        self._iuu_detected_epochs: int = 0
        self._total_escalations: int = 0
        self._correct_escalations: int = 0
        self._false_escalations: int = 0
        self._responses_judged_necessary: int = 0
        self._responses_judged_unnecessary: int = 0
        self._responses_dispatched: int = 0
        self._total_actual_catch = np.zeros(n_species)
        self._total_reported_catch = np.zeros(n_species)
        self._biomass_estimates: list[np.ndarray] = []
        self._biomass_actuals: list[np.ndarray] = []

    def record_epoch(self, metrics: EpochMetrics) -> None:
        """Record a single epoch's metrics.

        IUU is considered "detected" if dark vessels or SAR-AIS discrepancies
        were observed in this epoch.
        """
        self._epoch_history.append(metrics)
        if metrics.iuu_vessels_active > 0:
            self._iuu_active_epochs += 1
        # Detection: dark vessels found or SAR-AIS discrepancies while IUU was active
        if metrics.iuu_vessels_active > 0 and (
            metrics.dark_vessels_detected > 0 or metrics.sar_ais_discrepancies > 0
        ):
            self._iuu_detected_epochs += 1

    def record_escalation(self, *, correct: bool) -> None:
        """Record an escalation event."""
        self._total_escalations += 1
        if correct:
            self._correct_escalations += 1
        else:
            self._false_escalations += 1

    def record_response_outcomes(
        self,
        *,
        dispatched: int,
        judged_necessary: int,
        judged_unnecessary: int,
    ) -> None:
        """Record post-dispatch patrol judgments."""
        self._responses_dispatched += dispatched
        self._responses_judged_necessary += judged_necessary
        self._responses_judged_unnecessary += judged_unnecessary

    def record_catch(self, actual: np.ndarray, reported: np.ndarray) -> None:
        """Record actual vs reported catch."""
        self._total_actual_catch += actual[: self._n_species]
        self._total_reported_catch += reported[: self._n_species]

    def record_biomass_estimate(self, estimated: np.ndarray, actual: np.ndarray) -> None:
        """Record biomass estimate vs actual for stock assessment error."""
        self._biomass_estimates.append(estimated.copy())
        self._biomass_actuals.append(actual.copy())

    def compute_cumulative(
        self,
        final_biomass: np.ndarray,
        bmsy: np.ndarray,
    ) -> CumulativeMetrics:
        """Compute final cumulative metrics."""
        iuu_detection_rate = 0.0
        if self._iuu_active_epochs > 0:
            iuu_detection_rate = self._iuu_detected_epochs / self._iuu_active_epochs

        false_boarding_rate = 0.0
        if self._total_escalations > 0:
            false_boarding_rate = self._false_escalations / self._total_escalations

        unnecessary_boarding_rate = 0.0
        if self._responses_dispatched > 0:
            unnecessary_boarding_rate = (
                self._responses_judged_unnecessary / self._responses_dispatched
            )

        catch_detection = 0.0
        actual_sum = self._total_actual_catch.sum()
        reported_sum = self._total_reported_catch.sum()
        if actual_sum > 0:
            underreport = (actual_sum - reported_sum) / actual_sum
            catch_detection = min(1.0, underreport)

        # Stock assessment error: mean absolute relative error of estimates vs actuals
        if self._biomass_estimates:
            estimates = np.array(self._biomass_estimates)
            actuals = np.array(self._biomass_actuals)
            safe_actuals = np.where(actuals > 0, actuals, 1.0)
            stock_error = float(np.mean(np.abs(estimates - actuals) / safe_actuals))
        else:
            # Fallback: no estimates recorded, use final biomass vs BMSY
            safe_bmsy = np.where(bmsy > 0, bmsy, 1.0)
            stock_error = float(np.mean(np.abs(final_biomass - safe_bmsy) / safe_bmsy))

        # Biomass relative to BMSY
        safe_bmsy = np.where(bmsy > 0, bmsy, 1.0)
        biomass_ratio = float(np.mean(final_biomass / safe_bmsy))

        # Economic loss: catch from IUU relative to total
        iuu_catch_fraction = 0.0
        if actual_sum > 0 and reported_sum > 0:
            iuu_catch_fraction = max(0.0, (actual_sum - reported_sum) / actual_sum)

        return CumulativeMetrics(
            iuu_detection_rate=iuu_detection_rate,
            false_boarding_rate=false_boarding_rate,
            unnecessary_boarding_rate=unnecessary_boarding_rate,
            total_responses_judged_necessary=self._responses_judged_necessary,
            total_responses_judged_unnecessary=self._responses_judged_unnecessary,
            patrol_cost=float(self._total_escalations) * 10.0,
            catch_underreporting_detection=catch_detection,
            stock_assessment_error=stock_error,
            biomass_relative_to_bmsy=biomass_ratio,
            economic_loss_to_iuu=iuu_catch_fraction * actual_sum,
        )

    @property
    def epoch_history(self) -> list[EpochMetrics]:
        return self._epoch_history
