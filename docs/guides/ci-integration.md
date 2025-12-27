# CI Integration Guide

Integrate Lodestar with your CI/CD pipeline for automated health checks and deployment workflows.

## Health Checks in CI

Add Lodestar health checks to your CI pipeline:

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  lodestar-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run Lodestar doctor
        run: uv run lodestar doctor --json
```

## Validating Task Spec

Ensure the task spec is valid on every PR:

```yaml
- name: Validate task spec
  run: |
    uv run lodestar doctor --json | jq -e '.ok == true'
```

## Checking for Cycles

Lodestar automatically checks for dependency cycles:

```yaml
- name: Check dependencies
  run: |
    output=$(uv run lodestar doctor --json)
    if echo "$output" | jq -e '.data.checks[] | select(.name == "dependencies" and .status == "error")'; then
      echo "Dependency cycle detected!"
      exit 1
    fi
```

## Task Metrics

Export task metrics for dashboards:

```yaml
- name: Export metrics
  run: |
    uv run lodestar status --json > metrics.json
    # Upload to your metrics system
```

## Automated Verification

For automated testing, you can verify tasks programmatically:

```python
import subprocess
import json

def verify_task(task_id: str) -> bool:
    """Run tests and verify a task if they pass."""
    # Run your test suite
    result = subprocess.run(["pytest", f"tests/test_{task_id}.py"])

    if result.returncode == 0:
        # Mark task verified
        subprocess.run(["lodestar", "task", "verify", task_id])
        return True
    return False
```

## Branch Protection

Consider requiring Lodestar health checks for merges:

1. Go to repository Settings > Branches
2. Add branch protection rule for `main`
3. Require status checks: `lodestar-check`
