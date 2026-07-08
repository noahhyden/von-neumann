# reliability - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Tenth and final buildable module
from `ROADMAP-PROPOSAL.md` (after transfer, comms, assembly, isru, propellant, thermal,
power-source, autonomy, shielding). Numbers recomputed and confirmed (see "Validation").

`reliability` adds the real-world messiness CLAUDE.md 3 wants: degradation and mortality
that turn idealized exponential replication into bounded behavior, and unlock the swarm's
Aurora steady-state. **It is the highest-risk module** - the only one adding new RNG, with
the worst over-nesting temptation and the most proxy/gap data - so its discipline section
is load-bearing, not boilerplate.

---

## Scope

**Models (two sub-parameters that compose but do not nest):**

1. **Power degradation - PURE deterministic, NO RNG.** A multiplier `g(dose) in (0,1]` on
   `probe-sim`'s delivered power, from accumulated dose (dose-rate x time) plus, on a
   surface, an exponential dust term. A pure function of state.
2. **Discrete failure / mortality - SEEDED stochastic.** A per-day hazard applied to each
   active entity, drawn from the *existing* `multi-probe`/`swarm` seeded RNG in id order.
   On failure the entity leaves the active set. For `swarm`, a settlement death rate that
   produces the Aurora equilibrium.

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3): the internal cause tree of a
failure (arcing, bearing wear, SEU-to-latchup escalation) - those collapse to (a) a
dose-rate lookup, (b) a degradation curve, (c) a scalar hazard. No FMEA, no repair/
redundancy sub-model, no per-component MTBF stack.

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| ~0.18 %/yr (coeff 0.998199) | fraction | TJ GaAs array degradation, nominal (1.43% at 8 yr, 2.67% at 15 yr) | ScienceDirect S0038092X15005137 | https://www.sciencedirect.com/science/article/abs/pii/S0038092X15005137 | sourced |
| Isc 93.2%, Voc 86.0%, eff 74.5% | fraction | TJ GaAs EOL under heavy neutron fluence (lower bound) | ScienceDirect S0026271421003164 | https://www.sciencedirect.com/science/article/abs/pii/S0026271421003164 | sourced |
| 1.84 +/- 0.30 | mSv/day | Deep-space GCR dose-equivalent (MSL/RAD cruise) | PMC8649166 | https://pmc.ncbi.nlm.nih.gov/articles/PMC8649166/ | sourced |
| ~1 (solar max) to ~5 (solar min) | mSv/day | GCR dose over the solar cycle | PMC8649166 | (as above) | sourced |
| 30-40 krad/perijove (behind 2.2 g/cm^2 Al); 100-200 krad/day core | krad | Jovian belt dose (Galileo / extreme) | ResearchGate 3138193; Springer | https://link.springer.com/article/10.1007/s10686-021-09801-0 | sourced |
| ~4.66e-9 (28nm hardened) to ~1e-7 (generic) | upsets/bit/day | SEU rate, GEO | ScienceDirect S0026271417303554 | https://www.sciencedirect.com/science/article/abs/pii/S0026271417303554 | sourced |
| Weibull, beta<1; ~94% at 2 lifetimes -> ~1.1e-5/day | hazard | Satellite reliability (1584 sats) -> factory failure PROXY | Castet & Saleh 2009 | https://www.sciencedirect.com/science/article/abs/pii/S0951832009001094 | **[ESTIMATE]** (satellite proxy) |
| 41.3% failed/partial; 24.2% total | fraction | Small-satellite failure rate (upper bound for immature builds) | NASA NTRS 20190002705 | https://ntrs.nasa.gov/citations/20190002705 | sourced |
| dust: Isc/Pmax fall exponentially with loading | - | Lunar-dust array degradation (functional form) | NASA NTRS 19910020924 | https://ntrs.nasa.gov/citations/19910020924 | sourced (form); [ESTIMATE] rate |
| self-replication error / mutation rate | per copy | Replication fidelity | Freitas & Merkle treat qualitatively | http://www.molecularassembler.com/KSRM.htm | **[GAP]** |
| X_eq = 1 - T_l/T_s (ODE dX/dt = (1/T_l)X(1-X) - (1/T_s)X) | - | Aurora steady-state (VERIFIED) | Carroll-Nellenback et al. 2019, Eqs 28 & 32 | https://arxiv.org/abs/1902.04450 | sourced (verified) |

---

## The verified relations

**Aurora (verified against the paper, symbols corrected):** `X_eq = 1 - T_l/T_s`, where
**T_l = launch/spread time (Eq 30), T_s = settlement lifetime** (the opposite of the
intuitive reading). Plateau (settleable-but-empty systems persist, 0 < X_eq < 1) requires
`T_l < T_s`; as T_s -> infinity, X_eq -> 1 (galaxy fills); at T_l >= T_s the only stable
state is X = 0. Confirmed: T_l/T_s = 0.3/0.5/0.9 -> X_eq = 0.7/0.5/0.1.

**Satellite-proxy hazard [ESTIMATE]:** `lambda = -ln(R)/t = -ln(0.94)/15 yr = 1.13e-5/day`;
round-trips (per-day survival over 15 yr reproduces 0.94). Tag as a satellite analog, not
a measurement, at every use site.

**Array degradation (deterministic):** annual coeff 0.998199 -> 0.18%/yr, 1.43% at 8 yr,
2.67% at 15 yr; worse near the Sun / in Jovian belts.

---

## Proposed API

```python
# Deterministic power path (NO RNG):
def degraded_power(nominal_power_W: float, dose: float, elapsed_days: float,
                   *, on_surface: bool) -> float:
    """Power multiplier g(dose) x dust term. Pure function of state."""

# Seeded stochastic path (uses the EXISTING threaded RNG, in id order):
def step_failures(state, p_fail_per_day: float, dt: float):
    """Draw per active entity from state.rng in id order; drop failures. Returns new state+rng."""

def aurora_equilibrium(t_launch_yr: float, t_settle_life_yr: float) -> float:
    """X_eq = 1 - T_l/T_s (0 if T_l >= T_s)."""
```

---

## Validation plan (verified targets)

- **hazard=0 AND degradation=0 -> results bit-identical to current deterministic
  multi-probe/probe-sim.** The failure-free baseline must be exactly recovered. This is
  the mandatory regression and the guard against RNG contamination.
- death_rate=0 in swarm -> bit-identical to current monotone fill.
- death_rate>0 -> settled fraction rises then plateaus at X_eq < 1 (Aurora); assert the
  plateau exists, sits below 1.0, and higher death rate (larger T_l/T_s) gives lower X_eq.
  Assert `aurora_equilibrium(0.5, 1.0) == 0.5` and clamps to 0 when T_l >= T_s.
- Population under nonzero hazard reaches a BOUNDED steady state (birth = death), not
  unbounded exponential. Assert boundedness.
- Determinism: same seed -> bit-exact replay of failures (no Math.random, no wall clock).
- Degradation: array power at 15 yr = 0.9733 x nominal (2.67% loss); assert monotone
  decline and that it can push a probe below the copy threshold (an aging-power wall).

---

## Interface wiring

- **multi-probe (`fleet.py step`):** add `p_fail_per_day` to params; inside the existing
  id-ordered probe loop (which already threads `rng` for jitter), draw per active probe and
  drop on `u < 1-(1-p)^dt`. Same threaded rng, same order -> bit-exact replay. Add a
  `failed` count to the result.
- **probe-sim power path:** wrap `SolarArray.power_w(distance)` with `degraded_power`
  (deterministic; dose from a heliocentric/Jovian lookup). Feeds `build_rate_kg_per_day`,
  so degradation slows replication (a second, aging-driven power wall). No RNG here.
- **swarm (`sim.py step`):** add `settlement_death_rate_per_year`; each dt, iterate settled
  stars in index order, draw from the seeded rng, reset `settled_year[i] = -1` on death
  (retargeting machinery already exists) -> birth-death balance -> Aurora X_eq.
- **<-> shielding (dose loop):** shielding reduces the dose that drives degradation/failure;
  both consume ONE shared radiation-environment primitive (not two dose models).

---

## Why this is highest-risk, and the guards that contain it

1. **The only module adding RNG.** The failure draws MUST reuse the existing threaded
   generator in deterministic id order, or `speculate`/replay silently break - the
   sneakiest bug the project warns about (ROADMAP Design notes). The `hazard=0` bit-exact
   regression is the tripwire.
2. **Worst over-nesting temptation.** Resist modeling dose -> SEU -> latchup -> subsystem
   -> spacecraft. Everything collapses to a dose-rate lookup, a degradation curve, and a
   scalar hazard. The SEU/MTBF numbers *inform the parameter values*; they are not
   simulation layers.
3. **Proxy honesty.** The discrete-failure hazard is a satellite proxy applied to a
   factory (`[ESTIMATE]`); self-replication mutation rate is a genuine `[GAP]`. Tag both at
   every use site; a satellite is not a self-replicating factory.
4. **Split by kind.** One module, two clean sub-parameters (deterministic degradation
   multiplier; seeded discrete hazard) that compose but do not nest. If either grows a real
   sub-simulation, split then - the seam is cheap now.

Because of (1)-(3), `reliability` is sequenced last among the builds; but note the tension:
CLAUDE.md 3 explicitly *wants* the messiness it adds, and it unlocks the Aurora
steady-state, so there is a case for pulling it earlier once the RNG-purity risk is retired.
</content>
