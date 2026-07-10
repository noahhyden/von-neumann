# Where the numbers come from

`spine` introduces **no physical numbers of its own.** It is an *integrator*: it threads
one closure-sim `Factory` through three existing folds and routes a quantity the factory
already fixes to the one scale that used to guess it. Every number it reports therefore
traces to a sibling module's `REFERENCES.md`, or is derived by explicit math from those.

| Quantity (in spine) | How it is obtained | Source of truth |
| --- | --- | --- |
| `closure_ratio` | `closure_sim.compute_closure(factory)` on the shared factory | [`../closure-sim/REFERENCES.md`](../closure-sim/REFERENCES.md) |
| `single_factory_time_to_target_days` | `closure_sim.simulate(factory, factory.replication)` | [`../closure-sim/REFERENCES.md`](../closure-sim/REFERENCES.md) |
| `copy_time_days` | `multi_probe.time_to_build_one_copy_days(params_from_factory(factory), 1 AU)` = `closure_ratio · seed_mass / min(machinery, energy_cap)` | [`../multi-probe/REFERENCES.md`](../multi-probe/REFERENCES.md) (seed mass, machinery rate, array), which itself derives from closure-sim + probe-sim |
| `settle_time_years` | `copy_time_days / 365.25` (see the year basis below) | derived from `copy_time_days` |
| fleet doubling / population / binding | `multi_probe.simulate_fleet(params_from_factory(factory))` | [`../multi-probe/REFERENCES.md`](../multi-probe/REFERENCES.md) |
| swarm `t100_years`, `final_settled`, the dwell tax | `swarm.simulate_swarm(...)` with `settle_time_years` set to the derived value | [`../swarm/REFERENCES.md`](../swarm/REFERENCES.md) |

## The one derived constant

- **`DAYS_PER_JULIAN_YEAR = 365.25`** - the Julian year (1 yr = 365.25 d = 3.15576e7 s).
  This is not a free choice: it is the **same** year basis the swarm uses for its speed of
  light `C_PC_PER_YEAR` (`swarm/models.py`), so converting the factory's build time from
  days to years puts the manufacturing dwell on the same clock as the swarm's light-years.
  Conversion shown: 3.15576e7 s / 86400 s-per-day = 365.25 days.

## What spine *derives*, and why it is not a new number

The swarm's per-star **manufacturing dwell** (`settle_time_years`: how long a freshly
settled probe spends building offspring before they depart) was, before this module, an
ungrounded `[ESTIMATE]` defaulted to **0.0** - i.e. the front was assumed to replicate
instantaneously. `spine` replaces that guess with a *derivation*:

> A settled probe orbits a Sun-like star (Nicholson & Forgan's uniform field is Sun-like
> stars at 1 star/pc³) and must build one offspring's worth of *local* structure before it
> can launch children. That time is exactly the fleet's 1-AU copy cadence - the same
> closure-sim `min(machinery, energy_cap)` regime - in years.

Every input to that derivation is already sourced (closure ratio, seed mass, machinery
rate, and the solar array all live in closure-sim / probe-sim / multi-probe references).
So the dwell is now a *derived* quantity with a formula, not an assumption. The one modelling
choice - that a settled probe builds at the same 1-AU insolation the fleet model uses -
is stated here and is consistent with N&F's Sun-like field.

## The finding this grounds

With the dwell derived rather than zeroed, the front-fill time changes by a *measurable but
negligible* amount. Two quantities describe it, and they must be kept apart (a scrutiny finding
corrected in this pass):

- the **per-copy ratio** `f = tau / T100` - one build cadence against the whole fill. Powered:
  `f ~ 8.5e-7` (event-resolved, 1200-star field), under one part in a million.
- the **cumulative tax** `(T100_with - T100_zero) / T100_zero` - the fractional slowdown of the
  whole fill when the dwell is switched on. This is the physical cost of manufacturing on the
  timeline, and it is `f` times the number of settlements on the critical path (~18 for powered
  here). Powered: `~1.5e-5` (under one part in fifty thousand) - still negligible, but ~18x `f`.

The cumulative tax is ordered by probe speed (faster front -> shorter fill -> larger share):

- **powered** (3e-5 c): cumulative tax ~1.5e-5 at nominal; unresolvable by brute force.
- **slingshot-nearest** (accumulated speed to the 0.05 c cap): the dwell costs a median of
  ~0.32% of the fill (measured A/B over a 24-seed ensemble; IQR 0.26-0.36%). The single-seed
  value quoted earlier (~0.4%) is one draw from this distribution.
- **slingshot-maxboost**: positive but within seed-to-seed noise at the field size affordable
  here; reported as unresolved rather than as a point estimate.

The **robustness margin** is stated on the cumulative tax, not `f`: for the powered galactic
fill the cumulative cost stays under 1% until the copy time is ~a few hundred times nominal
(about two orders of magnitude; `f` alone would suggest ~15,000x, i.e. four orders, which
overstates it by the critical-path factor). For the fastest slingshot fronts the margin is only
~3x, because the nominal tax there is already ~0.3%.

**The copy time is machinery-limited at 1 AU.** For the default seed `min(machinery, energy_cap)`
= min(20 kg/day, ~3700 kg/day) = the 20 kg/day machinery rate; the energy cap is ~190x higher
(its `1/d^2` branch binds only past ~13.7 AU). So the copy time is set by the machinery build
rate and `C*m_seed`, and is insensitive to insolation and the [ESTIMATE] array efficiency across
essentially the whole target population (source: [`../multi-probe/REFERENCES.md`](../multi-probe/REFERENCES.md)).

These derived results are computed and committed by the reproducibility harness under
`experiments/` (`measure.py` -> `results/*.json`), and welded to the fold by
`tests/test_measure_results.py`. They introduce no new physical constant - each is
`derive_settle_time_years` fed into `swarm.simulate_swarm`, both already sourced above. See
[`SCRUTINY.md`](SCRUTINY.md) for the claim-by-claim plan and
[`../papers/spine/SCRUTINY.md`](../papers/spine/SCRUTINY.md) for the post-hoc adversarial review.

The physics: interstellar transit time dwarfs manufacturing time, so the same build cadence
that *is* the clock for a local fleet (transit is days) is a vanishing tax on galactic
exploration - and the faster the probe, the larger (still tiny) that tax, because faster
transit shrinks the hop time the dwell competes with. No `[GAP]` or `[ESTIMATE]` is
introduced by spine; it removes one (the swarm's 0.0 dwell) by grounding it.
