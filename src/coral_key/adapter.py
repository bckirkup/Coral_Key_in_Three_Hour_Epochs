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
from tattletots.models.report import Report
from tattletots.models.response_outcome import ResponseOutcome
from tattletots.models.stream import Stream
from tattletots.models.user import User

from coral_key.adversary.interference import PlatformInterference
from coral_key.adversary.iuu import IUUDetectionOracle
from coral_key.config import ScenarioConfig
from coral_key.fleet.behavior import FleetManager
from coral_key.fleet.vessel import VesselType
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
            )
            self._streams.append(stream)

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
            epoch=time_step,
            fish_distribution=fish_dist,
            enforcement_pressure=self._config.fleet.enforcement_pressure,
        )

        # 3. Fish stock dynamics
        self._fish_stock.step(catches=catch, habitat_suitability=habitat)

        # 4. Generate sensor observations and update streams
        observations = self._generate_observations(time_step)
        for stream, obs in zip(self._streams, observations, strict=True):
            # Apply potential interference to non-AIS streams
            if stream.label != self._ais.label:
                obs, interfered = self._interference.apply_interference(obs)
            else:
                interfered = False
            # Replace NaN with 0 for stream compatibility
            obs = np.nan_to_num(obs, nan=0.0)
            stream.update(obs)

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

    def infer_report_location(
        self,
        stream_data: list[NDArray[np.float64]],
        stream_labels: list[str],
    ) -> EventLocation:
        """Infer report location from AIS stream peak zone."""
        for data, label in zip(stream_data, stream_labels, strict=False):
            if label == "ais_positions" and data.size > 0:
                peak_idx = int(np.argmax(np.abs(data)))
                grid_ny = self._grid.ny
                return (peak_idx // grid_ny, peak_idx % grid_ny)
        return (0, 0)

    def score_relevance(self, signal_vector: NDArray[np.float64], user: User) -> float:
        """Score how relevant a signal is to a specific user."""
        return user.compute_relevance(signal_vector)

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
                catch = float(vessel.catch_this_epoch.sum()) if vessel.catch_this_epoch.size else 0.0
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
