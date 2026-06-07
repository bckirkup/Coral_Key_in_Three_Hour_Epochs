"""Adversary model: IUU behavior, gaming strategies, and platform interference."""

from __future__ import annotations

from coral_key.adversary.interference import PlatformInterference
from coral_key.adversary.iuu import IUUDetectionOracle

__all__ = ["IUUDetectionOracle", "PlatformInterference"]
