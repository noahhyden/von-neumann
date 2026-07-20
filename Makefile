# von-neumann dev-suite (trial)
#
# A thin root task runner over the monorepo. It does NOT fuse modules or add a server -
# each module stays independently runnable (CLAUDE.md 4); this just gives one place to
# run them together. Python modules use `uv run pytest`; `frontend` and `papers` are the
# two JS packages. Sweeps take a memory-aware worker cap so they stop OOMing.
#
# Common use:
#   make            # help
#   make test       # every module's tests (python + frontend)
#   make test-py    # just the python modules
#   make test M=swarm   # one module
#   make frontend   # live-rebuild the frontend (npm run serve)
#   make sweep NAME=branching_scale WORKERS=2   # one swarm experiment, worker-capped
#   make papers     # generate + typography-check the papers

# Python modules = top-level dirs with a pyproject.toml but no package.json (those are JS).
PY_MODULES := $(shell for d in */; do d=$${d%/}; \
	[ -f "$$d/pyproject.toml" ] && [ ! -f "$$d/package.json" ] && echo $$d; done)

M ?=
WORKERS ?=
NAME ?=

.DEFAULT_GOAL := help
.PHONY: help test test-py test-frontend frontend sweep papers list affected

help:
	@echo "von-neumann dev-suite"
	@echo ""
	@echo "  make test              run all module tests (python + frontend)"
	@echo "  make test-py           run all python module tests"
	@echo "  make test M=<module>   run one module's tests (e.g. M=swarm)"
	@echo "  make affected M=<module>   run tests for every module a change to M reaches"
	@echo "  make test-frontend     run frontend Layer A + Layer B (pimas contract)"
	@echo "  make frontend          live-rebuild the frontend (npm run serve)"
	@echo "  make sweep NAME=<name> [WORKERS=N]   run one swarm experiment"
	@echo "  make papers            generate + typography-check the papers"
	@echo "  make list              list the discovered python modules"
	@echo ""
	@echo "python modules: $(PY_MODULES)"

list:
	@echo $(PY_MODULES)

# `make test` with M= runs one module; without M= runs everything.
test:
ifeq ($(strip $(M)),)
	@$(MAKE) --no-print-directory test-py
	@$(MAKE) --no-print-directory test-frontend
else
	@echo ">> tests: $(M)"
	@cd $(M) && uv run pytest -q
endif

test-py:
	@for m in $(PY_MODULES); do \
		echo ">> tests: $$m"; \
		( cd $$m && uv run pytest -q ) || exit $$?; \
	done

# `make affected M=<module>` runs the tests of every module a change to M reaches
# (M plus its transitive importers), via scripts/depgraph.py, and prints the stale
# results/papers as a heads-up. The reachable set is computed, not remembered - the
# repo-scale replacement for "re-run everything" or "re-run just what I touched".
affected:
ifeq ($(strip $(M)),)
	@echo "usage: make affected M=<module>   (module dir, package name, or file path)"; exit 2
else
	@python3 scripts/depgraph.py --changed $(M)
	@echo ""
	@for m in $$(python3 scripts/depgraph.py --changed $(M) --list); do \
		echo ">> tests: $$m"; \
		( cd $$m && uv run --extra dev pytest -q ) || exit $$?; \
	done
endif

test-frontend:
	@echo ">> tests: frontend (Layer A + Layer B)"
	@cd frontend && npm test && npm run test:contract

frontend:
	@cd frontend && npm run serve

# Worker cap keeps big-N sweeps (e.g. branching_scale at 200k) inside RAM. Blank WORKERS
# uses all cores. Determinism is unaffected: executor.map preserves order at any count.
# `-O` strips debug invariants (~2-3x wall-clock win at bit-identical results, see
# docs/HARDWARE.md "Assertion mode" and swarm/experiments/_run.py). Sweep is by
# definition an ensemble run; invariants are on for tests + dev iteration only.
sweep:
	@test -n "$(NAME)" || { echo "usage: make sweep NAME=<experiment> [WORKERS=N]"; exit 2; }
	@echo ">> sweep: $(NAME)$(if $(WORKERS), (SWARM_WORKERS=$(WORKERS)))"
	@cd swarm/experiments && $(if $(WORKERS),SWARM_WORKERS=$(WORKERS) )uv run python -O measure.py $(NAME)

papers:
	@cd papers && npm run check
