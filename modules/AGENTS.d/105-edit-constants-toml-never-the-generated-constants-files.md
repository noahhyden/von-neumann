## Edit constants.toml, never the generated constants files

`core/src/vn_core/constants.toml` is the single source; `vn_core/constants.py` and `frontend/src/constants.ts` are both generated from it by `make constants`, so a constant cannot drift across the language boundary. Hand-edits are overwritten.
