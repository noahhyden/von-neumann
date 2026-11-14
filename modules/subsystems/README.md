# subsystems - spacecraft subsystem physics

Ten subsystem models that feed the probe, fleet and mission folds. Each is a submodule
(`subsystems.thermal`, `subsystems.transfer`, ...) rather than a module of its own,
because none of them has a presentation surface, a paper, or a second importer.

| Submodule | What it answers |
|---|---|
| `assembly` | Robotic build rate from published metal-AM deposition rates and OEE; the fleet doubling clock, with a 12-274 kg/day band |
| `autonomy` | Onboard compute demand against probe-sim's 1/d^2 supply, and the autonomy wall |
| `comms` | Deep-space downlink rate vs distance, `min(k/d^2, R_max)`, and the data-return wall |
| `isru` | Electrical energy to make oxygen and metal from regolith, and the closure ceiling a body's elements set |
| `power_source` | Solar vs fission vs RTG: the distance crossover `d = sqrt(sp_solar/sp_nuclear)`, and the Pu-238 vitamin wall |
| `propellant` | Reaction-mass demand (Tsiolkovsky), in-situ propellant energy, and the noble-gas import wall |
| `reliability` | Array and dose decay, a seeded per-day hazard fold, and the Aurora steady state `X_eq = 1 - T_l/T_s` |
| `shielding` | Shielding mass from areal-density attenuation: monotonic TID, the non-monotonic GCR dose minimum, and the shared `radenv` primitive |
| `thermal` | Heat rejection and radiator sizing (Stefan-Boltzmann), and the `T^4` leverage of hot radiators |
| `transfer` | Hohmann and impulsive delta-v, synodic windows, and low-thrust Edelbaum trip time |

## Why one module and not ten

A directory per model is the right default when a model is something a reader can be
shown. None of these ten is. Measured over the import DAG before the merge: none had a
frontend surface, none sourced a paper, and nothing outside this set imported any of
them. The only cross-module edges among them (`reliability -> shielding`,
`power_source -> thermal`, `propellant -> transfer`) had both ends inside the set, so
folding turned three cross-module dependencies into ordinary internal imports and lost
no seam that anything else could see.

What ten directories did cost was ten `pyproject.toml` files, ten `uv.lock` files, ten
virtualenvs and ten test suites for about 1900 lines of code, plus ten entries in
`modules/` for a reader to scan before finding the models that do have surfaces.

The rule this follows is in [`modules/README.md`](../README.md): a module earns its own
directory by having a presentation surface, a paper, or two or more importers.

## Interfaces

Depends outward on `vn-core`, `probe-sim`, `power-budget` and `launch-economics`.
Nothing imports `subsystems`, so it sits at the top of the import DAG; if something
comes to depend on one of these submodules, that is the signal to look again at whether
it should be promoted back out.

Each submodule re-exports its public API from its own `__init__.py`, so
`from subsystems.thermal import size_radiator` is the supported form. Reaching past that
into a submodule's internals is the same mistake across submodules as it was across
modules.

## References

Numbers and their sources are in [`REFERENCES.md`](REFERENCES.md), one section per
submodule. That file is the ten former per-module `REFERENCES.md` files concatenated
without edit; nothing was reworded or dropped in the merge.

## Develop

```sh
uv run --extra dev pytest -q              # the whole module
uv run --extra dev pytest -q tests/thermal   # one submodule
```

Test basenames repeat across submodules (every one has a `test_distributions.py`), so
the suite runs under `--import-mode=importlib`, set in `pyproject.toml`.
