# subsystems

Spacecraft subsystem physics. One submodule per subsystem.

<!-- BEGIN GENERATED:submodules -->
`subsystems` has **10** submodules.

| Submodule | Purpose | Detail |
|---|---|---|
| `assembly` | the robotic build rate that sets the doubling clock | [docs/assembly.md](docs/assembly.md) |
| `autonomy` | onboard compute demand and the autonomy wall | [docs/autonomy.md](docs/autonomy.md) |
| `comms` | deep-space downlink data rate and the data-return wall | [docs/comms.md](docs/comms.md) |
| `isru` | in-situ feedstock processing | [docs/isru.md](docs/isru.md) |
| `power_source` | solar vs fission vs RTG, and the Pu-238 wall | [docs/power_source.md](docs/power_source.md) |
| `propellant` | reaction mass, its production energy, and propellant closure | [docs/propellant.md](docs/propellant.md) |
| `reliability` | degradation, mortality, and the Aurora steady-state | [docs/reliability.md](docs/reliability.md) |
| `shielding` | radiation shielding mass, and the GCR trap | [docs/shielding.md](docs/shielding.md) |
| `thermal` | heat rejection and radiator sizing | [docs/thermal.md](docs/thermal.md) |
| `transfer` | interplanetary Δv and trip time | [docs/transfer.md](docs/transfer.md) |
<!-- END GENERATED:submodules -->

Regenerate the table with `make modules-readme`; do not edit it by hand.

- Numbers, sources and verdicts: [`REFERENCES.md`](REFERENCES.md), one section per submodule.
- Rules that bind work here: [`../AGENTS.d/`](../AGENTS.d/).

```sh
uv run --extra dev pytest -q              # the whole module
uv run --extra dev pytest -q tests/thermal   # one submodule
```
