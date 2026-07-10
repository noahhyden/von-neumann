# What we have learned

This project is a set of small, independent, source-checked models of self-replicating
space manufacturing. Each one asks a narrow question; together they answer a broader
one: *the leverage of self-replication is real, but it is bounded by physical walls
that reappear at every scale, and we can say which limit binds where.*

Every number below traces to a cited source or is derived by explicit math from numbers
that do (see each module's `REFERENCES.md` and the consolidated
[bibliography](frontend/src/sources.ts)). These are order-of-magnitude research results,
not forecasts. Where the literature has no value, we mark the gap rather than fill it.

---

## 1. Chips are the wall, and it is built of energy as much as supply chain

A lone factory can make its structure but not its electronics. The reason is twofold:
the chip supply chain is the deepest on Earth (400+ process steps, 9-nines-pure
materials, an EUV monopoly), **and** chips are staggeringly energy-hungry to make -
compute logic runs ~8,000 kWh/kg of embodied energy against ~5 kWh/kg for smelted
metal, a gap of roughly three orders of magnitude. A factory escapes the wall only if
it is *both* highly self-sufficient *and* swimming in power. For the 97%-closure lunar
seed, letting it make its own chips cuts time-to-target from ~29 to ~17 years - but only
when fed ~4 MW (a power plant that would outweigh the factory); at ~1 MW, making chips
locally *backfires* and it runs out of electricity before parts. For a 43%-closure
outpost, both paths are traps.
*Module: `closure-sim`. Sources: NASA CP-2255 (1980); Williams, Ayres & Heller (2002); Nagapurkar & Das (2022).*

## 2. The realistic near-term factory never closes on chips

Modern designs put achievable mass closure at ~70% (Shubov 2021) to 90-96% (NASA 1980),
and agree that chasing 100% is not worth it. Imported electronics ("vitamins") are
therefore a permanent design feature, not a temporary compromise on the road to full
autonomy.
*Module: `closure-sim`. Sources: Shubov (2021); NASA CP-2255 (1980); Freitas & Merkle (2004).*

## 3. Thinking is thermodynamically cheap but practically expensive

The Landauer limit (~2.9e-21 J per erased bit at 300 K) sits some 9-11 orders of
magnitude below what real hardware spends per operation. So the binding constraint on a
probe's onboard intelligence is hardware efficiency and waste-heat rejection, not
thermodynamics. The ~20 W human brain is the reference scale for intelligence-per-watt.
*Module: `power-budget`. Sources: Landauer (1961); Berut et al. (2012); Raichle & Gusnard (2002).*

## 4. Launch-mass leverage is the whole economic case, and it scales as 1/(1 - closure)

Because mass balance forces (1 - C) kg of vitamins to be imported per kg the factory
builds, installed-mass-per-launched-mass is exactly 1/(1 - C): about 3x at 67% closure,
about 33x at 97%. The rocket equation makes the cost of *not* doing this exponential in
the Δv to the destination. That exponential is the entire reason to build in place
instead of shipping a finished installation.
*Module: `launch-economics`. Sources: Tsiolkovsky rocket equation; SpaceX published pricing; coupled to `closure-sim`.*

## 5. A solar probe's reach is set by the inverse-square law

Delivered power falls as 1/d^2, from ~1361 W/m^2 at 1 AU to ~50 W/m^2 at Jupiter: at
twice the distance, a quarter of the power - and a quarter of the compute headroom.
Replication stalls at the heliocentric distance where the falling power budget drops
below the probe's build demand. (The full probe factory is blocked on an honest data
gap: no sourced per-module mass breakdown exists for the Borgue & Hein probe, so no
masses are invented to fill it.)
*Module: `probe-sim`. Sources: Kopp & Lean (2011); Borgue & Hein (2020); NASA Planetary Fact Sheet.*

## 6. At fleet scale, two ceilings emerge without being coded in

Run tens of probes as agents and two limits appear on their own. First, the finite
vitamin pool caps the fleet at floor(pool / (1 - C)*seed) copies - the electronics wall
made spatial, tied directly to the launch-mass budget. Second, a spatial power wall:
children disperse outward, 1/d^2 sunlight thins, and expansion stops (~13.6 AU crossover
for the default scenario) not because of parts but because of distance from the Sun.
*Module: `multi-probe`. Reuses `probe-sim` power and `closure-sim` build physics; no new numbers.*

## 7. Filling the galaxy: slingshots dominate, and greedy-nearest beats greedy-boost

A powered settlement front advances at only ~40% of an individual probe's cruise speed
(nearest-hop zig-zag plus settling delay eat the rest). Gravitational slingshots that
steal speed from stellar motion are far faster, reaching ~10^3 km/s - and, reproducing
the source paper, targeting the *nearest* star beats chasing the *maximum boost* on
total exploration time (boost-chasing wastes travel).
*Module: `swarm`. Source: Nicholson & Forgan (2013).*

## 8. Light-speed coordination is a real tax, sized by v/c and hop locality

When probes must decide against a light-delayed *belief* of which stars are already
settled, they race for the same target from stale views and waste trips. Measured over a
32-seed paired ensemble, the median cost versus perfect information is ~30% of the
exploration timescale for nearest-slingshot, ~50% for max-boost, and ~0% for powered
flight. A connected field still fills to 100% - lag alone produces no permanent
"Aurora" plateau. The scale is set by Lambda ~ v/c; whether it bites is decided by how
non-local each hop is. This implements the source paper's own stated future work.
*Module: `swarm` (FRONTIER #1). Sources: Nicholson & Forgan (2013); Olfati-Saber & Murray (2004); Ferrell (1965); RFC 4838.*

## 9. Which constraint binds at which scale (the cross-scale answer)

The factory's own build physics fixes a copy time of ~582 days for the lunar seed - and
that number *is* the local fleet's doubling clock. But the same ~582 days is only ~8e-7
of a ~2-million-year powered galactic fill; measured A/B, manufacturing dwell costs
about 0.4% of exploration time even for fast slingshots. So the cadence that governs a
local fleet is a negligible tax on interstellar exploration, where transit time
dominates. No single module could give this answer - it comes from threading one factory
through all three scales.
*Module: `spine`. Derived from `multi-probe` build physics and `swarm` fill; adds no new numbers.*

---

## The through-line

Read top to bottom, the models trace one argument. Self-replication buys enormous
launch-mass leverage (4), but only if a factory closes on nearly everything except
chips, which it cannot make (1, 2). Autonomy to run far from Earth is limited by
hardware, not physics (3), and how far it can run at all is set by sunlight (5). Scaled
to a fleet, the imported-electronics budget and the inverse-square law become hard
ceilings (6). Scaled to the galaxy, propulsion policy dominates the timeline (7),
light-speed coordination adds a policy-dependent tax (8), and the manufacturing cadence
that ruled the local fleet fades to a rounding error against interstellar transit (9).

Which constraint binds depends on the scale you are asking about - and that is the point
of building the models as separate, honest pieces rather than one fused simulation.
