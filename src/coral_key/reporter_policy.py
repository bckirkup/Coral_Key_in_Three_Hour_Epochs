"""Evidence-only reporter policy for Coral Key's published vessel streams."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from tattletots.interface.reporter_policy import (
    ReporterDecision,
    ReporterPolicyContext,
    ReporterStream,
    register_reporter_policy,
)
from tattletots.models.location import EventLocation

CORAL_REPORTER_POLICY_NAME = "coral_ais_sar_evidence"
_AIS_FEATURES_PER_VESSEL = 5
_MAX_AIS_MEMORY_AGE = 8


@dataclass
class CoralEvidenceReporterPolicy:
    """Report only from published AIS gaps and fresh SAR discrepancies."""

    last_known_locations: dict[int, EventLocation] = field(default_factory=dict)
    last_observed_steps: dict[int, int] = field(default_factory=dict)
    decision_steps: int = 0
    ais_evidence_steps: int = 0
    sar_evidence_steps: int = 0
    ais_or_sar_evidence_steps: int = 0

    def decide(self, context: ReporterPolicyContext) -> ReporterDecision:
        """Choose a location from the current public stream snapshots."""
        self.decision_steps += 1
        ais = self._find_stream(context.streams, "ais_vms")
        sar = self._find_stream(context.streams, "sar_satellite")
        ais_available = ais is not None and self._has_ais_declarations(ais)
        sar_available = sar is not None and self._has_sar_declarations(sar)
        self._record_evidence(ais_available, sar_available)
        observed_locations, missing_slots = self._read_available_ais(
            ais, ais_available, context.time_step
        )

        residual_location = self._fresh_sar_residual(sar, sar_available, observed_locations)
        if self._in_frame(residual_location, context):
            return ReporterDecision(escalate=True, location=residual_location)

        location = self._recent_missing_location(missing_slots, context.time_step)
        if self._in_frame(location, context):
            return ReporterDecision(escalate=True, location=location)

        return ReporterDecision(escalate=False)

    def _record_evidence(self, ais_available: bool, sar_available: bool) -> None:
        if ais_available:
            self.ais_evidence_steps += 1
        if sar_available:
            self.sar_evidence_steps += 1
        if ais_available or sar_available:
            self.ais_or_sar_evidence_steps += 1

    def _read_available_ais(
        self,
        stream: ReporterStream | None,
        available: bool,
        time_step: int,
    ) -> tuple[dict[int, EventLocation], list[int]]:
        if stream is None or not available:
            return {}, []
        return self._read_ais(stream, time_step)

    def _fresh_sar_residual(
        self,
        stream: ReporterStream | None,
        available: bool,
        observed_locations: dict[int, EventLocation],
    ) -> EventLocation | None:
        if stream is None or not available or not self._is_fresh(stream):
            return None
        return self._sar_residual_location(stream, observed_locations)

    @staticmethod
    def _find_stream(
        streams: tuple[ReporterStream, ...],
        label: str,
    ) -> ReporterStream | None:
        return next((stream for stream in streams if stream.label == label), None)

    @staticmethod
    def _has_ais_declarations(stream: ReporterStream) -> bool:
        coordinates = stream.metadata.coordinates
        identities = stream.metadata.identity
        return (
            coordinates is not None
            and identities is not None
            and len(coordinates) == stream.data.size
            and len(identities) == stream.data.size
        )

    @staticmethod
    def _has_sar_declarations(stream: ReporterStream) -> bool:
        coordinates = stream.metadata.sensor_coordinates
        return (
            coordinates is not None
            and len(coordinates) == stream.data.size
            and any(coordinate is not None for coordinate in coordinates)
        )

    @staticmethod
    def _is_fresh(stream: ReporterStream) -> bool:
        return bool(stream.observation_status) and all(
            status == "observed" for status in stream.observation_status
        )

    def _read_ais(
        self,
        stream: ReporterStream,
        time_step: int,
    ) -> tuple[dict[int, EventLocation], list[int]]:
        observed_locations: dict[int, EventLocation] = {}
        missing_slots: list[int] = []
        statuses = stream.observation_status
        coordinates = stream.metadata.coordinates
        if coordinates is None:
            return observed_locations, missing_slots

        n_slots = stream.data.size // _AIS_FEATURES_PER_VESSEL
        for slot in range(n_slots):
            start = slot * _AIS_FEATURES_PER_VESSEL
            block_status = statuses[start : start + _AIS_FEATURES_PER_VESSEL]
            block_coordinates = coordinates[start : start + _AIS_FEATURES_PER_VESSEL]
            if all(status == "observed" for status in block_status):
                coordinate = block_coordinates[0]
                if coordinate is not None:
                    location = (int(round(coordinate[0])), int(round(coordinate[1])))
                    self.last_known_locations[slot] = location
                    self.last_observed_steps[slot] = time_step
                    observed_locations[slot] = location
            elif all(status == "missing" for status in block_status):
                missing_slots.append(slot)
        return observed_locations, missing_slots

    def _sar_residual_location(
        self,
        stream: ReporterStream,
        observed_locations: dict[int, EventLocation],
    ) -> EventLocation | None:
        coordinates = stream.metadata.sensor_coordinates
        if coordinates is None:
            return None
        occupancy: dict[EventLocation, int] = {}
        for location in observed_locations.values():
            occupancy[location] = occupancy.get(location, 0) + 1

        best_residual = 0.0
        best_location: EventLocation | None = None
        for value, coordinate in zip(stream.data, coordinates, strict=True):
            if coordinate is None or not np.isfinite(value):
                continue
            location = (int(round(coordinate[0])), int(round(coordinate[1])))
            residual = float(value) - occupancy.get(location, 0)
            if residual > best_residual:
                best_residual = residual
                best_location = location
        return best_location

    def _recent_missing_location(
        self,
        missing_slots: list[int],
        time_step: int,
    ) -> EventLocation | None:
        candidates = [
            (
                time_step - self.last_observed_steps[slot],
                self.last_known_locations[slot],
            )
            for slot in missing_slots
            if slot in self.last_known_locations
            and slot in self.last_observed_steps
            and time_step - self.last_observed_steps[slot] <= _MAX_AIS_MEMORY_AGE
        ]
        return min(candidates)[1] if candidates else None

    @staticmethod
    def _in_frame(
        location: EventLocation | None,
        context: ReporterPolicyContext,
    ) -> bool:
        if location is None or context.location_frame is None:
            return location is not None
        minimum, maximum = context.location_frame
        return minimum[0] <= location[0] <= maximum[0] and minimum[1] <= location[1] <= maximum[1]


register_reporter_policy(CORAL_REPORTER_POLICY_NAME, CoralEvidenceReporterPolicy)
