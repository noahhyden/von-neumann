"""``--seed-slice`` / ``--merge`` bit-identity: shard + merge == single-machine full run.

Item 2 from #33's alternative-levers list. The seed ensemble is embarrassingly parallel,
so a heavy sweep can be split across K machines and merged back to one JSON. The bit-identity
guarantee is what makes this useful: a paper's committed number is the same whether we ran
the sweep on one box or K.

Two tests:

- **Unit** (``test_merge_interleaves_shards_deterministically``): construct synthetic per-seed
  rows for a tiny finite_size_periodic-shaped config, slice them exactly the way the CLI
  does, run the merger, and assert the resulting ``_tax_block`` output equals what a
  single-machine ``_tax_block`` would produce over the un-sliced rows. Fast (no simulation).
- **Interleave order** (``test_shard_positions_recover_original_seed_order``): verify the
  merger's position math - shard ``i % K`` at row ``i // K`` reconstructs position ``i`` in
  the pre-slice list - by threading a distinct "sentinel" per position through the shards
  and checking the merged sequence is 0, 1, 2, ...

The end-to-end CLI round-trip (``python -m experiments.measure --seed-slice 0/K ... && ...
--merge <name>`` produces a JSON byte-identical to a full-machine run) is verified by hand
against every committed ``finite_size_periodic.json`` when the module is changed - it takes
minutes at real N and is unsuitable for CI - but the fixture-check-out is unchanged in the
merged file's git diff.
"""

from __future__ import annotations

import json

from experiments.measure import (
    _apply_slice,
    _merge_finite_size_periodic,
    _tax_block,
    pct_delta,
)


def _fake_record(*, seed: int, wasted: int, arrivals: int, t100: float) -> dict:
    """A minimal record() shape - only the fields _tax_block reads."""
    return {
        "t100": t100,
        "total_launched": arrivals,
        "total_arrivals": arrivals,
        "wasted_arrivals": wasted,
        "wasted_travel_pc": wasted * 1.0,
        "settle_energy_c2": arrivals * 0.5,
        "wasted_energy_c2": wasted * 0.5,
        # Anchor a unique value in each row so the interleave test can prove position identity.
        "_seed": seed,
    }


def _fake_paired_rows(n_stars: int, seeds: list[int]) -> list[tuple[dict, dict]]:
    """Deterministic (base, treat) rows for a synthetic finite_size block."""
    rows: list[tuple[dict, dict]] = []
    for s in seeds:
        # Make the treatment noticeably heavier than the base so pct_delta is non-trivial.
        b = _fake_record(seed=s, wasted=(s % 10) + 1, arrivals=50 + s % 7, t100=1000.0 + s)
        t = _fake_record(seed=s, wasted=(s % 10) + 5, arrivals=50 + s % 7, t100=1200.0 + s)
        rows.append((b, t))
    return rows


class TestSeedSlice:
    """--seed-slice / --merge give byte-identical results to a single-machine full run."""

    def test_apply_slice_partitions_evenly_when_k_divides(self) -> None:
        seeds = list(range(16))
        s0 = _apply_slice.__wrapped__(seeds) if hasattr(_apply_slice, "__wrapped__") else None
        # Not decorated - just call with monkey-patched module state.
        from experiments import measure

        measure._SEED_SLICE = (0, 4)
        try:
            assert _apply_slice(seeds) == [0, 4, 8, 12]
            measure._SEED_SLICE = (1, 4)
            assert _apply_slice(seeds) == [1, 5, 9, 13]
            measure._SEED_SLICE = (2, 4)
            assert _apply_slice(seeds) == [2, 6, 10, 14]
            measure._SEED_SLICE = (3, 4)
            assert _apply_slice(seeds) == [3, 7, 11, 15]
        finally:
            measure._SEED_SLICE = None
        # A None slice returns the input unchanged (single-machine run).
        assert _apply_slice(seeds) == seeds

    def test_apply_slice_handles_uneven_partitions(self) -> None:
        """K > len(seeds) is legal; some shards get empty slices, others get one seed each."""
        from experiments import measure

        seeds = [10, 20, 30, 40, 50, 60]  # 6 seeds
        # K=4 -> shards get [2, 2, 1, 1] seeds
        measure._SEED_SLICE = (0, 4)
        try:
            assert _apply_slice(seeds) == [10, 50]
            measure._SEED_SLICE = (1, 4)
            assert _apply_slice(seeds) == [20, 60]
            measure._SEED_SLICE = (2, 4)
            assert _apply_slice(seeds) == [30]
            measure._SEED_SLICE = (3, 4)
            assert _apply_slice(seeds) == [40]
        finally:
            measure._SEED_SLICE = None

    def test_merge_reproduces_single_machine_tax_block(self) -> None:
        """The heart of the promise: shards + merger reproduce _tax_block(full_rows) exactly."""
        n_seeds = 12
        seeds = list(range(n_seeds))
        # Full run: _tax_block over ALL rows
        full_rows = _fake_paired_rows(n_stars=300, seeds=seeds)
        full_block = _tax_block(full_rows)

        # Sharded: run 4 slices, then interleave via the merger's position math
        k = 4
        shard_rows_by_idx: dict[int, list[tuple[dict, dict]]] = {}
        for shard_idx in range(k):
            sliced_seeds = [s for i, s in enumerate(seeds) if i % k == shard_idx]
            shard_rows_by_idx[shard_idx] = _fake_paired_rows(n_stars=300, seeds=sliced_seeds)

        # Rebuild what the merger sees in each shard's JSON: a _tax_block output with per_seed.
        # We only need per_seed for the merger to reconstruct rows.
        shards_json = []
        for shard_idx in range(k):
            block = _tax_block(shard_rows_by_idx[shard_idx])
            shards_json.append({
                "_shard": {"index": shard_idx, "count": k},
                "data": {"300": block},
            })

        # Fake config as the JSON would look.
        config = {"n_and_seeds": [[300, n_seeds]]}
        merged = _merge_finite_size_periodic(shards_json, config)

        # The merged block MUST equal the single-machine block byte-for-byte after JSON
        # round-trip (order-independent per key).
        assert json.dumps(merged["data"]["300"], sort_keys=True) == json.dumps(full_block, sort_keys=True)

    def test_shard_positions_recover_original_seed_order(self) -> None:
        """Position i in the merged list comes from shard (i % K) at row (i // K)."""
        n_seeds = 12
        seeds = list(range(n_seeds))
        k = 3
        # Tag each per_seed entry with a sentinel identifying its ORIGINAL seed value.
        shards_json = []
        for shard_idx in range(k):
            sliced = [s for i, s in enumerate(seeds) if i % k == shard_idx]
            per_seed = [{"base": {"_seed": s, **_fake_record(seed=s, wasted=1, arrivals=1, t100=1.0)},
                         "treat": {"_seed": s, **_fake_record(seed=s, wasted=2, arrivals=1, t100=2.0)}}
                        for s in sliced]
            shards_json.append({
                "_shard": {"index": shard_idx, "count": k},
                "data": {"300": {"per_seed": per_seed}},
            })
        config = {"n_and_seeds": [[300, n_seeds]]}
        merged = _merge_finite_size_periodic(shards_json, config)
        got_seeds = [e["base"]["_seed"] for e in merged["data"]["300"]["per_seed"]]
        assert got_seeds == seeds

    def test_merger_rejects_incomplete_shard_set(self) -> None:
        """If a shard is missing, merger MUST refuse to write a wrong result."""
        import pytest

        # Two shards claiming to be part of a 3-shard split, missing shard 2.
        shards_json = [
            {"_shard": {"index": 0, "count": 3}, "data": {"300": {"per_seed": [{"base": _fake_record(seed=0, wasted=1, arrivals=1, t100=1.0),
                                                                                "treat": _fake_record(seed=0, wasted=2, arrivals=1, t100=2.0)}]}}},
            {"_shard": {"index": 1, "count": 3}, "data": {"300": {"per_seed": [{"base": _fake_record(seed=1, wasted=1, arrivals=1, t100=1.0),
                                                                                "treat": _fake_record(seed=1, wasted=2, arrivals=1, t100=2.0)}]}}},
        ]
        # (There is no top-level check in _merge_finite_size_periodic for shard completeness;
        # that check lives in _do_merge. Here we prove the merger raises when it tries to read
        # a row from a shard that doesn't exist.)
        config = {"n_and_seeds": [[300, 3]]}  # asks for 3 seeds but only 2 shards
        with pytest.raises((KeyError, IndexError, ValueError)):
            _merge_finite_size_periodic(shards_json, config)
