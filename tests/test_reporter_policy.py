"""Tests for Coral Key's evidence-only reporter policy."""

from __future__ import annotations

import numpy as np
from tattletots.interface.reporter_policy import (
    ReporterDecision,
    ReporterMetadata,
    ReporterPolicyContext,
    ReporterStream,
    create_reporter_policy,
)

from coral_key.reporter_policy import CORAL_REPORTER_POLICY_NAME, CoralEvidenceReporterPolicy


def _context(
    *,
    ais_data: list[float] | None = None,
    ais_status: tuple[str, ...] | None = None,
    ais_coordinates: tuple[tuple[float, ...] | None, ...] | None = None,
    sar_data: list[float] | None = None,
    sar_status: tuple[str, ...] | None = None,
    sar_coordinates: tuple[tuple[float, ...] | None, ...] | None = None,
    time_step: int = 0,
) -> ReporterPolicyContext:
    streams: list[ReporterStream] = []
    if ais_data is not None:
        streams.append(
            ReporterStream(
                label="ais_vms",
                data=np.asarray(ais_data, dtype=np.float64),
                observation_status=ais_status or ("observed",) * len(ais_data),
                metadata=ReporterMetadata(
                    coordinates=ais_coordinates,
                    identity=tuple(
                        "vessel-1" if coordinate is not None else None
                        for coordinate in ais_coordinates or ()
                    ),
                ),
            )
        )
    if sar_data is not None:
        streams.append(
            ReporterStream(
                label="sar_satellite",
                data=np.asarray(sar_data, dtype=np.float64),
                observation_status=sar_status or ("observed",) * len(sar_data),
                metadata=ReporterMetadata(sensor_coordinates=sar_coordinates),
            )
        )
    observation = np.zeros(2, dtype=np.float64)
    signal_vector = np.zeros(2, dtype=np.float64)
    return ReporterPolicyContext(
        observation=observation,
        signal_vector=signal_vector,
        anomaly_score=0.0,
        escalation_threshold=1.0,
        time_step=time_step,
        location_frame=((0, 0), (3, 3)),
        streams=tuple(streams),
    )


def test_policy_is_registered_under_coral_name() -> None:
    policy = create_reporter_policy(CORAL_REPORTER_POLICY_NAME)

    assert isinstance(policy, CoralEvidenceReporterPolicy)
    assert CORAL_REPORTER_POLICY_NAME == "coral_ais_sar_evidence"
    assert policy.decision_steps == 0


def test_hand_built_context_exposes_only_public_observation_surface() -> None:
    context = _context()

    assert set(context.__dataclass_fields__) == {
        "observation",
        "signal_vector",
        "anomaly_score",
        "escalation_threshold",
        "time_step",
        "location_frame",
        "streams",
    }
    assert not hasattr(context, "world")
    assert not hasattr(context, "adapter")
    assert not hasattr(context, "active_locations")


def test_policy_abstains_without_vessel_evidence() -> None:
    decision = CoralEvidenceReporterPolicy().decide(_context())

    assert decision == ReporterDecision(escalate=False)


def test_policy_ignores_unrelated_streams_and_nonfresh_sar() -> None:
    context = _context(sar_data=[1.0, 0.0, 0.0, 0.0], sar_status=("missing",) * 4)
    unrelated = ReporterStream(
        label="catch_reports",
        data=np.ones(4, dtype=np.float64),
        observation_status=("observed",) * 4,
        metadata=ReporterMetadata(),
    )
    context = ReporterPolicyContext(
        observation=context.observation,
        signal_vector=context.signal_vector,
        anomaly_score=context.anomaly_score,
        escalation_threshold=context.escalation_threshold,
        time_step=context.time_step,
        location_frame=context.location_frame,
        streams=(unrelated, *context.streams),
    )

    decision = CoralEvidenceReporterPolicy().decide(context)

    assert decision == ReporterDecision(escalate=False)


def test_sar_residual_location_responds_to_informative_evidence() -> None:
    policy = CoralEvidenceReporterPolicy()
    coordinates = tuple((index // 2, index % 2) for index in range(4))
    ais_coordinates = tuple((0.0, 0.0) for _ in range(5))
    ais_data = [0.0, 0.0, 0.5, 0.5, 1.0]

    low = policy.decide(
        _context(
            ais_data=ais_data,
            ais_coordinates=ais_coordinates,
            sar_data=[1.0, 2.0, 0.0, 0.0],
            sar_coordinates=coordinates,
        )
    )
    high = policy.decide(
        _context(
            ais_data=ais_data,
            ais_coordinates=ais_coordinates,
            sar_data=[1.0, 0.0, 0.0, 3.0],
            sar_coordinates=coordinates,
            time_step=8,
        )
    )

    assert low.escalate is True
    assert high.escalate is True
    assert low.location == (0, 1)
    assert high.location == (1, 1)
    assert low.location != high.location


def test_policy_uses_recent_ais_location_when_slot_goes_missing() -> None:
    policy = CoralEvidenceReporterPolicy()
    observed = policy.decide(
        _context(
            ais_data=[0.1, 0.2, 0.5, 0.5, 1.0],
            ais_coordinates=tuple((1.0, 2.0) for _ in range(5)),
            time_step=1,
        )
    )
    missing = policy.decide(
        _context(
            ais_data=[0.0] * 5,
            ais_status=("missing",) * 5,
            ais_coordinates=(None,) * 5,
            time_step=2,
        )
    )

    assert observed.escalate is False
    assert missing.escalate is True
    assert missing.location == (1, 2)


def test_policy_never_escalates_without_a_location_and_stays_in_frame() -> None:
    policy = CoralEvidenceReporterPolicy()
    decision = policy.decide(
        _context(
            ais_data=[0.1, 0.2, 0.5, 0.5, 1.0],
            ais_coordinates=tuple((3.0, 3.0) for _ in range(5)),
            sar_data=[0.0, 0.0, 0.0, 2.0],
            sar_coordinates=((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (3.0, 3.0)),
        )
    )

    assert not decision.escalate or decision.location is not None
    assert decision.location is not None
    assert (0, 0) <= decision.location <= (3, 3)


def test_policy_abstains_for_published_location_outside_frame() -> None:
    decision = CoralEvidenceReporterPolicy().decide(
        _context(
            ais_data=[0.1, 0.2, 0.5, 0.5, 1.0],
            ais_coordinates=tuple((9.0, 9.0) for _ in range(5)),
            sar_data=[0.0, 0.0, 0.0, 2.0],
            sar_coordinates=((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (9.0, 9.0)),
        )
    )

    assert decision == ReporterDecision(escalate=False)
