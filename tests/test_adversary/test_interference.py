"""Tests for platform interference."""

from __future__ import annotations

import numpy as np

from coral_key.adversary.interference import PlatformInterference


class TestPlatformInterference:
    def test_no_interference_at_zero_rate(self) -> None:
        rng = np.random.default_rng(42)
        pi = PlatformInterference(interference_rate=0.0, rng=rng)
        data = np.ones(10)
        result, interfered = pi.apply_interference(data)
        assert interfered is False
        np.testing.assert_array_equal(result, data)

    def test_always_interferes_at_rate_one(self) -> None:
        rng = np.random.default_rng(42)
        pi = PlatformInterference(interference_rate=1.0, rng=rng)
        data = np.ones(10)
        result, interfered = pi.apply_interference(data)
        assert interfered is True
        # At least some values should be different
        assert not np.array_equal(result, data)

    def test_interference_injects_nan_or_noise(self) -> None:
        rng = np.random.default_rng(42)
        pi = PlatformInterference(interference_rate=1.0, rng=rng)
        data = np.zeros(20)
        result, _ = pi.apply_interference(data)

        # Should have some NaN or non-zero values
        has_nan = np.any(np.isnan(result))
        has_nonzero = np.any(result != 0.0)
        assert has_nan or has_nonzero
