"""ReefWatch domain adapter: plugs into TattleTots engine via DomainAdapter ABC."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from tattletots.engine.response_judgment import judge_necessity
from tattletots.interface.domain_adapter import DomainAdapter
from tattletots.models.dispatch_target import DispatchTarget
from tattletots.models.location import EventLocation
from tattletots.models.observation import ObservationStatus, StreamMetadata
from tattletots.models.report import Report
from tattletots.models.response_outcome import ResponseOutcome
from tattletots.models.stream import Stream
from tattletots.models.user import User

from coral_key.adversary.interference import PlatformInterference
from coral_key.adversary.iuu import IUUDetectionOracle
from coral_key.config import ScenarioConfig
from coral_key.fleet.behavior import FleetManager
from coral_key.fleet.vessel import Vessel, VesselType
from coral_key.metrics import EpochMetrics, MetricsCollector
from coral_key.ocean.fish_stock import FishStock
from coral_key.ocean.grid import OceanGrid
from coral_key.ocean.oceanography import Oceanography
from coral_key.sensors.ais import AISStream
from coral_key.sensors.catch_reports import CatchReportStream
from coral_key.sensors.edna import EDNAStream
from coral_key.sensors.electronic_monitoring import EMStream
from coral_key.sensors.oceanographic import OceanographicStream
from coral_key.sensors.sar import SARStream
from coral_key.users import create_all_users


class ReefWatchAdapter(DomainAdapter):
    """TattleTots domain adapter for fishery monitoring and IUU detection.

    Simulates a marine protected area with:
    - Fish stock dynamics (Schaefer model)
    - Mixed fleet (legal, gaming, IUU vessels)
    - Multiple sensor modalities (AIS, SAR, catch reports, oceanographic, eDNA, EM)
    - Adversarial behavior (AIS disable/spoof, platform interference)
    - Three user profiles (Patrol Commander, Stock Scientist, Policy Director)

    Time step = 3-hour epoch.
    """

    def __init__(self, config: ScenarioConfig | None = None) -> None:
        self._config = config or ScenarioConfig()
        self._rng = np.random.default_rng(self._config.seed)

        # Build ocean environment
        self._grid = OceanGrid.generate(
            nx=self._config.ocean.n_zones_x,
            ny=self._config.ocean.n_zones_y,
            mpa_fraction=self._config.ocean.mpa_fraction,
            n_ports=self._config.ocean.n_ports,
            rng=self._rng,
        )
        self._n_zones = self._grid.nx * self._grid.ny

        self._oceanography = Oceanography(
            grid=self._grid,
            sst_base=self._config.ocean.sst_base,
            sst_amplitude=self._config.ocean.sst_seasonal_amplitude,
            chlorophyll_base=self._config.ocean.chlorophyll_base,
            rng=self._rng,
        )

        # Fish stocks
        self._fish_stock = FishStock(
            n_species=self._config.fish.n_species,
            n_zones=self._n_zones,
            carrying_capacity=self._config.fish.carrying_capacity,
            intrinsic_growth_rate=self._config.fish.intrinsic_growth_rate,
            catchability=self._config.fish.catchability,
            rng=self._rng,
        )

        # Fleet
        self._fleet = FleetManager(
            grid=self._grid,
            fleet_config=self._config.fleet,
            adversary_config=self._config.adversary,
            n_species=self._config.fish.n_species,
            catch_efficiency=self._config.fish.catch_efficiency,
            carrying_capacity=self._config.fish.carrying_capacity,
            rng=self._rng,
        )

        # Sensors
        n_vessels = (
            self._config.fleet.n_legal_vessels
            + self._config.fleet.n_gaming_vessels
            + self._config.fleet.n_iuu_vessels
        )
        self._ais = AISStream(
            n_vessels=n_vessels,
            update_interval=self._config.sensors.ais_update_interval,
            features_per_vessel=self._config.sensors.ais_features_per_vessel,
        )
        self._sar = SARStream(
            grid=self._grid,
            revisit_interval=self._config.sensors.sar_revisit_interval,
            rng=self._rng,
        )
        self._catch_reports = CatchReportStream(
            n_species=self._config.fish.n_species,
            underreport_fraction_iuu=self._config.fleet.underreport_fraction,
            underreport_fraction_gaming=self._config.adversary.gaming_underreport_margin,
            rng=self._rng,
        )
        self._ocean_sensor = OceanographicStream(n_zones=self._n_zones)
        self._edna = EDNAStream(
            n_species=self._config.fish.n_species,
            sample_interval=self._config.sensors.edna_sample_interval,
            rng=self._rng,
        )
        em_cap = self._config.sensors.em_monitored_vessels
        self._em = EMStream(
            n_species=self._config.fish.n_species,
            review_rate=self._config.sensors.em_review_rate,
            n_monitored_vessels=em_cap if em_cap is not None else n_vessels,
            rng=self._rng,
        )

        # Adversary
        self._interference = PlatformInterference(
            interference_rate=self._config.adversary.platform_interference_rate,
            rng=self._rng,
        )
        self._iuu_oracle = IUUDetectionOracle(grid=self._grid)

        # Metrics
        self._metrics = MetricsCollector(n_species=self._config.fish.n_species)

        # Build TattleTots streams
        self._streams: list[Stream] = []
        self._setup_streams()

        # Users
        total_dim = sum(s.dimensionality for s in self._streams)
        self._users = create_all_users(n_priority_dims=total_dim)

        # State
        self._current_epoch = 0
        self._ocean_state = self._oceanography.compute_state(0, self._config.epoch_hours)

    def _setup_streams(self) -> None:
        """Create TattleTots Stream objects for each sensor modality."""
        sensor_specs: list[tuple[str, int]] = [
            (self._ais.label, self._ais.dimensionality),
            (self._sar.label, self._sar.dimensionality),
            (self._catch_reports.label, self._catch_reports.dimensionality),
            (self._ocean_sensor.label, self._ocean_sensor.dimensionality),
            (self._edna.label, self._edna.dimensionality),
            (self._em.label, self._em.dimensionality),
        ]
        for label, dim in sensor_specs:
            stream = Stream(
                stream_type="raw",  # type: ignore[arg-type]
                dimensionality=dim,
                label=label,
                current_data=np.zeros(dim),
                metadata=self._initial_metadata(label, dim),
            )
            self._streams.append(stream)

    def _initial_metadata(self, label: str, dimensionality: int) -> StreamMetadata:
        """Declare static provenance where it is known before the first epoch."""
        if label == self._sar.label:
            return self._zone_metadata(label)
        if label == self._ocean_sensor.label:
            return self._zone_metadata(label, repetitions=3)
        return StreamMetadata(
            modality=[label] * dimensionality,
            coordinates=[None] * dimensionality,
            sensor_coordinates=[None] * dimensionality,
            identity=[None] * dimensionality,
            footprints=[None] * dimensionality,
            resolution=[None] * dimensionality,
        )

    def _zone_metadata(self, modality: str, repetitions: int = 1) -> StreamMetadata:
        """Declare static grid-zone geometry for a per-zone sensor stream."""
        coordinates: list[tuple[float, ...] | None] = [
            (float(zone.x), float(zone.y)) for _ in range(repetitions) for zone in self._grid.zones
        ]
        footprint: list[tuple[float, ...] | None] = [(1.0, 1.0)] * len(coordinates)
        return StreamMetadata(
            sensor_coordinates=coordinates,
            modality=[modality] * len(coordinates),
            identity=[None] * len(coordinates),
            footprints=footprint,
            resolution=[1.0] * len(coordinates),
        )

    def _ais_metadata(self, vessels: list[Vessel], observation: np.ndarray) -> StreamMetadata:
        """Declare actual or self-reported AIS positions without sanitizing spoofing."""
        coordinates: list[tuple[float, ...] | None] = []
        identities: list[str | None] = []
        footprint = (0.0, 0.0)
        for index, vessel in enumerate(vessels[: self._ais.n_vessels]):
            position = vessel.reported_position or vessel.position
            offset = index * self._ais.features_per_vessel
            for feature_index in range(self._ais.features_per_vessel):
                available = offset + feature_index < observation.size and not np.isnan(
                    observation[offset + feature_index]
                )
                coordinate = (float(position.zone_x), float(position.zone_y)) if available else None
                coordinates.append(coordinate)
                identities.append(vessel.id if available else None)
        missing = self._ais.dimensionality - len(coordinates)
        coordinates.extend([None] * missing)
        identities.extend([None] * missing)
        return StreamMetadata(
            coordinates=coordinates,
            modality=[self._ais.label] * self._ais.dimensionality,
            identity=identities,
            footprints=[footprint] * self._ais.dimensionality,
            resolution=[0.0] * self._ais.dimensionality,
        )

    def _vessel_metadata(
        self,
        label: str,
        vessels: list[Vessel],
        observation: np.ndarray,
        stride: int,
    ) -> StreamMetadata:
        """Declare per-vessel provenance from the observation's own availability."""
        coordinates: list[tuple[float, ...] | None] = []
        identities: list[str | None] = []
        dimensionality = observation.size
        for index in range(min(len(vessels), dimensionality // stride)):
            vessel = vessels[index]
            coordinate = (float(vessel.position.zone_x), float(vessel.position.zone_y))
            offset = index * stride
            for feature_index in range(stride):
                available = not np.isnan(observation[offset + feature_index])
                coordinates.append(coordinate if available else None)
                identities.append(vessel.id if available else None)
        missing = dimensionality - len(coordinates)
        coordinates.extend([None] * missing)
        identities.extend([None] * missing)
        return StreamMetadata(
            coordinates=coordinates,
            modality=[label] * dimensionality,
            identity=identities,
            footprints=[(0.0, 0.0)] * dimensionality,
            resolution=[0.0] * dimensionality,
        )

    def _edna_metadata(self) -> StreamMetadata:
        """Declare geometry only for the current eDNA sample."""
        zones = self._edna.last_sample_zones
        if zones is None:
            return self._initial_metadata(self._edna.label, self._edna.dimensionality)
        coordinates: list[tuple[float, ...] | None] = [
            (
                float(self._grid.zones[int(zone)].x),
                float(self._grid.zones[int(zone)].y),
            )
            for _ in range(self._config.fish.n_species)
            for zone in zones
        ]
        return StreamMetadata(
            sensor_coordinates=coordinates,
            modality=[self._edna.label] * len(coordinates),
            identity=[None] * len(coordinates),
            footprints=[(1.0, 1.0)] * len(coordinates),
            resolution=[1.0] * len(coordinates),
        )

    @staticmethod
    def _observation_status(
        observation: np.ndarray, missing_values: tuple[float, ...] = ()
    ) -> np.ndarray:
        """Convert sensor absence markers into explicit transport statuses."""
        missing = np.isnan(observation)
        for value in missing_values:
            missing |= observation == value
        return np.where(
            missing,
            ObservationStatus.MISSING.value,
            ObservationStatus.OBSERVED.value,
        )

    @staticmethod
    def _clear_missing_metadata(metadata: StreamMetadata, status: np.ndarray) -> StreamMetadata:
        """Clear observed-object provenance absent from the final reading."""
        coordinates = list(metadata.coordinates) if metadata.coordinates is not None else None
        identities = list(metadata.identity) if metadata.identity is not None else None
        if coordinates is not None:
            for index, feature_status in enumerate(status):
                if feature_status == ObservationStatus.MISSING.value:
                    coordinates[index] = None
        if identities is not None:
            for index, feature_status in enumerate(status):
                if feature_status == ObservationStatus.MISSING.value:
                    identities[index] = None
        return metadata.model_copy(update={"coordinates": coordinates, "identity": identities})

    def get_streams(self) -> list[Stream]:
        """Return domain data streams."""
        return self._streams

    def get_users(self) -> list[User]:
        """Return domain user profiles."""
        return self._users

    def step(self, time_step: int) -> None:
        """Advance the domain simulation by one 3-hour epoch."""
        self._current_epoch = time_step

        # 1. Update oceanography
        self._ocean_state = self._oceanography.compute_state(time_step, self._config.epoch_hours)
        habitat = self._oceanography.compute_fish_habitat_suitability(self._ocean_state)

        # 2. Fleet operations (returns total actual catch)
        # Pass actual local biomass (biomass * spatial fraction) so catch scales with stock
        fish_dist = np.array(
            [sp.biomass * sp.spatial_distribution for sp in self._fish_stock.species]
        )
        catch = self._fleet.step(
            time_step,
            fish_distribution=fish_dist,
            enforcement_pressure=self._config.fleet.enforcement_pressure,
        )

        # 3. Fish stock dynamics
        self._fish_stock.step(catches=catch, habitat_suitability=habitat)

        # 4. Generate sensor observations and update streams
        observations = self._generate_observations(time_step)
        vessels = self._fleet.vessels
        stream_metadata = [
            self._ais_metadata(vessels, observations[0]),
            self._zone_metadata(self._sar.label),
            self._initial_metadata(self._catch_reports.label, observations[2].size),
            self._zone_metadata(self._ocean_sensor.label, repetitions=3),
            self._edna_metadata(),
            self._vessel_metadata(
                self._em.label,
                vessels,
                observations[5],
                self._config.fish.n_species + 2,
            ),
        ]
        missing_markers = ((), (-1.0,), (), (), (-1.0,), (-1.0,))
        for stream, obs, metadata, markers in zip(
            self._streams, observations, stream_metadata, missing_markers, strict=True
        ):
            # Apply potential interference to non-AIS streams
            if stream.label != self._ais.label:
                obs, interfered = self._interference.apply_interference(obs)
            else:
                interfered = False
            # Interference injects NaN data gaps or numeric corruption; only the
            # former changes availability, while corruption remains present data.
            status = self._observation_status(obs, markers)
            metadata = self._clear_missing_metadata(metadata, status)
            # Replace NaN with 0 for stream compatibility
            obs = np.nan_to_num(obs, nan=0.0)
            stream.metadata = metadata
            stream.update(obs, status=status)

        # 5. Record metrics
        reported_catch = self._fleet.get_reported_catches()
        self._metrics.record_catch(catch, reported_catch)

        ais_obs = observations[0]
        sar_obs = observations[1]
        n_vessels = len(self._fleet.vessels)
        self._metrics.record_epoch(
            EpochMetrics(
                epoch=time_step,
                iuu_vessels_active=len(self._iuu_oracle.get_active_iuu_events(self._fleet.vessels)),
                mpa_violations=self._iuu_oracle.count_mpa_violations(self._fleet.vessels),
                dark_vessels_detected=self._ais.count_dark_vessels(ais_obs),
                sar_ais_discrepancies=self._sar.cross_reference_ais(sar_obs, ais_obs, n_vessels),
                total_catch_actual=float(catch.sum()),
                total_catch_reported=float(reported_catch.sum()),
                platform_interference_events=1 if interfered else 0,
            )
        )

        # 6. Biomass estimation (CPUE-based with noise) for stock assessment metric
        # Only estimate when there's catch data (vessels are fishing)
        if reported_catch.sum() > 0:
            actual_biomass = self._fish_stock.get_total_biomass()
            estimated_biomass = self._estimate_biomass(reported_catch)
            self._metrics.record_biomass_estimate(estimated_biomass, actual_biomass)

    def _estimate_biomass(self, reported_catch: np.ndarray) -> np.ndarray:
        """Produce a noisy biomass estimate from reported catch (simulates assessment).

        Inverts the catch model: C ≈ efficiency * B/n_zones * n_active * E[noise].
        So: B_est = C * n_zones / (n_active * efficiency * mean_catch_noise).
        The mean of Uniform(0.5, 2.0) is 1.25.
        """
        n_active = sum(1 for v in self._fleet.vessels if not v.at_port)
        effort = max(1, n_active)
        efficiency = self._config.fish.catch_efficiency
        n_species = self._config.fish.n_species
        mean_catch_noise = 1.25  # E[Uniform(0.5, 2.0)]

        estimates = np.zeros(n_species)
        for i in range(n_species):
            catch_i = reported_catch[i] if i < len(reported_catch) else 0.0
            if catch_i > 0 and efficiency > 0:
                raw_estimate = catch_i * self._n_zones / (effort * efficiency * mean_catch_noise)
            else:
                raw_estimate = self._config.fish.carrying_capacity
            # Add observation noise (10% CV)
            noise = float(self._rng.normal(0, 0.10 * raw_estimate))
            estimates[i] = max(1.0, raw_estimate + noise)
        return estimates

    def _generate_observations(self, epoch: int) -> list[np.ndarray]:
        """Generate all sensor observations for this epoch."""
        vessels = self._fleet.vessels
        return [
            self._ais.observe(vessels, epoch),
            self._sar.observe(vessels, epoch),
            self._catch_reports.observe(vessels),
            self._ocean_sensor.observe(self._ocean_state),
            self._edna.observe(self._fish_stock, epoch, self._n_zones),
            self._em.observe(vessels),
        ]

    def get_ground_truth(self, time_step: int) -> bool:
        """Return whether IUU activity is happening at this time step."""
        return self._iuu_oracle.is_iuu_active(self._fleet.vessels)

    def get_active_locations(self, time_step: int) -> list[EventLocation]:
        """Return zones where IUU vessels are currently active."""
        events = self._iuu_oracle.get_active_iuu_events(self._fleet.vessels)
        locations: list[EventLocation] = []
        for e in events:
            zx = e["zone_x"]
            zy = e["zone_y"]
            locations.append((int(str(zx)), int(str(zy))))
        return locations

    def get_location_frame(self) -> tuple[EventLocation, EventLocation]:
        """Declare the grid extent without reconstructing sensor provenance."""
        coordinates = [(zone.x, zone.y) for zone in self._grid.zones]
        return (
            (
                min(coordinate[0] for coordinate in coordinates),
                min(coordinate[1] for coordinate in coordinates),
            ),
            (
                max(coordinate[0] for coordinate in coordinates),
                max(coordinate[1] for coordinate in coordinates),
            ),
        )

    def infer_report_location(
        self,
        stream_data: list[NDArray[np.float64]],
        stream_labels: list[str],
    ) -> EventLocation | None:
        """Infer location from the strongest normalized declared evidence.

        Each candidate stream is normalized by its RMS magnitude before its
        strongest feature competes with other modalities. The winning feature
        is mapped through the geometry published by that stream.
        """
        best = self._best_declared_geometry_feature(stream_data, stream_labels)
        if best is None:
            return None
        _, _, _, location = best
        return location

    def _best_declared_geometry_feature(
        self,
        stream_data: list[NDArray[np.float64]],
        stream_labels: list[str],
    ) -> tuple[int, float, int, EventLocation] | None:
        """Return the strongest normalized feature and its declared location."""
        streams_by_label = {stream.label: stream for stream in self._streams}
        best: tuple[int, float, int, EventLocation] | None = None
        for data, label in zip(stream_data, stream_labels, strict=False):
            stream = streams_by_label.get(label)
            if stream is None or stream.metadata is None:
                continue
            coordinates = stream.metadata.sensor_coordinates
            if coordinates is None or not any(coordinate is not None for coordinate in coordinates):
                coordinates = stream.metadata.coordinates
            if coordinates is None:
                continue
            finite = np.isfinite(data)
            if not np.any(finite):
                continue
            magnitudes = np.abs(data)
            magnitudes[~finite] = 0.0
            scale = float(np.sqrt(np.mean(magnitudes**2)))
            if scale <= 0.0:
                continue
            feature_index = int(np.argmax(magnitudes))
            if feature_index >= len(coordinates) or coordinates[feature_index] is None:
                continue
            coordinate = coordinates[feature_index]
            if coordinate is None or len(coordinate) < 2:
                continue
            score = float(magnitudes[feature_index] / scale)
            location = (int(round(coordinate[0])), int(round(coordinate[1])))
            modalities = stream.metadata.modality or []
            detection_terms = ("ais", "sar", "electronic_monitoring")
            tier = (
                0
                if any(
                    any(term in (modality or "").lower() for term in detection_terms)
                    for modality in modalities
                )
                else 1
            )
            if best is None or (tier, -score) < (best[0], -best[1]):
                best = (tier, score, feature_index, location)
        return best

    def score_relevance(self, signal_vector: NDArray[np.float64], user: User) -> float:
        from tattletots.engine.relevance import score_report_relevance

        return score_report_relevance(signal_vector, user)

    def compute_costs(
        self,
        n_escalations: int,
        n_correct: int,
        n_false_alarms: int,
        n_missed: int,
    ) -> dict[str, float]:
        """Compute domain-specific costs for fishery operations.

        Patrol costs are high. False boardings damage diplomacy.
        Missed IUU leads to stock depletion.
        """
        patrol_cost_per_sortie = 50.0
        false_boarding_cost = 100.0
        missed_iuu_cost = 200.0

        return {
            "surveillance_cost": n_escalations * patrol_cost_per_sortie,
            "response_cost": n_correct * patrol_cost_per_sortie
            + n_false_alarms * false_boarding_cost,
            "damage_cost": n_missed * missed_iuu_cost,
        }

    def dispatch_patrol(self, zone_x: int, zone_y: int) -> None:
        """Board IUU vessels in a zone and return them to port."""
        ports = self._grid.get_port_zones()
        if not ports:
            return
        port = ports[0]
        for vessel in self._fleet.vessels:
            if vessel.vessel_type != VesselType.IUU or vessel.at_port:
                continue
            if vessel.position.zone_x == zone_x and vessel.position.zone_y == zone_y:
                vessel.catch_this_epoch = np.zeros_like(vessel.catch_this_epoch)
                vessel.return_to_port(port.x, port.y)
                return

    def get_responder_user_id(self) -> str:
        """Patrol Commander authorizes IUU patrol dispatch."""
        for user in self._users:
            if user.name == "Patrol Commander":
                return user.id
        return self._users[0].id

    def dispatch_and_judge_responses(
        self,
        targets: list[DispatchTarget],
        time_step: int,
    ) -> list[ResponseOutcome]:
        """Patrol COP-selected zones and judge responder necessity."""
        outcomes: list[ResponseOutcome] = []
        responder_id = self.get_responder_user_id()

        for target in targets:
            zone_x, zone_y = target.location
            before = self._iuu_severity(zone_x, zone_y)
            self.dispatch_patrol(zone_x, zone_y)
            after = self._iuu_severity(zone_x, zone_y)
            dispatched = True

            linked_reports = target.reports or [
                Report(
                    agent_id="",
                    target_user_id=responder_id,
                    time_step=time_step,
                    signal_vector=np.array([]),
                    confidence=0.0,
                    anomaly_score=0.0,
                    location=target.location,
                    verified=True,
                )
            ]
            primary = next((r for r in linked_reports if r.agent_id), linked_reports[0])
            if primary.correct:
                self._metrics.record_escalation(correct=True)
            elif primary.verified and primary.correct is False:
                self._metrics.record_escalation(correct=False)

            problem, mitigated, necessary = judge_necessity(before, after)
            for report in linked_reports:
                outcome = ResponseOutcome(
                    agent_id=report.agent_id,
                    responder_user_id=responder_id,
                    time_step=time_step,
                    location=target.location,
                    response_type="patrol",
                    dispatched=dispatched,
                    problem_severity_before=before,
                    problem_severity_after=after,
                    problem_present=problem,
                    mitigated=mitigated,
                    response_necessary=necessary,
                )
                report.response_outcome = outcome
                outcomes.append(outcome)

        return outcomes

    def _iuu_severity(self, zone_x: int, zone_y: int) -> float:
        """IUU activity severity in a zone (0 if none)."""
        severity = 0.0
        for vessel in self._fleet.vessels:
            if vessel.vessel_type != VesselType.IUU or vessel.at_port:
                continue
            if vessel.position.zone_x == zone_x and vessel.position.zone_y == zone_y:
                catch = (
                    float(vessel.catch_this_epoch.sum()) if vessel.catch_this_epoch.size else 0.0
                )
                severity = max(severity, 1.0 + catch)
        return severity

    @property
    def metrics_collector(self) -> MetricsCollector:
        """Access the metrics collector for post-run analysis."""
        return self._metrics

    @property
    def fish_stock(self) -> FishStock:
        """Access fish stock state."""
        return self._fish_stock

    @property
    def grid(self) -> OceanGrid:
        """Access ocean grid."""
        return self._grid

    def to_config(self) -> dict[str, object]:
        """Serialize scenario configuration."""
        return self._config.model_dump()

    @classmethod
    def from_config(cls, config_dict: dict[str, object]) -> ReefWatchAdapter:
        """Construct from a configuration dict."""
        config = ScenarioConfig.model_validate(config_dict)
        return cls(config=config)

    @classmethod
    def from_config_file(cls, path: Path) -> ReefWatchAdapter:
        """Load scenario from a JSON config file."""
        with open(path) as f:
            config_dict = json.load(f)
        return cls.from_config(config_dict)
