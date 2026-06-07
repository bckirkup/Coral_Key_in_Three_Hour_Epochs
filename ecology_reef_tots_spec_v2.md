# ReefTots / ReefWatch: Domain Specification
## Fishery Monitoring, IUU Detection, and Ocean Sensor Ecology

### 1. Purpose

ReefTots tests whether a TattleTots information ecology can improve fishery monitoring and IUU detection in a mixed ecological-adversarial domain. The system must manage fish-stock uncertainty, strategic vessel behavior, and physical ocean sensor platforms.

Insider threat / corrupt officials are explicitly deferred. The current adversary model includes Layers 1-3 only:
1. IUU fishers
2. Compliant-but-gaming fishers
3. Actors interfering with monitoring platforms or command links

### 2. Core Hypothesis

A BMA ecology can improve IUU detection and stock assessment under sparse, deceptive, and partially missing data by exploiting residual inconsistencies across AIS, satellite vessel detections, catch reports, oceanography, and autonomous ocean platforms.

### 3. Environment

#### 3.1 Spatial Domain
- Marine protected area (MPA) plus surrounding legal fishing grounds
- Grid of ocean zones with depth, habitat type, distance to port, jurisdiction
- Seasonal oceanographic regime (temperature, chlorophyll, currents)
- Ports and landing sites

#### 3.2 Fish Stock Dynamics
- 2-3 target species
- Schaefer/logistic production model for each species:
  B_{t+1} = B_t + r B_t (1 - B_t/K) - C_t
- MSY = rK/4, B_MSY = K/2
- Spatial distribution driven by SST, chlorophyll, habitat, and season
- CPUE = qB + lognormal observation error

#### 3.3 Fleet Dynamics
- Legal vessels: mostly honest, fish in allowed zones, report catch
- Gaming vessels: operate legally but high-grade, misreport fine-scale location, underreport by small margins
- IUU vessels: fish in MPA, disable/spoof AIS, underreport or do not report catch
- Vessel behavior responds to enforcement pressure and fish abundance

### 4. Physical Platforms and Basal Streams

#### 4.1 AIS / VMS
- Vessel position, speed, heading, identity
- Failure modes: AIS off, spoofed position, unrealistic tracks
- High temporal resolution

#### 4.2 SAR / Optical Satellite Vessel Detection
- Independent detection of vessels, including dark vessels
- Revisit: hours to days
- SAR works through cloud/night but costs more
- Used to audit AIS

#### 4.3 Electronic Monitoring (EM)
- Cameras on vessels
- Catch handling, gear deployment, discards
- Review cost depends on review rate; EM can be ~50% cheaper than observers

#### 4.4 Catch Reports / Landing Records
- Self-reported catch, species, weight, location
- Can be falsified or strategically blurred

#### 4.5 Oceanographic Data
- SST, chlorophyll-a, currents, upwelling indices
- Drives fish distribution and expected CPUE

#### 4.6 eDNA Sampling
- Sparse, delayed samples from water
- Species presence / relative abundance signal
- Useful for stock distribution validation

#### 4.7 Autonomous Ocean Platforms
Physical Tots may include:
- Underwater gliders: CTD, acoustic sensors, eDNA sampler; slow but persistent; weeks endurance
- Saildrone / surface USV: AIS receiver, radar, camera, acoustic, meteorological sensors; months endurance
- Wave gliders: low-power acoustic/environmental monitoring
- Patrol ASVs: higher speed, shorter endurance

These platforms can be Tots with body plans, energy budgets, sensing strategies, reporting strategies, and susceptibility to interference.

### 5. Adversary Model (Layers 1-3)

#### Layer 1: IUU Fishers
- Fish in MPA or closed zones
- Disable AIS near restricted areas
- Spoof positions
- Underreport catch
- Avoid known patrol routes

#### Layer 2: Legal Fishers Gaming the System
- High-grading: discarding low-value catch
- Fine-scale misreporting: legally report zone, but obscure exact hotspot extraction
- Time-shifting reports to exploit enforcement windows
- Stay technically compliant while degrading stock assessments

#### Layer 3: Platform Interference
- Jam or spoof command links
- Physically foul or tow sensor platforms
- Obscure cameras or damage sensors
- Induce data gaps that mimic normal ocean comms failure

Cybersecurity is embedded here: command/data links for gliders and surface drones are attack surfaces. The full disembodied cybersecurity domain is separate and should be built later.

### 6. Users

#### Patrol Commander
- Attention budget: daily/weekly
- Priority: where to send patrol vessels
- Values high-confidence IUU intercepts and dark-vessel detection

#### Stock Assessment Scientist
- Attention budget: monthly/quarterly
- Priority: CPUE trends, stock biomass uncertainty, eDNA validation
- Values data quality and uncertainty reduction

#### Policy Director
- Attention budget: seasonal/annual
- Priority: quota setting, MPA effectiveness, public reporting
- Values decision-ready summaries, not raw detections

### 7. Expected Tot Roles

Software/sensor Tots:
- AIS behavior agents
- SAR/optical vessel-detection agents
- Catch-report consistency agents
- Oceanographic habitat agents
- CPUE/stock assessment agents
- Patrol recommendation brokers
- Whistleblowers auditing AIS gaps, impossible vessel tracks, or catch/oceanography inconsistencies

Physical platform Tots:
- Glider scouts: oceanographic mapping, eDNA/acoustic sampling
- Surface sentinels: AIS/SAR cross-cueing, dark vessel confirmation
- Patrol relays: communication and local confirmation

### 8. Competing Architectures

#### A0 Human observer / patrol baseline
Observer coverage, port sampling, manual patrol planning.

#### A1 AIS anomaly dashboard
AIS/VMS monitoring with rule-based dark-vessel and speed/loitering detection.

#### A2 Electronic monitoring + human review
On-vessel EM cameras, sampled review, catch verification.

#### A3 Centralized multi-source fusion
Strong conventional competitor:
- AIS + SAR/optical + catch reports + oceanography + stock model
- Centralized ML for IUU risk scoring
- Centralized patrol allocation optimization
- Bayesian stock assessment

#### A4 BMA / TattleTots ecology
Self-organizing residual-processing ecology with physical ocean platforms as optional Tots.

### 9. Metrics

- IUU detection rate
- False boarding/inspection rate
- Patrol cost
- Dark-vessel detection latency
- Catch underreporting detection
- AIS spoofing detection
- Platform interference detection
- Stock assessment error
- CPUE bias reduction
- Quota-setting error
- Long-term biomass relative to B_MSY
- Economic loss to IUU
- Human attention load by user type
- Graceful degradation under sensor/platform loss

### 10. Falsification Test

BMA must improve either:
1. IUU detection at equal or lower patrol cost, OR
2. Stock assessment accuracy at equal or lower monitoring cost,

compared to centralized AIS+SAR+catch+oceanography fusion.

The strongest expected BMA advantage is not raw accuracy under clean conditions, but robustness to missing/deceptive data and cross-source residual exploitation.
