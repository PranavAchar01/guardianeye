# Contributing to GuardianEye

Thanks for your interest in improving GuardianEye. This guide covers local
setup, the checks we run, and how to propose changes.

## Development setup

GuardianEye uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
```

This creates a virtual environment and installs both runtime and development
dependencies.

## Running the checks

Before opening a pull request, make sure both of these pass:

```bash
uv run ruff check .   # lint and import order
uv run pytest -q      # unit tests
```

The same checks run in CI on every push and pull request. You can also install
the pre-commit hooks so they run automatically:

```bash
uv run pre-commit install
```

## Making changes

1. Create a branch off `main`.
2. Keep each commit focused on a single concern.
3. Add or update tests for any behavior change.
4. Run ruff and pytest locally.
5. Open a pull request describing what changed and why.

## Style

- Line length is 100 characters (enforced by ruff).
- Public functions and classes carry type hints and short docstrings.
- Prose and comments avoid em dashes; use commas, colons, or separate sentences.

## Scope of the project

GuardianEye is a safety-monitoring prototype. Detection is anonymous by design:
no faces are identified or stored. Please keep contributions aligned with that
privacy stance.
