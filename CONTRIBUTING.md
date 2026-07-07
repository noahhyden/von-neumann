# Contributing

Thanks for taking a look. This is a solo research project - a source-checked set of
physics models of self-replicating space manufacturing, maintained by one person and
published so it can be read and cited. A few things up front so expectations are clear.

## What is and isn't welcome

- **Issues flagging a factual or sourcing error are the most valuable thing you can
  send.** The whole project rests on one rule: every number traces to a citable source
  (see any module's `REFERENCES.md`). If you find a figure that does not match its
  cited source, a dead citation, or a physics or math mistake, please open an issue.
  That is a real contribution and it is appreciated.
- **Code contributions and pull requests are generally not accepted.** This is a
  single-author project under a deliberately restrictive license (see `LICENSE` and
  `LICENSE-DOCS`), which does not grant rights to publish derivative works. If you
  think a change is worth making, open an issue to discuss it first rather than sending
  a pull request.
- For questions and general discussion, use Discussions, not issues.

## The rules the project holds itself to

These are the invariants behind every change here. They are listed so you can see the
bar the work is held to, and so a flagged issue can point at the one that is broken:

- **No number is assumed.** Every mass, energy, rate, cost, efficiency, or threshold
  either traces to a citable source or is derived by explicit math from numbers that
  do, and is recorded in that module's `REFERENCES.md`. A number with no reference
  entry is a bug. Genuine gaps are marked `[GAP]` or `[ESTIMATE]`, never guessed.
- **Behavior is validated end to end**, not merely "it ran": assertions check real
  numbers and the edge regimes that matter.
- **The models are pure, seeded, deterministic folds**, with pimas only as the
  reactive skin. Randomness is seeded state threaded through the fold - never a wall
  clock, never `Math.random()`.
- **Typography:** no em-dash (U+2014) and no emoji, anywhere. Plain ASCII hyphens.
- **One module = one directory**, independently runnable and tested, and nesting no
  deeper than the question needs.

## Running the tests

Each Python module is self-contained:

    cd <module> && uv run --extra dev pytest -q

The whole suite (all modules plus the frontend's two test layers) runs from the repo
root with `./scripts/test-all.sh` - see the README's "Reproducing all results".
