## Derive module counts, never hardcode them, and run every selftest in CI

Derive counts from depgraph.Graph(REPO).modules, never a literal: a hardcoded count rotted silently because CI never ran --selftest. A selftest nothing runs is not a check; put it on the required CI path.
