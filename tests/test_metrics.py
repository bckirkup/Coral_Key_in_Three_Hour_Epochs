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

    def test_escalation_tracking(self) -> None:
        collector = MetricsCollector(n_species=1)
        collector.record_escalation(correct=True)
        collector.record_escalation(correct=True)
        collector.record_escalation(correct=False)

        biomass = np.array([500.0])
        bmsy = np.array([500.0])
        result = collector.compute_cumulative(biomass, bmsy)
        assert result.false_boarding_rate == 1.0 / 3.0
