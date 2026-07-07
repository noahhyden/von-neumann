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
negligible* amount, and the size of that change is ordered by probe speed:

- **powered** (3e-5 c): the ~1.6 yr dwell is ~8e-7 of the ~2e6 yr fill - unresolvable by
  brute force, negligible by orders of magnitude.
- **slingshot-nearest** (accumulated speed to the 0.05 c cap): the dwell costs ~0.4% of the
  fill (measured A/B, `measure_dwell_tax`, fine timestep on a small field).

The physics: interstellar transit time dwarfs manufacturing time, so the same build cadence
that *is* the clock for a local fleet (transit is days) is a vanishing tax on galactic
exploration - and the faster the probe, the larger (still tiny) that tax, because faster
transit shrinks the hop time the dwell competes with. No `[GAP]` or `[ESTIMATE]` is
introduced by spine; it removes one (the swarm's 0.0 dwell) by grounding it.
