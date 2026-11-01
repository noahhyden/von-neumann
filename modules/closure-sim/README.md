# closure-sim

**A small tool for asking: could a factory in space build copies of itself?**

Imagine landing a single robotic factory on the Moon. It digs up local dirt, makes
metal, and uses that metal to build a *second* factory just like itself. Then two
become four, four become eight. This is the dream of "self-replicating" space
manufacturing - and the reason people get excited about it is that, in principle,
you only have to launch *one* factory and let it multiply.

The catch is that no factory can make *everything* it's built from. Some parts -
above all **computer chips** - need a supply chain so vast (hundreds of factories,
ultra-pure materials, machines that cost hundreds of millions of dollars) that a
lone factory in space has no hope of making them. Those parts have to keep coming
from Earth. This tool calls them **"vitamins"** (a term from the original 1980 NASA
study): small but essential things you must keep shipping in.

`closure-sim` lets you describe a factory as a parts list, then answers:

1. **How self-sufficient is it?** What fraction of its own weight can it make
   locally, and which parts are the vitamins?
2. **How fast could it multiply?** Starting from one seed, does it grow explosively,
   crawl along slowly, or stall out - and why?
3. **What if it could make its own chips?** The headline question: how much does
   being able to make electronics locally change everything?

It prints clean tables in your terminal. No graphics, no internet, no setup beyond
installing it. It's **module 1** of a larger project, deliberately kept small and
well-tested. Every number is grounded in real research - see
[REFERENCES.md](REFERENCES.md).

---

## The one idea you need: "closure"

**Closure** is the share of a factory's own weight it can build from local
material. If a factory is 90% closed, it makes 90% of itself and imports 10% as
vitamins.

Here's why closure is the whole game, in everyday terms:

- To build a *new* copy, the factory needs both **local parts** (which it makes
  itself, as fast as its machines and power allow) and **vitamins** (which only
  arrive on the next rocket from Earth).
- The local parts can grow *with* the factory: more factory means more machines
  making more parts - this is the explosive, doubling-every-year kind of growth.
- But the vitamins arrive at a **fixed trickle** from Earth, no matter how big the
  factory gets. So the vitamins become the bottleneck. The factory can only grow as
  fast as its slowest-arriving essential part.

**The closer a factory gets to 100% closure, the smaller its vitamin needs, and the
longer it can keep growing explosively.** A factory that's only 50% closed is
forever rationed by the rocket schedule. A factory that's 99% closed is nearly
unstoppable. That tipping point is what this tool lets you explore.

> **A trap to watch for:** measuring closure by *weight* makes electronics look
> trivial - chips might be 1% of the factory's mass. But that 1% can be the
> difference between a factory that multiplies and one that's stuck. This tool
> always shows you the vitamins *and* how badly they throttle growth, not just the
> headline percentage.

<details>
<summary>The actual math, for the curious (optional)</summary>

Let `C` = closure (0 to 1), `F` = installed factory mass, `R` = vitamin resupply
rate (kg/day), `α` = productivity (kg/day of output per kg of factory). Building new
factory mass needs local and vitamin inputs in ratio `C : (1−C)`, giving three
possible "speed limits" on growth:

| limit | growth rate | behavior |
|---|---|---|
| material (machines) | `(α·F)/C` | grows with the factory → **exponential** |
| energy (power) | `power ÷ energy-per-kg` `/ C` | fixed → linear |
| resupply (vitamins) | `R/(1−C)` | fixed → linear |

The **slowest** of the three sets the pace. Early on, the factory is small so the
material limit is low and growth is exponential. As it grows, it eventually hits
either the fixed energy ceiling or the fixed resupply ceiling and flattens to linear
growth. As `C → 1`, the resupply ceiling `R/(1−C) → infinity` and growth never has
to flatten. That's the regime change the simulator captures.
</details>

---

## Install

You need Python 3.12. The easiest way (using [uv](https://docs.astral.sh/uv/)):

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"     # "[dev]" also installs the test tools
.venv/bin/pytest               # optional: run the 19 tests
```

(Plain `pip install -e ".[dev]"` works too inside any Python 3.12 environment.)

## Try it

Three commands, each takes a scenario file:

```bash
closure-sim closure   scenarios/lunar_regolith_seed.yaml   # how self-sufficient is it?
closure-sim replicate scenarios/lunar_regolith_seed.yaml   # how fast does it grow?
closure-sim wall      scenarios/lunar_regolith_seed.yaml   # what if it made its own chips?
```

You can tweak the assumptions without editing files, e.g.:

```bash
closure-sim wall scenarios/lunar_regolith_seed.yaml --power 1000   # try 1 MW instead of 4
```

(`--power`, `--target`, `--resupply`, `--cadence`, `--duration`.)

---

## The headline result: the electronics wall

The `wall` command runs the scenario twice - once with electronics shipped from
Earth, once pretending the factory can make its own chips - and compares them. The
two example scenarios tell **opposite** stories, and together they capture the real
dilemma:

### Story 1 - the lunar seed: making chips locally *wins* (if you have the power)

This factory is 97% self-sufficient; chips are just 1.25% of its weight. As long as
chips are imported, the rocket schedule caps its growth and it takes **~29 years** to
reach the target output. Give it the ability to make its own chips and that cap
lifts - it gets there in **~17 years**, over a decade sooner.

**But** there's a catch the tool makes visible: chips take *thousands* of times more
energy to manufacture than metal. Making them locally only pays off if the factory
has enormous power - about 4 megawatts in this scenario (a power plant that would
itself weigh more than the factory). Run it with `--power 1000` and you'll see making
chips locally actually *backfires*: the factory runs out of electricity before it
runs out of parts.

### Story 2 - the low-closure outpost: a trap from both sides

This factory is only 43% self-sufficient and stuffed with electronics. Shipping the
chips in, it's permanently starved for resupply - a slow crawl. Trying to make the
chips locally is even worse: their colossal energy appetite collapses the factory's
power budget. **Closure went up, but things got worse.** It's stuck either way.

**The lesson both stories share:** chips aren't a vitamin by accident. They're a
vitamin because making them is both supply-chain-deep *and* staggeringly
energy-hungry. A factory only escapes the wall if it's already highly self-sufficient
*and* swimming in power.

---

## Write your own factory

A scenario is a plain text file (YAML). List the parts; mark anything the factory
can't make locally with `producible_locally: false` - those become vitamins. Add a
`replication:` block to enable the growth simulation.

```yaml
name: My Seed Factory

subsystems:
  - name: Structure (metal from local rock)
    mass_kg: 3000
    category: structure            # structure | power | compute | electronics |
    producible_locally: true       #   actuators | thermal | sensors | ...
    processes: [casting, machining]
    energy_to_produce_kwh_per_kg: 5.0    # electricity to make 1 kg, on-site

  - name: Computer chips           # a vitamin - can't be made locally
    mass_kg: 80
    category: compute              # 'compute' & 'electronics' are what `wall` toggles
    producible_locally: false
    processes: [semiconductor_fab]
    energy_to_produce_kwh_per_kg: 8000.0   # chips cost ~1000x more energy than metal

replication:
  seed_mass_kg: 5000               # weight of the first factory, landed from Earth
  local_build_rate_kg_per_day: 12  # how much it can build per day to start with
  vitamin_resupply_mass_kg: 50     # vitamins shipped each delivery...
  resupply_cadence_days: 30        # ...every 30 days (so ~1.67 kg/day on average)
  available_power_kw: 1000         # electricity available (a major separate cost)
  target_output_kg_per_day: 1000   # the goal you're timing the factory against
  duration_days: 14600             # how long to simulate (40 years here)
  dt_days: 1.0                     # simulation step (1 day)
```

Then run the three commands on your file. Realistic ranges for every number are in
[REFERENCES.md](REFERENCES.md).

---

## Using it from Python

```python
from closure_sim import load_factory, compute_closure, simulate, electronics_wall

factory = load_factory("scenarios/lunar_regolith_seed.yaml")

print(compute_closure(factory).closure_ratio)        # 0.97
print(simulate(factory).time_to_target_days)         # days to hit the target
print(electronics_wall(factory).after.time_to_target_days)  # ...if chips were local
```

## What's inside

```
src/closure_sim/
  models.py        the parts list & factory definition
  closure.py       the self-sufficiency calculation
  replication.py   the growth-over-time simulation
  analysis.py      the electronics-wall comparison
  scenarios.py     loads your YAML/JSON files
  cli.py           the three terminal commands
scenarios/         two ready-to-edit examples
tests/             19 tests checking the math behaves correctly
REFERENCES.md      where every number comes from, with sources
```

**Built to be extended.** Later modules (a detailed power-budget model, launch-cost
economics) plug in at clean seams: power is already a single isolated input, and the
seed mass / resupply figures are the natural cost hooks. This module deliberately
does *not* model chemistry, nanoscale manufacturing, or anything with a screen - it
does one thing: the closure-and-replication story, grounded and tested.
```
