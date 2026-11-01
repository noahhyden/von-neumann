# von-neumann dev-suite: a thin root task runner over the monorepo (see README.md).

# The module list has one source of truth: scripts/depgraph.py (plus the two tooling packages).
PY_MODULES := $(shell python3 scripts/depgraph.py --json | python3 -c \
	"import json,sys; print(*json.load(sys.stdin)['modules'], 'scripts', 'runner')")
# Shell snippet: cd into module $$m, wherever it lives.
MODCD = cd "$$([ -d modules/$$m ] && echo modules/$$m || echo $$m)"

M ?=
WORKERS ?=
NAME ?=

.DEFAULT_GOAL := help
.PHONY: help test test-py test-frontend frontend run runs ps papers list affected lint-rules agents

help:
	@echo "von-neumann dev-suite"
	@echo ""
	@echo "  make test              run all module tests (python + frontend)"
	@echo "  make test-py           run all python module tests"
	@echo "  make test M=<module>   run one module's tests (e.g. M=swarm)"
	@echo "  make affected M=<module>   run tests for every module a change to M reaches"
	@echo "  make test-frontend     run frontend Layer A + Layer B (pimas contract)"
	@echo "  make frontend          live-rebuild the frontend (npm run serve)"
	@echo "  make run SPEC=<path/to/run.yaml>     run one simulation from its spec"
	@echo "  make runs              list every committed run spec"
	@echo "  make ps                show live runs and their progress"
	@echo "  make papers            generate + typography-check the papers"
	@echo "  make lint-rules        one-line comments + AGENTS.d rule cap"
	@echo "  make agents            regenerate every AGENTS.md from its AGENTS.d/"
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
	@m=$(M); $(MODCD) && uv run pytest -q
endif

test-py:
	@for m in $(PY_MODULES); do \
		echo ">> tests: $$m"; \
		( $(MODCD) && uv run pytest -q ) || exit $$?; \
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
		( $(MODCD) && uv run --extra dev pytest -q ) || exit $$?; \
	done
endif

test-frontend:
	@echo ">> tests: frontend (Layer A + Layer B)"
	@cd frontend && npm test && npm run test:contract

frontend:
	@cd frontend && npm run serve

# One simulation run, one committed spec. Everything the run needs (worker cap, -O,
# backend selection) lives in the yaml, so there is nothing to remember and nothing to export.
run:
	@test -n "$(SPEC)" || { echo "usage: make run SPEC=<path/to/run.yaml>   (see: make runs)"; exit 2; }
	@cd runner && uv run vn-run ../$(SPEC)

runs:
	@cd runner && uv run vn-run ls

ps:
	@cd runner && uv run vn-run ps

papers:
	@cd papers && npm run check

# Guards: comments are one line, an AGENTS.d rule is one line of 255.
lint-rules:
	@python3 .github/scripts/check_one_line_comments.py
	@python3 .github/scripts/check_agents_rule_length.py

agents:
	@python3 .github/scripts/gen_agents_md.py --write
