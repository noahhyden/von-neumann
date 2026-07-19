# Where the numbers come from

Every quantity traces to a source below, or is derived from ones that do. Units:
m/s, kg, seconds, USD. Prices are list prices and change over time - they are
scenario *inputs*, documented here, not baked into the model.

## Physics (hardcoded - defined/first-principles only)

- **`G0_M_S2 = 9.80665` m/s²** - standard gravity, *exact by definition* (BIPM/SI).
  Used only to convert specific impulse (s) to exhaust velocity.
- **Tsiolkovsky rocket equation**, `m0/mf = exp(Δv / v_e)` - Tsiolkovsky (1903);
  standard result (e.g. Curtis, *Orbital Mechanics for Engineering Students*, or
  Sutton & Biblarz, *Rocket Propulsion Elements*). Derived, not hardcoded.

## Scenario inputs (representative sourced values - not constants)

### Specific launch cost ($/kg to LEO)

- **Falcon 9 (reusable): ~$3,000/kg.** SpaceX list price ~$69.75M for ~22,800 kg to
  LEO → ~$3,060/kg. Source: SpaceX Capabilities & Services,
  https://www.spacex.com/media/Capabilities&Services.pdf . *Reasonable* - a widely
  cited ballpark; the marginal (internal, reused) cost is lower and not public.
- **Falcon Heavy: ~$1,500/kg.** ~$97M for ~63,800 kg to LEO → ~$1,520/kg (same source).
- **Starship (projected): `[ESTIMATE]`, ~$100–1,000/kg.** SpaceX targets are far
  lower (aspirational <$100/kg); no operational price exists yet. Treat as a wide
  `[ESTIMATE]` until real flight pricing is published.

### Δv budgets (m/s)

Representative one-way budgets, from standard Δv tables (e.g. NASA / Curtis):
- Earth surface → LEO: **~9,300–10,000 m/s** (including gravity and drag losses).
- LEO → trans-lunar injection: **~3,100 m/s**.
- LEO → Mars transfer injection: **~3,600 m/s**.
- LEO → Earth escape: **~3,200 m/s**.

These are inputs to `rocket_equation_mass_ratio`; a scenario must cite the specific
budget it uses.

### Specific impulse, Isp (s)

- LOX/RP-1 chemical: **~280–340 s** (e.g. Merlin 1D ~282 s sea level, ~311 s vacuum).
- LOX/LH2 chemical: **~450 s** (e.g. RS-25 ~452 s vacuum).
- Electric/ion: **~1,500–4,000 s**.
- Source: Sutton & Biblarz, *Rocket Propulsion Elements*; manufacturer data. Inputs,
  not constants.

## Value (value.py - the output side of the case)

The `value` candidate from `ROADMAP-PROPOSAL.md` is folded in here rather than built as a
module, because only one output survives the iron rule.

### The defensible output (no new numbers)

- **Launch-cost-avoided value** = `local_mass_produced_kg × cost_per_kg_usd`. Definitional
  arithmetic over the specific launch cost already sourced above (`output_value_launch_avoided_usd`);
  it is the same computation as `launch_cost_usd`, read as value *returned* rather than
  *paid*. No new number is introduced.

### The honesty backbone (sourced anchors, used only to debunk the headlines)

These numbers exist to show the "$X quintillion asteroid" figures are arithmetic fictions;
they are NOT modelled as returns (PGM/settlement/$-per-bit value are `[ESTIMATE]`/`[GAP]`).

- **`PLATINUM_MARKET_ANNUAL_USD = 7.25e9`** - the entire global platinum market was worth
  ~USD 7.25 billion in 2024. Source: Statista global platinum industry,
  https://www.statista.com/topics/3039/platinum/ ; market-report figures (~$7.25B 2024).
  Verdict: sourced.
- **`PLATINUM_ANNUAL_PRODUCTION_T = 175`** - world platinum mine production ~170-179 t/yr
  (2024-2025). Source: Statista global platinum mine production,
  https://www.statista.com/statistics/1170691/mine-production-of-platinum-worldwide/ .
  Verdict: sourced.
- **`PSYCHE_QUOTED_VALUE_USD = 1.0e19`** - the widely-quoted "$10 quintillion" value of
  asteroid 16 Psyche's metal at spot prices. Sources: Newsweek,
  https://www.newsweek.com/psyche-asteroid-mission-10-quintillion-valuable-metals-nasa-1989659 ;
  HowStuffWorks, https://science.howstuffworks.com/psyche-16-asteroid.htm (which itself
  notes the value is meaningless because that much metal "would immediately render metals
  valueless on the markets"). Verdict: sourced (the headline to debunk, not an endorsed
  value).
- **Derived debunk:** `market_absorption_years(1e19) = 1e19 / 7.25e9 = 1.4e9 years` - it
  would take over a billion years to sell 16 Psyche's metal at the current market's annual
  turnover. `realizable_value_ceiling_usd(years) = years × market` caps what any commodity
  can actually realize far below the raw spot-price-times-tonnage figure. The point: value
  is bounded by what a market can absorb, not by tonnage.

## Notes

- The **launch-mass leverage** (`target / (seed + vitamins)`) links directly to
  `closure-sim`: the vitamin mass is set by mass closure, so higher closure → fewer
  vitamins → more leverage. Coupling the two is future work (see README).

## Further reading and cross-checks (bibliography)

Sources that ground this module's ideas or cross-check its numbers, consolidated in the project bibliography (frontend/src/sources.ts) and shown on the site's Sources page. These add context; they are not new numbers in the code.

- **Sutton & Biblarz 2016** - G. P. Sutton & O. Biblarz (2016). Rocket Propulsion Elements (9th ed.). Wiley, ISBN 978-1-118-75365-1. https://www.wiley.com/en-us/Rocket+Propulsion+Elements,+9th+Edition-p-9781118753651. The standard text behind the rocket equation and the chemical specific-impulse ranges the scenarios use (LOX/RP-1 ~280-340 s, LOX/LH2 ~450 s). Pins the previously bundled Sutton & Biblarz mention to a specific edition.
- **Curtis 2020** - H. D. Curtis (2020). Orbital Mechanics for Engineering Students (4th ed.). Butterworth-Heinemann (Elsevier), ISBN 978-0-12-824025-0. https://shop.elsevier.com/books/orbital-mechanics-for-engineering-students/curtis/978-0-12-824025-0. Grounds the rocket-equation derivation and the representative delta-v budgets (surface-to-LEO ~9.3-10 km/s, LEO-to-TLI ~3.1 km/s, LEO-to-Mars ~3.6 km/s) that drive the mass-ratio computation.
- **Jones 2018** - H. W. Jones (NASA Ames) (2018). The Recent Large Reduction in Space Launch Cost (ICES-2018-81). 48th International Conference on Environmental Systems; NASA NTRS 20200001093. https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20200001093.pdf. An independent, NASA-authored cross-check on the module's $/kg-to-LEO scenario inputs: Shuttle ~$54,500/kg vs Falcon 9 ~$2,720/kg, a roughly 20x reduction. Corroborates the SpaceX vendor list price with an agency analysis.
- **Goebel & Katz 2008** - D. M. Goebel & I. Katz (JPL) (2008). Fundamentals of Electric Propulsion: Ion and Hall Thrusters. JPL Space Science and Technology Series, Wiley, DOI 10.1002/9780470436448. https://onlinelibrary.wiley.com/doi/book/10.1002/9780470436448. The standard text grounding the electric / ion specific-impulse band (~1,500-4,000 s) - the high-Isp end that makes deep-space transfer far cheaper in propellant than chemical.
- **NEXT-C 2021** - NASA Glenn Research Center (NEXT-C flight team) (2021). A Summary of the NEXT-C Flight Thruster Proto-flight Testing. NASA NTRS 20210018563 / AIAA. https://ntrs.nasa.gov/api/citations/20210018563/downloads/NEXT-C%20AIAA%20Paper%202021%20FINAL.pdf. A flight-qualified data point at the top of the electric Isp range: ~4,190 s at 6.9 kW, flown on DART (2021). Shows the upper electric-Isp bound is a demonstrated value, not just a textbook span.
- **Borowski et al. 2012** - S. K. Borowski, D. R. McCurdy & T. W. Packard (NASA Glenn) (2012). Nuclear Thermal Rocket (NTR) Propulsion: A Proven Game-Changing Technology for Future Human Exploration Missions. NASA NTRS 20120009207. https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20120009207.pdf. Fills the Isp gap between chemical (~450 s) and electric (thousands of s): nuclear thermal at ~900 s, an intermediate propulsion option for moving seed mass with less propellant penalty.

## Analytical companion (issue #50, Phase 2 pilot)

`docs/FINDINGS_CLASSIFICATION.md` #21 asserts that mass leverage tends to
`1 / (1 - C)` in the small-seed limit. Derivation:

Let M be the target installed mass, s the seed mass, and C the closure ratio.
The mass built locally is `M - s`; each locally-built kilogram needs `1 - C`
kg of imported vitamins. Launched mass:

    L = s + (1 - C) * (M - s)  =  s*C + (1 - C)*M

Leverage:

    G(s, C) = M / L  =  1 / (s*C/M + (1 - C))

With `eps := s / M` as the small parameter, expanding at fixed C in (0, 1):

    G(0, C) = 1 / (1 - C)
    G(eps, C) = 1/(1-C) - eps * C / (1-C)^2 + O(eps^2 / (1-C))

Boundaries:
- `C = 0`: G = 1 (launch everything).
- `C = 1`: G = M / s, unbounded as `s -> 0`.

The test `tests/test_analytical_companions.py` asserts sim agrees with the
closed form to `1e-9` relative at points, monotone approach to the asymptote
as `eps -> 0`, and the leading-order correction to `O(eps^2 / (1-C))`.
