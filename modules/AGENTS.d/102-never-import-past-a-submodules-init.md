## Never import past a submodule's __init__.py

Submodule boundaries are real: never reach past a submodule's __init__.py into its internals or import a private name from a sibling, because the clean-interface rule holds inside a module exactly as it does between modules.
