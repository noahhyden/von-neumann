## Run a committed yaml spec, never hand-typed parameters

A run is a committed yaml spec under `<module>/runs/`: execute `make run SPEC=<path>`, list with `make runs`. The schema in runner/src/vn_runner/spec.py forbids env vars so a stale export cannot change a result; never hand-type parameters at a shell.
