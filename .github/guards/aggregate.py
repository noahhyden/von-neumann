#!/usr/bin/env python3
"""Fail the `PR guard` check once, after every guard step has reported its own outcome."""

from __future__ import annotations

import json
import os
import sys

# Guards with no `if:` condition: these never skip legitimately, so a skip means something upstream took them down.
MUST_RUN = {"typography", "depgraph", "cifilter", "depgraph_tests", "affected"}


def evaluate(steps: dict, job_status: str) -> tuple[bool, list[str]]:
    """Return (failed, report lines) for the collected step outcomes."""
    fail = job_status != "success"
    lines: list[str] = []
    if fail:
        lines.append(f"FAIL  <setup>  a step without continue-on-error failed (job status: {job_status})")
    for sid, step in steps.items():
        outcome = (step or {}).get("outcome")
        if outcome is None:
            continue
        bad = outcome == "failure" or (sid in MUST_RUN and outcome == "skipped")
        tag = "FAIL" if bad else ("SKIP" if outcome == "skipped" else "PASS")
        lines.append(f"{tag}  {sid} ({outcome})")
        if bad:
            fail = True
    return fail, lines


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    steps = json.loads(os.environ.get("STEPS", "{}"))
    fail, lines = evaluate(steps, os.environ.get("JOB_STATUS", "success"))
    print("Guard results:")
    for line in lines:
        print(f"  {line}")
        if line.startswith("FAIL"):
            print(f"::error::guard failed: {line[6:]}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## PR guard\n\n```\n" + "\n".join(lines) + "\n```\n")
    return int(fail)


def selftest() -> int:
    ok = {"typography": {"outcome": "success"}, "affected": {"outcome": "success"}}
    assert evaluate(ok, "success")[0] is False

    # One failing guard fails the check even though the job itself is still green.
    one_bad = dict(ok, depgraph={"outcome": "failure"})
    assert evaluate(one_bad, "success")[0] is True

    # A skipped MUST_RUN guard is a failure: it means setup took it down, not that it had nothing to do.
    skipped = dict(ok, cifilter={"outcome": "skipped"})
    assert evaluate(skipped, "success")[0] is True

    # A skipped conditional guard (frontend untouched) is fine.
    cond = dict(ok, frontend={"outcome": "skipped"})
    assert evaluate(cond, "success")[0] is False

    # A setup failure fails even when every reported guard passed.
    assert evaluate(ok, "failure")[0] is True
    print("aggregate selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
