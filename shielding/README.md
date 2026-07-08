# shielding - armour against radiation, and when more is worse

Electronics in deep space or in Jupiter's magnetosphere degrade under radiation, and the
defence is mass: shielding. This module turns a radiation dose budget into the shield
mass that meets it - and captures a fact that trips up naive models, that for one of the
two radiation regimes, piling on more shielding makes things *worse*.

## What it models

Built from published areal-density attenuation (no particle-transport code):

- **`radenv.py` - the shared radiation environment.** The GCR/Jovian dose numbers, in one
  place, consumed by both this module and `reliability` (per the proposal's cross-cutting
  note). Two bases kept strictly distinct: TID in rad(Si) for electronics, dose-
  equivalent in mSv for biology.
- **TID electronics shielding (monotonic).** `tid_attenuation_factor` and
  `areal_density_for_tid_budget` - shield until the chips' dose budget is met, using an
  exponential attenuation whose length is fit to Juno's flight anchor (1 cm Ti = ~800x).
- **GCR shielding (NON-monotonic).** `gcr_shielding_is_counterproductive` and
  `recommend_gcr_areal_density` enforce the dose-equivalent minimum near **~20 g/cm^2 Al**:
  beyond it, secondary neutrons make thicker shielding worse, so the module refuses to
  over-shield.
- **Mass and closure.** `shield_mass_kg` (areal density x area x 10) is a BOM line, but
  `closure_contribution_kg` marks locally-built regolith shielding as mass that **raises**
  closure - the opposite of imported vitamins. `regolith_thickness_for_areal_density_cm`
  answers whether cheap COTS parts behind thick local regolith can substitute for imported
  radiation-hardened parts.

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure, deterministic, no pimas,
no RNG (CLAUDE.md 7).

## What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No particle-transport / Monte-Carlo dose code - attenuation is a sourced exponential (TID)
plus the sourced GCR minimum. Material-dependent secondary yields are out of scope (the
regolith-vs-metal equivalence is a tagged `[ESTIMATE]` using areal density as a proxy).

## What it found

- **For GCR, "more shielding is safer" is false.** Dose-equivalent bottoms out near
  20 g/cm^2 and rises again - a model that shielded past it would produce confident
  nonsense, so the module hard-stops there.
- **Shielding is the one mass that helps closure.** Because it can be made from local
  regolith, it raises the locally-built fraction, and thick regolith can stand in for
  imported rad-hardness - letting a factory use cheap COTS electronics behind dirt.

## Interfaces

- **-> `closure-sim`:** shield mass (BOM), and the closure-raising contribution of local
  shielding.
- **shares `radenv` with `reliability`:** one radiation-environment primitive, two
  consumers.
- **<- `power-source` / `mission`:** the environment selects which dose numbers apply.

## Run the tests

```
uv run --extra dev pytest -q
```

9 tests: the areal-density/mass conversion, the Juno ~200 kg and ~800x anchors, TID
monotonicity, the GCR non-monotonic cap at 20 g/cm^2, the regolith-for-metal substitution
at equal areal density, and local shielding raising closure.
