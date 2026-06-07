"""Baseline comparator architectures (A0-A3) for ReefWatch falsification.

A0: AIS-only surveillance (cheapest, lowest capability)
A1: AIS + SAR fusion (adds satellite dark-vessel detection)
A2: AIS + SAR + Catch reports (adds reported-catch anomaly detection)
A3: Full centralized fusion (AIS + SAR + catch + oceanographic) — the system to beat

The BMA/TattleTots ecology must beat A3 on at least one metric at equal or lower cost,
or match A3 at significantly lower patrol cost.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field


class BaselineResult(BaseModel):
    """Results from running a baseline architecture on ReefWatch sensor data."""

    architecture: str
    iuu_detections: int = Field(default=0, ge=0)
    false_alarms: int = Field(default=0, ge=0)
    total_alerts: int = Field(default=0, ge=0)
    detection_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    false_alarm_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    patrol_cost: float = Field(default=0.0, ge=0.0)
    stock_estimate_error: float = Field(default=0.0, ge=0.0)
    mean_detection_latency: float = Field(default=0.0, ge=0.0)


class BaselineA0:
    """A0: AIS-only surveillance.

    Detects IUU by flagging dark vessels (AIS gaps).
    Cheapest architecture, but blind to AIS-spoofing and off-grid fishing.
    """

    def __init__(self, dark_vessel_threshold: int = 1) -> None:
        self._threshold = dark_vessel_threshold
        self._detections = 0
        self._false_alarms = 0
        self._total_alerts = 0
        self._iuu_active_epochs = 0
        self._detected_epochs = 0
        self._latencies: list[int] = []
        self._epochs_since_iuu_start = 0
        self._iuu_was_active = False

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Process one epoch. Returns True if alert raised."""
        if iuu_active:
            self._iuu_active_epochs += 1
            if not self._iuu_was_active:
                self._epochs_since_iuu_start = 0
            self._epochs_since_iuu_start += 1
            self._iuu_was_active = True
        else:
            self._iuu_was_active = False
            self._epochs_since_iuu_start = 0

        alert = dark_vessels >= self._threshold
        if alert:
            self._total_alerts += 1
            if iuu_active:
                self._detections += 1
                self._detected_epochs += 1
                self._latencies.append(self._epochs_since_iuu_start)
            else:
                self._false_alarms += 1
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        """Compute final baseline metrics."""
        detection_rate = 0.0
        if self._iuu_active_epochs > 0:
            detection_rate = self._detected_epochs / self._iuu_active_epochs
        false_alarm_rate = 0.0
        if self._total_alerts > 0:
            false_alarm_rate = self._false_alarms / self._total_alerts

        return BaselineResult(
            architecture="A0_AIS_only",
            iuu_detections=self._detections,
            false_alarms=self._false_alarms,
            total_alerts=self._total_alerts,
            detection_rate=detection_rate,
            false_alarm_rate=false_alarm_rate,
            patrol_cost=self._total_alerts * patrol_cost_per_alert,
            mean_detection_latency=float(np.mean(self._latencies)) if self._latencies else 0.0,
        )


class BaselineA1:
    """A1: AIS + SAR fusion.

    Combines AIS dark-vessel detection with SAR satellite cross-referencing.
    Better at detecting AIS-disabled vessels via SAR confirmation.
    """

    def __init__(
        self,
        dark_vessel_threshold: int = 1,
        sar_discrepancy_threshold: int = 1,
    ) -> None:
        self._dark_thresh = dark_vessel_threshold
        self._sar_thresh = sar_discrepancy_threshold
        self._detections = 0
        self._false_alarms = 0
        self._total_alerts = 0
        self._iuu_active_epochs = 0
        self._detected_epochs = 0
        self._latencies: list[int] = []
        self._epochs_since_iuu_start = 0
        self._iuu_was_active = False

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Process one epoch. Alerts on AIS dark OR SAR discrepancy."""
        if iuu_active:
            self._iuu_active_epochs += 1
            if not self._iuu_was_active:
                self._epochs_since_iuu_start = 0
            self._epochs_since_iuu_start += 1
            self._iuu_was_active = True
        else:
            self._iuu_was_active = False
            self._epochs_since_iuu_start = 0

        alert = dark_vessels >= self._dark_thresh or sar_discrepancies >= self._sar_thresh
        if alert:
            self._total_alerts += 1
            if iuu_active:
                self._detections += 1
                self._detected_epochs += 1
                self._latencies.append(self._epochs_since_iuu_start)
            else:
                self._false_alarms += 1
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        detection_rate = 0.0
        if self._iuu_active_epochs > 0:
            detection_rate = self._detected_epochs / self._iuu_active_epochs
        false_alarm_rate = 0.0
        if self._total_alerts > 0:
            false_alarm_rate = self._false_alarms / self._total_alerts

        return BaselineResult(
            architecture="A1_AIS_SAR",
            iuu_detections=self._detections,
            false_alarms=self._false_alarms,
            total_alerts=self._total_alerts,
            detection_rate=detection_rate,
            false_alarm_rate=false_alarm_rate,
            patrol_cost=self._total_alerts * patrol_cost_per_alert,
            mean_detection_latency=float(np.mean(self._latencies)) if self._latencies else 0.0,
        )


class BaselineA2:
    """A2: AIS + SAR + Catch reports.

    Adds catch underreporting detection to A1's vessel-tracking capabilities.
    Detects gaming/IUU through discrepancies in reported catch vs expected.
    """

    def __init__(
        self,
        dark_vessel_threshold: int = 1,
        sar_discrepancy_threshold: int = 1,
        catch_anomaly_threshold: float = 0.1,
    ) -> None:
        self._dark_thresh = dark_vessel_threshold
        self._sar_thresh = sar_discrepancy_threshold
        self._catch_thresh = catch_anomaly_threshold
        self._detections = 0
        self._false_alarms = 0
        self._total_alerts = 0
        self._iuu_active_epochs = 0
        self._detected_epochs = 0
        self._latencies: list[int] = []
        self._epochs_since_iuu_start = 0
        self._iuu_was_active = False

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Alert on AIS dark OR SAR discrepancy OR catch anomaly."""
        if iuu_active:
            self._iuu_active_epochs += 1
            if not self._iuu_was_active:
                self._epochs_since_iuu_start = 0
            self._epochs_since_iuu_start += 1
            self._iuu_was_active = True
        else:
            self._iuu_was_active = False
            self._epochs_since_iuu_start = 0

        alert = (
            dark_vessels >= self._dark_thresh
            or sar_discrepancies >= self._sar_thresh
            or catch_anomaly >= self._catch_thresh
        )
        if alert:
            self._total_alerts += 1
            if iuu_active:
                self._detections += 1
                self._detected_epochs += 1
                self._latencies.append(self._epochs_since_iuu_start)
            else:
                self._false_alarms += 1
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        detection_rate = 0.0
        if self._iuu_active_epochs > 0:
            detection_rate = self._detected_epochs / self._iuu_active_epochs
        false_alarm_rate = 0.0
        if self._total_alerts > 0:
            false_alarm_rate = self._false_alarms / self._total_alerts

        return BaselineResult(
            architecture="A2_AIS_SAR_Catch",
            iuu_detections=self._detections,
            false_alarms=self._false_alarms,
            total_alerts=self._total_alerts,
            detection_rate=detection_rate,
            false_alarm_rate=false_alarm_rate,
            patrol_cost=self._total_alerts * patrol_cost_per_alert,
            mean_detection_latency=float(np.mean(self._latencies)) if self._latencies else 0.0,
        )


class BaselineA3:
    """A3: Full centralized fusion (AIS + SAR + Catch + Oceanographic).

    The architecture to beat. Combines all non-BMA sensor modalities with
    threshold-based fusion. Uses oceanographic context (habitat suitability)
    to weight detection probability.
    """

    def __init__(
        self,
        dark_vessel_threshold: int = 1,
        sar_discrepancy_threshold: int = 1,
        catch_anomaly_threshold: float = 0.08,
        ocean_anomaly_weight: float = 0.3,
    ) -> None:
        self._dark_thresh = dark_vessel_threshold
        self._sar_thresh = sar_discrepancy_threshold
        self._catch_thresh = catch_anomaly_threshold
        self._ocean_weight = ocean_anomaly_weight
        self._detections = 0
        self._false_alarms = 0
        self._total_alerts = 0
        self._iuu_active_epochs = 0
        self._detected_epochs = 0
        self._latencies: list[int] = []
        self._epochs_since_iuu_start = 0
        self._iuu_was_active = False
        # Stock assessment: running CPUE estimate
        self._cpue_estimates: list[float] = []

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Fused alert: any single modality OR weighted combination exceeds threshold."""
        if iuu_active:
            self._iuu_active_epochs += 1
            if not self._iuu_was_active:
                self._epochs_since_iuu_start = 0
            self._epochs_since_iuu_start += 1
            self._iuu_was_active = True
        else:
            self._iuu_was_active = False
            self._epochs_since_iuu_start = 0

        # Composite score: weighted sum of normalized indicators
        score = 0.0
        if dark_vessels >= self._dark_thresh:
            score += 0.4
        if sar_discrepancies >= self._sar_thresh:
            score += 0.3
        if catch_anomaly >= self._catch_thresh:
            score += 0.2
        score += self._ocean_weight * ocean_anomaly

        # Alert if any strong signal OR composite exceeds threshold
        alert = score >= 0.3

        if alert:
            self._total_alerts += 1
            if iuu_active:
                self._detections += 1
                self._detected_epochs += 1
                self._latencies.append(self._epochs_since_iuu_start)
            else:
                self._false_alarms += 1
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        detection_rate = 0.0
        if self._iuu_active_epochs > 0:
            detection_rate = self._detected_epochs / self._iuu_active_epochs
        false_alarm_rate = 0.0
        if self._total_alerts > 0:
            false_alarm_rate = self._false_alarms / self._total_alerts

        return BaselineResult(
            architecture="A3_Full_Centralized",
            iuu_detections=self._detections,
            false_alarms=self._false_alarms,
            total_alerts=self._total_alerts,
            detection_rate=detection_rate,
            false_alarm_rate=false_alarm_rate,
            patrol_cost=self._total_alerts * patrol_cost_per_alert,
            mean_detection_latency=float(np.mean(self._latencies)) if self._latencies else 0.0,
        )


def run_baseline_comparison(
    epoch_metrics: list[dict[str, object]],
    patrol_cost_per_alert: float = 50.0,
) -> list[BaselineResult]:
    """Run all baseline architectures on recorded epoch metrics.

    Args:
        epoch_metrics: List of dicts with keys:
            dark_vessels_detected, sar_ais_discrepancies, iuu_vessels_active,
            total_catch_actual, total_catch_reported
        patrol_cost_per_alert: Cost per patrol sortie.

    Returns:
        List of BaselineResult, one per architecture (A0 through A3).
    """
    a0 = BaselineA0()
    a1 = BaselineA1()
    a2 = BaselineA2()
    a3 = BaselineA3()

    for m in epoch_metrics:
        dark = int(str(m.get("dark_vessels_detected", 0)))
        iuu_active = int(str(m.get("iuu_vessels_active", 0))) > 0
        sar_disc = int(str(m.get("sar_ais_discrepancies", 0)))

        actual = float(str(m.get("total_catch_actual", 0.0)))
        reported = float(str(m.get("total_catch_reported", 0.0)))
        catch_anomaly = (actual - reported) / actual if actual > 0 else 0.0

        for baseline in (a0, a1, a2, a3):
            baseline.process_epoch(
                dark_vessels=dark,
                iuu_active=iuu_active,
                sar_discrepancies=sar_disc,
                catch_anomaly=catch_anomaly,
            )

    return [
        a0.get_result(patrol_cost_per_alert),
        a1.get_result(patrol_cost_per_alert),
        a2.get_result(patrol_cost_per_alert),
        a3.get_result(patrol_cost_per_alert),
    ]
