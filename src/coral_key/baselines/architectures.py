"""Baseline comparator architectures (A0-A3) for ReefWatch falsification.

Each architecture uses a fundamentally different decision strategy:

A0: AIS-only, conservative threshold (cheapest — requires blatant multi-vessel evidence)
A1: AIS + SAR confirmation (corroboration lowers false alarms, improves detection)
A2: Multi-source OR (adds catch-anomaly as independent channel — catches gaming)
A3: Temporal evidence accumulator (fuses weak signals across a sliding window)

The BMA/TattleTots ecology must beat A3 on at least one metric at equal or lower cost,
or match A3 at significantly lower patrol cost.
"""

from __future__ import annotations

from collections import deque

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


class _BaseTracker:
    """Shared bookkeeping for detection/false-alarm tracking."""

    def __init__(self) -> None:
        self._detections = 0
        self._false_alarms = 0
        self._total_alerts = 0
        self._iuu_active_epochs = 0
        self._detected_epochs = 0
        self._latencies: list[int] = []
        self._epochs_since_iuu_start = 0
        self._iuu_was_active = False

    def _track_iuu_state(self, iuu_active: bool) -> None:
        if iuu_active:
            self._iuu_active_epochs += 1
            if not self._iuu_was_active:
                self._epochs_since_iuu_start = 0
            self._epochs_since_iuu_start += 1
            self._iuu_was_active = True
        else:
            self._iuu_was_active = False
            self._epochs_since_iuu_start = 0

    def _record_alert(self, iuu_active: bool) -> None:
        self._total_alerts += 1
        if iuu_active:
            self._detections += 1
            self._detected_epochs += 1
            self._latencies.append(self._epochs_since_iuu_start)
        else:
            self._false_alarms += 1

    def _build_result(self, name: str, patrol_cost_per_alert: float) -> BaselineResult:
        detection_rate = 0.0
        if self._iuu_active_epochs > 0:
            detection_rate = self._detected_epochs / self._iuu_active_epochs
        false_alarm_rate = 0.0
        if self._total_alerts > 0:
            false_alarm_rate = self._false_alarms / self._total_alerts
        return BaselineResult(
            architecture=name,
            iuu_detections=self._detections,
            false_alarms=self._false_alarms,
            total_alerts=self._total_alerts,
            detection_rate=detection_rate,
            false_alarm_rate=false_alarm_rate,
            patrol_cost=self._total_alerts * patrol_cost_per_alert,
            mean_detection_latency=(float(np.mean(self._latencies)) if self._latencies else 0.0),
        )


class BaselineA0(_BaseTracker):
    """A0: AIS-only surveillance with conservative threshold.

    Requires multiple simultaneous dark vessels to raise alert.
    Cheapest but lowest detection rate — only catches blatant multi-vessel AIS gaps.
    """

    def __init__(self, dark_vessel_threshold: int = 2) -> None:
        super().__init__()
        self._threshold = dark_vessel_threshold

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Alert only when dark vessel count is clearly anomalous (≥ threshold)."""
        self._track_iuu_state(iuu_active)
        alert = dark_vessels >= self._threshold
        if alert:
            self._record_alert(iuu_active)
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        return self._build_result("A0_AIS_only", patrol_cost_per_alert)


class BaselineA1(_BaseTracker):
    """A1: AIS + SAR cross-reference (corroboration strategy).

    Uses SAR to confirm AIS gaps: alerts on single dark vessel only when
    SAR also shows a discrepancy. Can also alert on strong AIS signal alone
    (≥ A0 threshold). Better precision than A0 at similar recall.
    """

    def __init__(
        self,
        strong_dark_threshold: int = 2,
        weak_dark_threshold: int = 1,
        sar_confirmation_threshold: int = 1,
    ) -> None:
        super().__init__()
        self._strong_thresh = strong_dark_threshold
        self._weak_thresh = weak_dark_threshold
        self._sar_thresh = sar_confirmation_threshold

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Alert on strong AIS signal OR (weak AIS + SAR confirmation)."""
        self._track_iuu_state(iuu_active)
        alert = dark_vessels >= self._strong_thresh or (
            dark_vessels >= self._weak_thresh and sar_discrepancies >= self._sar_thresh
        )
        if alert:
            self._record_alert(iuu_active)
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        return self._build_result("A1_AIS_SAR", patrol_cost_per_alert)


class BaselineA2(_BaseTracker):
    """A2: Multi-source with independent catch channel.

    Adds catch-anomaly as an independent detection channel. Can detect IUU/gaming
    even when AIS is enabled (no dark vessels). Three pathways to alert:
    1. Strong AIS signal (≥ blatant threshold)
    2. AIS + SAR confirmation (same as A1)
    3. Catch anomaly exceeds threshold (independent of vessel tracking)
    """

    def __init__(
        self,
        strong_dark_threshold: int = 2,
        weak_dark_threshold: int = 1,
        sar_confirmation_threshold: int = 1,
        catch_anomaly_threshold: float = 0.05,
    ) -> None:
        super().__init__()
        self._strong_thresh = strong_dark_threshold
        self._weak_thresh = weak_dark_threshold
        self._sar_thresh = sar_confirmation_threshold
        self._catch_thresh = catch_anomaly_threshold

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Alert on strong AIS OR (weak AIS + SAR) OR catch anomaly."""
        self._track_iuu_state(iuu_active)
        ais_strong = dark_vessels >= self._strong_thresh
        ais_sar_confirmed = (
            dark_vessels >= self._weak_thresh and sar_discrepancies >= self._sar_thresh
        )
        catch_alert = catch_anomaly >= self._catch_thresh
        alert = ais_strong or ais_sar_confirmed or catch_alert
        if alert:
            self._record_alert(iuu_active)
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        return self._build_result("A2_AIS_SAR_Catch", patrol_cost_per_alert)


class BaselineA3(_BaseTracker):
    """A3: Temporal evidence accumulator (sliding window fusion).

    Accumulates evidence across all modalities over a sliding window.
    Can detect persistent low-level IUU that no single epoch makes obvious.
    Most expensive but highest detection rate with managed false alarms.

    Decision: sum evidence weights over last `window_size` epochs.
    Alert when accumulated score exceeds `alert_threshold`.
    """

    def __init__(
        self,
        window_size: int = 4,
        alert_threshold: float = 1.0,
        dark_vessel_weight: float = 0.6,
        sar_weight: float = 0.4,
        catch_weight: float = 0.5,
        ocean_weight: float = 0.2,
    ) -> None:
        super().__init__()
        self._window_size = window_size
        self._alert_threshold = alert_threshold
        self._dark_w = dark_vessel_weight
        self._sar_w = sar_weight
        self._catch_w = catch_weight
        self._ocean_w = ocean_weight
        self._evidence_window: deque[float] = deque(maxlen=window_size)

    def process_epoch(
        self,
        dark_vessels: int,
        iuu_active: bool,
        *,
        sar_discrepancies: int = 0,
        catch_anomaly: float = 0.0,
        ocean_anomaly: float = 0.0,
    ) -> bool:
        """Accumulate evidence; alert when window sum exceeds threshold."""
        self._track_iuu_state(iuu_active)

        # Compute per-epoch evidence score
        epoch_score = 0.0
        if dark_vessels >= 1:
            epoch_score += self._dark_w * min(dark_vessels, 3)
        if sar_discrepancies >= 1:
            epoch_score += self._sar_w * min(sar_discrepancies, 3)
        if catch_anomaly > 0:
            epoch_score += self._catch_w * min(catch_anomaly / 0.15, 1.0)
        epoch_score += self._ocean_w * ocean_anomaly

        self._evidence_window.append(epoch_score)

        # Alert when accumulated evidence over window exceeds threshold
        window_sum = sum(self._evidence_window)
        alert = window_sum >= self._alert_threshold

        if alert:
            self._record_alert(iuu_active)
            # Partial reset to avoid re-alerting on same evidence
            self._evidence_window.clear()
        return alert

    def get_result(self, patrol_cost_per_alert: float = 50.0) -> BaselineResult:
        return self._build_result("A3_Full_Centralized", patrol_cost_per_alert)


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
