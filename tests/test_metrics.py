"""Tests for metrics collection."""

from __future__ import annotations

import numpy as np

from coral_key.metrics import CumulativeMetrics, EpochMetrics, MetricsCollector


class TestEpochMetrics:
    def test_construction(self) -> None:
        m = EpochMetrics(epoch=5, iuu_vessels_active=2, mpa_violations=1)
        assert m.epoch == 5
        assert m.iuu_vessels_active == 2


class TestMetricsCollector:
    def test_record_and_compute(self) -> None:
        collector = MetricsCollector(n_species=2)

        for i in range(10):
            collector.record_epoch(EpochMetrics(epoch=i, iuu_vessels_active=1 if i % 2 == 0 else 0))
            collector.record_catch(
                actual=np.array([10.0, 5.0]),
                reported=np.array([8.0, 4.0]),
            )

        biomass = np.array([400.0, 600.0])
        bmsy = np.array([500.0, 500.0])
        result = collector.compute_cumulative(biomass, bmsy)

        assert isinstance(result, CumulativeMetrics)
        assert result.biomass_relative_to_bmsy > 0
        assert result.stock_assessment_error >= 0
        assert result.catch_underreporting_detection >= 0

    def test_iuu_detection_wiring(self) -> None:
        """IUU is detected when dark vessels or SAR discrepancies appear during IUU epochs."""
        collector = MetricsCollector(n_species=1)

        # Epoch with IUU active + dark vessel = detection
        collector.record_epoch(EpochMetrics(epoch=0, iuu_vessels_active=2, dark_vessels_detected=1))
        # Epoch with IUU active but no detection signal
        collector.record_epoch(EpochMetrics(epoch=1, iuu_vessels_active=1, dark_vessels_detected=0))
        # Epoch with IUU + SAR discrepancy = detection
        collector.record_epoch(EpochMetrics(epoch=2, iuu_vessels_active=1, sar_ais_discrepancies=2))

        result = collector.compute_cumulative(np.array([500.0]), np.array([500.0]))
        # 3 IUU-active epochs, 2 detected
        assert result.iuu_detection_rate == 2.0 / 3.0

    def test_biomass_estimate_tracking(self) -> None:
        """Stock assessment error uses recorded estimates vs actuals."""
        collector = MetricsCollector(n_species=2)

        # Perfect estimates: error should be ~0
        for _ in range(5):
            collector.record_biomass_estimate(
                estimated=np.array([500.0, 400.0]),
                actual=np.array([500.0, 400.0]),
            )

        result = collector.compute_cumulative(np.array([500.0, 400.0]), np.array([500.0, 500.0]))
        assert result.stock_assessment_error < 0.01

    def test_biomass_estimate_with_error(self) -> None:
        """Noisy estimates produce non-zero stock assessment error."""
        collector = MetricsCollector(n_species=1)

        collector.record_biomass_estimate(
            estimated=np.array([600.0]),
            actual=np.array([500.0]),
        )

        result = collector.compute_cumulative(np.array([500.0]), np.array([250.0]))
        # Error = |600-500|/500 = 0.2
        assert abs(result.stock_assessment_error - 0.2) < 0.01

    def test_escalation_tracking(self) -> None:
        collector = MetricsCollector(n_species=1)
        collector.record_escalation(correct=True)
        collector.record_escalation(correct=True)
        collector.record_escalation(correct=False)

        biomass = np.array([500.0])
        bmsy = np.array([500.0])
        result = collector.compute_cumulative(biomass, bmsy)
        assert result.false_boarding_rate == 1.0 / 3.0
