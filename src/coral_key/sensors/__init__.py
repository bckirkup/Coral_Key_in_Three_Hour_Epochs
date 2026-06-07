"""Sensor streams: AIS, SAR, catch reports, oceanographic data, eDNA, EM."""

from __future__ import annotations

from coral_key.sensors.ais import AISStream
from coral_key.sensors.catch_reports import CatchReportStream
from coral_key.sensors.edna import EDNAStream
from coral_key.sensors.electronic_monitoring import EMStream
from coral_key.sensors.oceanographic import OceanographicStream
from coral_key.sensors.sar import SARStream

__all__ = [
    "AISStream",
    "CatchReportStream",
    "EDNAStream",
    "EMStream",
    "OceanographicStream",
    "SARStream",
]
