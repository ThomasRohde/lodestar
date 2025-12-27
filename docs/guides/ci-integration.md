# CI Integration Guide

Integrate Lodestar with your CI/CD pipeline for automated health checks and deployment workflows.

## GitHub Actions Workflows

Lodestar comes with two GitHub Actions workflows:

### CI Workflow (`.github/workflows/ci.yml`)

Runs on every push and pull request:

- **Linting**: Runs `ruff check` and `ruff format --check`
- **Testing**: Runs pytest on Python 3.12 and 3.13
- **Docs Build**: Builds documentation with `mkdocs build --strict`
- **Lodestar Health**: Runs `lodestar doctor` to validate task spec

```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install 3.12
      - run: uv sync --extra dev
      - run: uv run ruff check src tests
      - run: uv run ruff format --check src tests

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install 3.12
      - run: uv sync --extra dev
      - run: uv run pytest

  lodestar-health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install 3.12
      - run: uv sync
      - run: uv run lodestar doctor
```

### Docs Deployment (`.github/workflows/docs.yml`)

Deploys documentation to GitHub Pages when docs change:

```yaml
name: Deploy Docs

on:
  push:
    branches: [main, master]
    paths:
      - 'docs/**'
      - 'mkdocs.yml'

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install 3.12
      - run: uv sync --extra docs
      - run: uv run mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./site

  deploy:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/deploy-pages@v4
```

## Health Checks in CI

The `lodestar-health` job validates your task specification:

```yaml
- name: Run lodestar doctor
  run: uv run lodestar doctor
```

This catches:

- Invalid YAML syntax
- Missing task dependencies
- Dependency cycles
- Orphaned tasks

### Strict Mode

For stricter validation, use `--json` and parse the output:

```yaml
- name: Validate task spec
  run: |
    output=$(uv run lodestar doctor --json)
    if ! echo "$output" | jq -e '.ok == true'; then
      echo "Lodestar health check failed!"
      echo "$output" | jq
      exit 1
    fi
```

## Validating PRs

Add Lodestar checks to branch protection:

1. Go to repository Settings > Branches
2. Add branch protection rule for `main`
3. Enable "Require status checks to pass"
4. Select: `lint`, `test`, `lodestar-health`

## Task Metrics in CI

Export task metrics for dashboards:

```yaml
- name: Export metrics
  run: |
    uv run lodestar status --json > metrics.json
    echo "Task counts:"
    jq '.data.tasks' metrics.json
```

## Preventing Broken Specs

Add a pre-commit hook to validate locally:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: lodestar-doctor
        name: Lodestar health check
        entry: uv run lodestar doctor
        language: system
        pass_filenames: false
        files: ^\.lodestar/spec\.yaml$
```

## Automated Verification

For automated testing workflows, verify tasks programmatically:

```python
import subprocess
import json

def run_lodestar(cmd: list[str]) -> dict:
    """Run a lodestar command and return JSON output."""
    result = subprocess.run(
        ["uv", "run", "lodestar"] + cmd + ["--json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

def verify_if_tests_pass(task_id: str) -> bool:
    """Run tests for a task and verify if they pass."""
    # Run tests
    test_result = subprocess.run(
        ["uv", "run", "pytest", f"tests/test_{task_id.lower()}.py"],
        capture_output=True
    )

    if test_result.returncode == 0:
        # Mark task verified
        run_lodestar(["task", "verify", task_id])
        return True
    return False
```

## Setting Up GitHub Pages

To deploy documentation:

1. Go to repository Settings > Pages
2. Set Source to "GitHub Actions"
3. Push to main/master with docs changes
4. Docs deploy automatically

Your docs will be available at:
`https://<org>.github.io/<repo>/`
