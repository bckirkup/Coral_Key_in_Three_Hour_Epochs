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
    def test_requires_multiple_dark_vessels(self) -> None:
        """A0 needs >= 2 dark vessels (conservative threshold)."""
        a0 = BaselineA0(dark_vessel_threshold=2)
        # Single dark vessel — not enough for A0
        assert a0.process_epoch(dark_vessels=1, iuu_active=True) is False
        # Two dark vessels — alert
        assert a0.process_epoch(dark_vessels=2, iuu_active=True) is True

    def test_detection_rate_reflects_conservatism(self) -> None:
        a0 = BaselineA0(dark_vessel_threshold=2)
        # 5 epochs with IUU: only 2 have >= 2 dark vessels
        a0.process_epoch(dark_vessels=1, iuu_active=True)
        a0.process_epoch(dark_vessels=2, iuu_active=True)
        a0.process_epoch(dark_vessels=1, iuu_active=True)
        a0.process_epoch(dark_vessels=3, iuu_active=True)
        a0.process_epoch(dark_vessels=0, iuu_active=True)
        result = a0.get_result()
        assert result.detection_rate == 2.0 / 5.0


class TestBaselineA1:
    def test_confirms_single_dark_with_sar(self) -> None:
        """A1 catches single dark vessel when SAR confirms."""
        a1 = BaselineA1()
        # Single dark, no SAR — no alert (unlike old A1)
        assert a1.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=0) is False
        # Single dark + SAR — alert
        assert a1.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=1) is True

    def test_strong_ais_alone_triggers(self) -> None:
        """A1 still alerts on strong AIS signal (>= 2) without SAR."""
        a1 = BaselineA1()
        assert a1.process_epoch(dark_vessels=2, iuu_active=True, sar_discrepancies=0) is True

    def test_beats_a0(self) -> None:
        """A1 should detect more than A0 when SAR provides confirmation."""
        a0 = BaselineA0()
        a1 = BaselineA1()
        # Epoch where only A1 detects (dark=1, sar=1)
        a0.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=1)
        a1.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=1)
        assert a0.get_result().detection_rate == 0.0
        assert a1.get_result().detection_rate == 1.0


class TestBaselineA2:
    def test_independent_catch_channel(self) -> None:
        """A2 detects via catch anomaly even without dark vessels or SAR."""
        a2 = BaselineA2()
        # No AIS/SAR signal but catch anomaly
        alert = a2.process_epoch(
            dark_vessels=0, iuu_active=True, sar_discrepancies=0, catch_anomaly=0.1
        )
        assert alert is True

    def test_inherits_a1_detection(self) -> None:
        """A2 still catches everything A1 catches."""
        a2 = BaselineA2()
        assert a2.process_epoch(dark_vessels=1, iuu_active=True, sar_discrepancies=1) is True
        assert a2.process_epoch(dark_vessels=2, iuu_active=True) is True


class TestBaselineA3:
    def test_accumulates_evidence(self) -> None:
        """A3 fires after accumulating weak signals over window."""
        a3 = BaselineA3(window_size=4, alert_threshold=1.0)
        # Single weak signal — not enough
        assert a3.process_epoch(dark_vessels=1, iuu_active=True) is False
        # Second weak signal — accumulates
        assert a3.process_epoch(dark_vessels=1, iuu_active=True) is True

    def test_catches_persistent_low_level_iuu(self) -> None:
        """A3 detects persistent catch anomaly that single-epoch detectors miss."""
        a3 = BaselineA3(window_size=4, alert_threshold=0.8)
        # Small catch anomaly each epoch — too weak for A2's threshold (0.05)
        a3.process_epoch(dark_vessels=0, iuu_active=True, catch_anomaly=0.03)
        a3.process_epoch(dark_vessels=0, iuu_active=True, catch_anomaly=0.03)
        a3.process_epoch(dark_vessels=0, iuu_active=True, catch_anomaly=0.03)
        # Adding one dark vessel pushes accumulated score over threshold
        alert = a3.process_epoch(dark_vessels=1, iuu_active=True, catch_anomaly=0.03)
        assert alert is True

    def test_window_reset_after_alert(self) -> None:
        """Evidence window resets after alert to avoid double-counting."""
        a3 = BaselineA3(window_size=3, alert_threshold=1.0)
        a3.process_epoch(dark_vessels=2, iuu_active=True)  # should alert
        # Next epoch with weak signal shouldn't alert (window cleared)
        assert a3.process_epoch(dark_vessels=0, iuu_active=True, catch_anomaly=0.01) is False


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

    def test_hierarchical_detection(self) -> None:
        """Higher architectures should achieve >= detection of lower ones."""
        # Scenario: mixed signals — some have dark vessels, some have SAR, some have catch
        metrics = []
        # Epochs where only A0 could detect (dark >= 2, no SAR)
        for _ in range(5):
            metrics.append(
                {
                    "dark_vessels_detected": 2,
                    "sar_ais_discrepancies": 0,
                    "iuu_vessels_active": 1,
                    "total_catch_actual": 50.0,
                    "total_catch_reported": 45.0,
                }
            )
        # Epochs where A1+ can detect (dark=1, SAR=1) but A0 can't
        for _ in range(5):
            metrics.append(
                {
                    "dark_vessels_detected": 1,
                    "sar_ais_discrepancies": 1,
                    "iuu_vessels_active": 1,
                    "total_catch_actual": 50.0,
                    "total_catch_reported": 42.0,
                }
            )
        # Epochs where A2+ catches via catch anomaly (no dark/SAR)
        for _ in range(5):
            metrics.append(
                {
                    "dark_vessels_detected": 0,
                    "sar_ais_discrepancies": 0,
                    "iuu_vessels_active": 1,
                    "total_catch_actual": 50.0,
                    "total_catch_reported": 40.0,
                }
            )
        # Non-IUU epochs
        for _ in range(5):
            metrics.append(
                {
                    "dark_vessels_detected": 0,
                    "sar_ais_discrepancies": 0,
                    "iuu_vessels_active": 0,
                    "total_catch_actual": 50.0,
                    "total_catch_reported": 50.0,
                }
            )

        results = run_baseline_comparison(metrics)
        a0 = results[0]
        a1 = results[1]
        a2 = results[2]

        # Strict hierarchy: A0 < A1 <= A2
        assert a1.detection_rate > a0.detection_rate
        assert a2.detection_rate >= a1.detection_rate
