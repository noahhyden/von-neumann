# Security policy

## Supported versions

This is a research project, not a deployed service. The `main` branch is the only
supported version; there are no released packages to patch.

## Reporting a vulnerability

If you find a security issue - for example in the build pipeline, a GitHub workflow, or
the static site - please report it privately rather than opening a public issue:

- Preferred: open a **GitHub Security Advisory** from the repository's **Security** tab.
- Alternatively: send a direct message to the repository owner, **@noahhyden**, on GitHub.

Please do not disclose the issue publicly until it has been addressed. Expect an
acknowledgement within a few days.

## Trust model

- The public site at <https://vn.noahhyden.com> is a **static build** with no backend,
  no accounts, and no server-side state. It runs entirely in the visitor's browser and
  collects nothing.
- The models are **pure, deterministic folds** in plain data. They make no network
  calls and touch no filesystem at runtime.
- The one credential in CI is a fine-grained token used solely by the pimas canary to
  file issues in the author's own `pimas` repository; it is unreachable from
  fork-triggered workflows.
- As with any repository, build and run only branches you trust; the code in a pull
  request is not vetted until it has been reviewed.
