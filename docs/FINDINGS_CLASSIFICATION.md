# Findings classification (issue #50, Phase 1)

Companion to `FINDINGS.md`. That document is prose about what the models
show; this one is a **classification table** for issue #50's Phase 1 - which
of those claims plausibly have a closed form, which have a rigorous bound,
and which are irreducibly numerical.

The Phase-1 output is this table. It tells us where to spend Phase 2
derivation effort, and it is a research output on its own: ranking a claim
as **C** (numerics-native) is an intentional call, not a placeholder.

## Classification

- **A** - plausibly closed form under stated assumptions. A Phase-2 derivation
  should reproduce the sim's answer exactly (within float tolerance) or
  explain the discrepancy.
- **B** - plausibly has a rigorous bound (asymptotic, upper, or lower). A
  Phase-2 derivation may not give the point value but should bracket it.
- **C** - genuinely requires numerics. Nonlinear coupling, discrete
  combinatorics, or path-dependence beyond what algebra holds. Simulation
  remains the workhorse; a derivation is not the goal.

## Inventory

| # | Module / slug | Claim | Where | Regime | Class |
|---|---|---|---|---|---|
| 1 | closure-sim / lunar-closure | Lunar-regolith seed ~97% self-sufficient; chips ~1.25% by mass | closure-sim/README.md | Sourced lunar BOM | A |
| 2 | closure-sim / chip-lift | Time-to-target drops 29 yr -> 17 yr with local chips (needs ~4 MW) | closure-sim/README.md | 3-regime min(machinery, power, resupply) | C |
| 3 | multi-probe / spatial-power-wall | Fleet stops expanding at ~13.6 AU (default) | multi-probe/README.md | 1/d^2 solar x closure-sim | A |
| 4 | multi-probe / build-rate-anchor | ~20 kg/day machinery cap near Sun | multi-probe/README.md, assembly/README.md | Fixed-probe, near-Sun WAAM | A |
| 5 | swarm / front-speed-40pct | Settlement front ~40% of one probe's speed | swarm/README.md, REFERENCES.md | Nearest-hop, 1 star/pc^3 uniform | **C (reclassified from B - see note)** |
| 6 | swarm / coordination-tax | Fuel tax ~ Λ = v/c; slope 0.95, ratio 1+Λ | swarm/REFERENCES.md | Powered, N=500, event step | B |
| 7 | swarm / finite-size-decline | Tax fraction 19.0%->13.1% over N=300..4800 | swarm/REFERENCES.md | Λ=0.2, powered | C |
| 8 | spine / copy-time-582d | Derived copy time ~582 days | spine/README.md, assembly/README.md | C * M_seed / build_rate | A |
| 9 | spine / dwell-negligible | Powered dwell ~8e-7 of 2 Myr fill; <1% until copy-time is 15000x nominal | spine/README.md | Powered policy | A/B |
| 10 | spine / slingshot-dwell-tax | Measured median tax ~0.32% (nearest slingshot) | spine/README.md | 24-seed A/B ensemble | C |
| 11 | reliability / aurora-plateau | Steady-state settled fraction = 1 - T_l/T_s | reliability/README.md | Carroll-Nellenback 2019 Eq. 32 | A |
| 12 | reliability / array-derate | ~0.2-0.5%/yr solar-array loss -> ~5% over 17 yr | reliability/README.md | Flight-anchored compounding | A |
| 13 | assembly / rate-band | LPBF 2.9 / WAAM 20.4 / NASA-1980 274 kg/day | assembly/README.md | Multiplicative OEE | A |
| 14 | thermal / T4-leverage | 530 K radiator ~10x lighter/kW than 300 K | thermal/README.md | Stefan-Boltzmann, 3 kg/m^2 | A |
| 15 | thermal / ISS-anchor | 35 kW at 275 K -> 67.5 m^2 vs measured 70.3 m^2 (4%) | thermal/README.md | Two-sided eps*sigma*T^4 | A |
| 16 | transfer / Hohmann-anchors | Earth-Mars 5.59 km/s / 259 d; Earth-Jupiter 14.4 km/s / 2.7 yr | transfer/README.md | Coplanar circular | A |
| 17 | transfer / SEP-vs-Hohmann | SEP spiral Δv >= Hohmann (5.66 vs 5.59) | transfer/README.md | Constant-thrust | A |
| 18 | comms / DSOC-fit | k~56, two DSOC anchors agree to 2.5%; crossover d ~ 0.46 AU | comms/README.md | Friis-Shannon | A |
| 19 | isru / LOX-energy | 24.3 ± 5.8 kWh/kg LOX; iron 2.6-4.0 kWh/kg | isru/README.md | H2-reduction chain | A |
| 20 | isru / closure-ceiling | Lunar C <= mass-fraction of parts w/o C/H/N | isru/README.md | Composition accounting | A |
| 21 | launch-economics / leverage-1over1mC | Leverage -> 1/(1-C) in the seed << target limit | launch-economics/README.md | Mass balance | **A (Phase-2 pilot, this PR)** |
| 22 | launch-economics / propellant-93pct | LEO's ~9.4 km/s -> 93% propellant fraction | launch-economics/README.md | Tsiolkovsky, one stage | A |
| 23 | power-budget / Landauer-slack | 9-11 OOM slack over k_B T ln 2 at 300 K | power-budget/README.md | k_B T ln 2 | A |
| 24 | power-source / crossover-4AU | Crossover = sqrt(sp_solar_1AU / sp_nuclear) ~ 3.9-4.4 AU; power-independent | power-source/README.md | 1/d^2 solar | A |
| 25 | power-source / Pu-238-wall | 8.1 kg per GPHS-RTG vs 0.5-1.5 kg/yr supply | power-source/README.md | Isotope arithmetic | A |
| 26 | probe-sim / operational-range | Bisection on distance where regime flips | probe-sim/README.md | Composed with closure-sim | C |
| 27 | propellant / HHV-floor | 4.41 kWh/kg water-electrolysis floor | propellant/README.md | HHV(H2) * mass fraction | A |
| 28 | propellant / xenon-wall | Global Xe 40-60 t/yr; 10-t load > 10% supply | propellant/README.md | Import accounting | A |
| 29 | shielding / GCR-min-20 | Dose-equivalent bottoms out ~20 g/cm^2 then rises | shielding/README.md | Sourced GCR curve | B |
| 30 | autonomy / wall-sqrt | Wall AU = sqrt(P_1AU / P_req) | autonomy/README.md | 1/d^2 power | A |

## Phase 2 backlog (ranked by leverage)

**High-leverage class-A closed forms (fastest to formalize):**
- **#21 launch-economics leverage 1/(1-C)** - cleanest one-liner. Formalized
  as this PR's pilot; sets the pattern for the rest.
- **#24 power-source crossover d\* = sqrt(sp_solar/sp_nuclear)** - non-obvious
  that power cancels; a genuinely surprising A-result.
- **#30 autonomy wall = sqrt(P_1AU/P_req)** - identical shape to #24 from the
  demand side; publishing both together shows the 1/d^2 law twice.
- **#14/#15 thermal T^4 leverage + ISS anchor** - one formula plus one anchor.
- **#8/#9 spine copy-time + dwell fraction** - pure composition of #1, #4, #21
  plus a clock conversion.
- **#11 aurora plateau** - already closed form from CN-2019; restate with the
  collapse condition `T_l < T_s`.

**High-leverage class-B (biggest scientific payoff):**
- **#6 swarm coordination-tax ~ Λ** - the derivation `waste_ls / waste_inst
  = 1 + v/c` is in prose in `swarm/REFERENCES.md`; formalizing as a numbered
  equation with the collision-exposure argument is the headline follow-up
  target.
- **#5 swarm front-speed 40pct** - classical spreading-process; likely a
  rigorous asymptotic exists.

**Class-C (numerics-native, skip for Phase 2):**
- #2 (chip lift), #7 (finite-size tax decline), #10 (slingshot dwell tax),
  #26 (probe-sim operational range). These are where simulation is the right
  tool; a "why numerics" companion belongs in paper prose, not a derivation
  attempt.

**Class-C reclassification: #5 swarm front-speed 40pct.** Initially ranked B
on the guess that spreading-process asymptotics might give a rigorous
front-speed coefficient. On inspection the "40%" is genuinely numerical: it
mixes hop-length geometry (nearest-neighbor 3D Poisson), the zig-zag angle
distribution, and dwell time. Trivial bounds are available (`v_front <= v`
absolute upper; `v_front > 0` when settle_time is finite) but neither pins
the ~0.4 coefficient. This is the point of the Phase-1 classification: the
promotion from B to C is itself a finding.

## Convention for a Phase-2 derivation

Adopted by this PR as the pilot; every subsequent Phase-2 companion follows
the same shape:

1. State the assumptions (regime, dimensionless small parameter).
2. Derive symbolically. The module's `REFERENCES.md` carries the numerical
   inputs.
3. State the resulting closed form.
4. Add a test that instantiates the sim at the derivation's assumptions and
   asserts the two agree to a stated tolerance.
5. Reference the derivation from the module's `REFERENCES.md`.

Non-goals for Phase 2 (already in the issue text, restated here):
- No formal proof assistants. Pencil-and-paper derivations are the deliverable.
- Not "replace simulation." Simulation remains the workhorse for class C.
- Not "derive everything." A C-classification is a valid finding.
