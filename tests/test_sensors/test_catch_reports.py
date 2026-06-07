"""Tests for catch report stream."""

from __future__ import annotations

import numpy as np

from coral_key.fleet.vessel import Vessel, VesselType
from coral_key.sensors.catch_reports import CatchReportStream


class TestCatchReportStream:
    def test_dimensionality(self) -> None:
        stream = CatchReportStream(n_species=3)
        assert stream.dimensionality == 3

    def test_legal_vessel_reports_honestly(self, rng: np.random.Generator) -> None:
        stream = CatchReportStream(n_species=2, rng=rng)
        vessel = Vessel(
            vessel_type=VesselType.LEGAL,
            catch_this_epoch=np.array([10.0, 5.0]),
            at_port=False,
        )
        reported = stream.observe([vessel])
        # Legal reports are very close to actual (small noise)
        assert reported.shape == (2,)
        assert abs(reported[0] - 10.0) < 3.0
        assert abs(reported[1] - 5.0) < 3.0

    def test_iuu_underreports(self, rng: np.random.Generator) -> None:
        stream = CatchReportStream(n_species=2, underreport_fraction_iuu=0.5, rng=rng)
        vessel = Vessel(
            vessel_type=VesselType.IUU,
            catch_this_epoch=np.array([100.0, 50.0]),
            at_port=False,
        )
        reported = stream.observe([vessel])
        # Should be significantly less than actual
        assert reported[0] < 80.0
        assert reported[1] < 40.0

    def test_underreport_ratio(self) -> None:
        stream = CatchReportStream(n_species=2)
        actual = np.array([100.0, 50.0])
        reported = np.array([80.0, 45.0])
        ratio = stream.compute_underreport_ratio(reported, actual)
        np.testing.assert_allclose(ratio, [0.2, 0.1])
