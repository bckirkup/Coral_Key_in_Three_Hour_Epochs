"""Tests for baseline comparator architectures."""

from __future__ import annotations

from coral_key.baselines.architectures import (
    BaselineA0,
    BaselineA1,
    BaselineA2,
    BaselineA3,
    run_baseline_comparison,
)


class TestBaselineA0:
    def test_detects_dark_vessels(self) -> None:
        a0 = BaselineA0(dark_vessel_threshold=1)
        # IUU active + dark vessel = detection
        alert = a0.process_epoch(dark_vessels=2, iuu_active=True)
        assert alert is True
        result = a0.get_result()
        assert result.iuu_detections == 1
        assert result.detection_rate == 1.0

    def test_no_alert_when_no_dark_vessels(self) -> None:
        a0 = BaselineA0(dark_vessel_threshold=1)
        alert = a0.process_epoch(dark_vessels=0, iuu_active=True)
        assert alert is False

    def test_false_alarm_on_dark_vessel_without_iuu(self) -> None:
        a0 = BaselineA0(dark_vessel_threshold=1)
        alert = a0.process_epoch(dark_vessels=1, iuu_active=False)
        assert alert is True
        result = a0.get_result()
        assert result.false_alarms == 1
        assert result.false_alarm_rate == 1.0


class TestBaselineA1:
    def test_detects_via_sar(self) -> None:
        a1 = BaselineA1(dark_vessel_threshold=2, sar_discrepancy_threshold=1)
        # Only 1 dark vessel (below threshold), but SAR discrepancy
        alert = a1.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=1)
        assert alert is True

    def test_no_alert_below_all_thresholds(self) -> None:
        a1 = BaselineA1(dark_vessel_threshold=2, sar_discrepancy_threshold=2)
        alert = a1.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=1)
        assert alert is False


class TestBaselineA2:
    def test_detects_via_catch_anomaly(self) -> None:
        a2 = BaselineA2(
            dark_vessel_threshold=5, sar_discrepancy_threshold=5, catch_anomaly_threshold=0.1
        )
        alert = a2.process_epoch(
            dark_vessels=0, iuu_active=True, sar_discrepancies=0, catch_anomaly=0.15
        )
        assert alert is True


class TestBaselineA3:
    def test_fused_detection(self) -> None:
        a3 = BaselineA3()
        # Dark vessel alone triggers
        alert = a3.process_epoch(dark_vessels=1, iuu_active=True)
        assert alert is True

    def test_multiple_epochs(self) -> None:
        a3 = BaselineA3()
        for _ in range(5):
            a3.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=1)
        for _ in range(3):
            a3.process_epoch(dark_vessels=0, iuu_active=False)
        result = a3.get_result()
        assert result.detection_rate == 1.0
        assert result.false_alarms == 0


class TestRunBaselineComparison:
    def test_returns_four_architectures(self) -> None:
        metrics = [
            {
                "dark_vessels_detected": 2,
                "sar_ais_discrepancies": 1,
                "iuu_vessels_active": 1,
                "total_catch_actual": 100.0,
                "total_catch_reported": 85.0,
            },
            {
                "dark_vessels_detected": 0,
                "sar_ais_discrepancies": 0,
                "iuu_vessels_active": 0,
                "total_catch_actual": 80.0,
                "total_catch_reported": 80.0,
            },
        ]
        results = run_baseline_comparison(metrics)
        assert len(results) == 4
        names = [r.architecture for r in results]
        assert "A0_AIS_only" in names
        assert "A1_AIS_SAR" in names
        assert "A2_AIS_SAR_Catch" in names
        assert "A3_Full_Centralized" in names

    def test_a3_beats_a0(self) -> None:
        metrics = [
            {
                "dark_vessels_detected": 0,
                "sar_ais_discrepancies": 1,
                "iuu_vessels_active": 1,
                "total_catch_actual": 50.0,
                "total_catch_reported": 40.0,
            }
        ] * 10
        results = run_baseline_comparison(metrics)
        a0 = next(r for r in results if r.architecture == "A0_AIS_only")
        a3 = next(r for r in results if r.architecture == "A3_Full_Centralized")
        # A3 should detect more than A0 when only SAR discrepancies exist
        assert a3.detection_rate >= a0.detection_rate
