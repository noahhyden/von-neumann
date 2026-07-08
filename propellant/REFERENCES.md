# Where the numbers come from

Every quantity in `propellant` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: m/s, kg, seconds, kWh, tonnes. Delta-v and Isp are inputs (from
`transfer` and `launch-economics`); this module adds production energy and the propellant-
closure axis.

## Reaction-mass demand (reused, not re-derived)

- **Tsiolkovsky rocket equation** `m0/mf = exp(Delta_v / v_e)` - reused from
  `launch-economics` (`rocket_equation_mass_ratio`, `exhaust_velocity_m_s`,
  `propellant_fraction`), not re-implemented. The Delta-v is supplied by `transfer`
  (`hohmann_transfer` / `edelbaum_delta_v_m_s` / `sep_transfer`). Verdict: derived from
  sourced siblings; a test round-trips `reaction_mass_kg` against both.
- **Isp bands** (route presets): LOX/LH2 chemical ~450 s; water electrothermal ~300 s;
  xenon Hall EP ~1800 s; xenon ion EP (NEXT-C) ~4190 s. Source: `launch-economics/
  REFERENCES.md` (Sutton & Biblarz; Goebel & Katz; NEXT-C). Verdict: sourced.

## Production energy (water route)

- **`HHV_HYDROGEN_KWH_PER_KG = 39.4`** - higher heating value of hydrogen, 142 MJ/kg =
  39.4 kWh/kg. The thermodynamic total (electrical + thermal) to dissociate water into
  H2 + O2 at standard conditions. Source: Electrolysis of water, Wikipedia,
  https://en.wikipedia.org/wiki/Electrolysis_of_water (HHV 39.4 kWh/kg; Gibbs dG =
  -237.1 kJ/mol behind the 1.23 V minimum). Verdict: sourced (thermodynamic).
- **`HYDROGEN_MASS_FRACTION_OF_WATER = 2.016/18.015 = 0.1119`** - from standard atomic
  masses (H 1.008, O 15.999). Derived.
- **`water_electrolysis_hhv_min_kwh_per_kg() = 39.4 x 0.1119 = 4.41 kWh/kg water`** -
  the thermodynamic floor to electrolyse 1 kg of water (matching the proposal's 4.41).
  Derived, shown. Verdict: derived from the two sourced values above.
- **`KORNUTA_FULL_CHAIN_KWH_PER_KG = 11.3`** - practical mining-to-liquefaction chain for
  water-ice propellant (Kornuta et al.), well above the electrolysis-only floor. Same
  figure `isru` cites for the water-ice LOX route (the shared literature value; the seam
  is kept clean - isru does regolith->parts, propellant does water-ice->reaction mass).
  Verdict: sourced. (Real electrolysers alone run ~50-55 kWh/kg H2 ~ 5.6-6.2 kWh/kg
  water; the full chain adds mining and liquefaction.)

## The noble-gas import wall

- **`XENON_WORLD_SUPPLY_T_PER_YR = (40, 60)`** - Earth's entire annual xenon production is
  ~40-60 tonnes/year (extracted from air; ~1 part in 11.5 million). Sources: Xenon,
  Wikipedia, https://en.wikipedia.org/wiki/Xenon (~60 t/yr); industry figures (~40 t/yr).
  Verdict: sourced (range).
- **NASA anchor:** "a xenon propellant load of 10 metric tons represents greater than 10%
  of the global annual production rate of xenon" and a single such buy disrupts the
  market. Source: Xenon Acquisition Strategies for High-Power Electric Propulsion NASA
  Missions, NTRS 20150023080, https://ntrs.nasa.gov/api/citations/20150023080/downloads/20150023080.pdf .
  Verdict: sourced (primary). `xenon_supply_fraction(10)` reproduces this (10/60 = 16.7%
  > 10%).

## Propellant closure (the new axis)

- **Definition (derived):** `propellant_closure` = fraction of a route's reaction mass
  obtainable locally. Water routes = 1.0 on a water-bearing body (both H and O local),
  0.0 on a dry body; noble-gas EP = 0.0 anywhere (xenon/krypton are not extractable
  off-world in bulk). This is a distinct axis from structural mass closure (isru/
  closure-sim): a probe can close its structure yet still be tethered to Earth by
  propellant.
- **The trade (derived, shown):** for a fixed Delta-v, high-Isp xenon EP drives
  propellant *mass* down (Tsiolkovsky) but leaves 100% of it imported; a water route
  carries more mass but imports none on a water body. `imported = (1 - closure) x mass`.

## `[ESTIMATE]` / basis notes

- Isp presets are representative points within sourced bands; a scenario should pick and
  cite its own. Water-EP Isp varies widely by thruster type.
- Xenon supply is a range; krypton (cheaper, ~8x more abundant) is an alternative not
  modelled here - the wall is specific to xenon, the highest-performance choice.

## Interface wiring

- **<- transfer:** consumes the Delta-v from `hohmann_transfer` / `edelbaum_delta_v_m_s`.
- **reuses launch-economics:** the rocket equation and g0 (single source of truth).
- **shares Kornuta's water-ice energy with isru** (same literature figure; distinct
  seam - do not merge the modules).
- **-> closure-sim / mission:** propellant closure and imported-propellant mass are a new
  import term alongside structural vitamins; the xenon wall caps EP-fleet size.

## Further reading (bibliography)

- **Kornuta et al. 2019** - Commercial lunar propellant architecture. New Space / full-
  chain water-ice-to-propellant energy (~11 kWh/kg), the practical anchor above.
- **NASA NTRS 20150023080** - Xenon Acquisition Strategies for High-Power Electric
  Propulsion. The 10 t = >10% of world supply anchor behind the import wall.
