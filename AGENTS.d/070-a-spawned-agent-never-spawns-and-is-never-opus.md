## A spawned agent never spawns, and is never Opus

Delegation is one level deep: an orchestrator may spawn, a spawned agent may not, and every spawn passes `model` of `sonnet` or `haiku` explicitly - use `slice-worker`, which has no `Agent` tool, because a prompt instruction not to delegate does not hold.
