"""lodestar doctor command - Check repository health."""

from __future__ import annotations

from typing import Any

import typer

from lodestar.models.envelope import Envelope, NextAction
from lodestar.spec.dag import validate_dag
from lodestar.spec.loader import SpecNotFoundError, SpecValidationError, load_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path


def doctor_command(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Check repository health and diagnose issues.

    Validates spec.yaml, checks for dependency cycles, and verifies
    runtime database integrity.
    """
    if explain:
        _show_explain(json_output)
        return

    checks: list[dict[str, Any]] = []
    all_passed = True

    # Check 1: Repository initialized
    root = find_lodestar_root()
    if root is None:
        checks.append(
            {
                "name": "repository",
                "status": "fail",
                "message": "Not a Lodestar repository",
                "fix": "Run 'lodestar init' to initialize",
            }
        )
        all_passed = False
        _output_results(checks, all_passed, json_output)
        return

    checks.append(
        {
            "name": "repository",
            "status": "pass",
            "message": f"Repository found at {root}",
        }
    )

    # Check 2: Spec file exists and is valid
    try:
        spec = load_spec(root)
        checks.append(
            {
                "name": "spec.yaml",
                "status": "pass",
                "message": f"Valid spec with {len(spec.tasks)} tasks",
            }
        )
    except SpecNotFoundError:
        checks.append(
            {
                "name": "spec.yaml",
                "status": "fail",
                "message": "spec.yaml not found",
                "fix": "Run 'lodestar init' to create spec.yaml",
            }
        )
        all_passed = False
        _output_results(checks, all_passed, json_output)
        return
    except SpecValidationError as e:
        checks.append(
            {
                "name": "spec.yaml",
                "status": "fail",
                "message": f"Invalid spec: {e}",
                "fix": "Fix the YAML syntax or schema errors",
            }
        )
        all_passed = False
        _output_results(checks, all_passed, json_output)
        return

    # Check 3: DAG validation (no cycles, valid deps)
    dag_result = validate_dag(spec)
    if dag_result.valid:
        checks.append(
            {
                "name": "dependencies",
                "status": "pass",
                "message": "No cycles or missing dependencies",
            }
        )
    else:
        for error in dag_result.errors:
            checks.append(
                {
                    "name": "dependencies",
                    "status": "fail",
                    "message": error,
                    "fix": "Fix the dependency configuration in spec.yaml",
                }
            )
            all_passed = False

    # Add warnings for orphan tasks
    for warning in dag_result.warnings:
        checks.append(
            {
                "name": "dependencies",
                "status": "warn",
                "message": warning,
            }
        )

    # Check 4: Runtime database (if exists)
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        try:
            from lodestar.runtime.database import RuntimeDatabase

            db = RuntimeDatabase(runtime_path)
            stats = db.get_stats()
            checks.append(
                {
                    "name": "runtime.sqlite",
                    "status": "pass",
                    "message": f"Database OK ({stats['agents']} agents)",
                }
            )
        except Exception as e:
            checks.append(
                {
                    "name": "runtime.sqlite",
                    "status": "fail",
                    "message": f"Database error: {e}",
                    "fix": "Delete runtime.sqlite to regenerate",
                }
            )
            all_passed = False
    else:
        checks.append(
            {
                "name": "runtime.sqlite",
                "status": "info",
                "message": "Not created yet (will be created on first use)",
            }
        )

    # Check 5: .gitignore
    gitignore_path = root / ".lodestar" / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if "runtime.sqlite" in content:
            checks.append(
                {
                    "name": ".gitignore",
                    "status": "pass",
                    "message": "Runtime files are gitignored",
                }
            )
        else:
            checks.append(
                {
                    "name": ".gitignore",
                    "status": "warn",
                    "message": "runtime.sqlite not in .gitignore",
                    "fix": "Add 'runtime.sqlite' to .lodestar/.gitignore",
                }
            )
    else:
        checks.append(
            {
                "name": ".gitignore",
                "status": "warn",
                "message": ".gitignore missing in .lodestar",
                "fix": "Run 'lodestar init --force' to recreate",
            }
        )

    _output_results(checks, all_passed, json_output)


def _output_results(checks: list[dict[str, Any]], all_passed: bool, json_output: bool) -> None:
    """Output doctor results."""
    next_actions = []
    if not all_passed:
        next_actions.append(
            NextAction(
                intent="init",
                cmd="lodestar init",
                description="Reinitialize to fix issues",
            )
        )

    if json_output:
        print_json(
            Envelope.success(
                {"healthy": all_passed, "checks": checks},
                next_actions=next_actions,
            ).model_dump()
        )
        return

    # Rich output
    console.print()
    console.print("[bold]Health Check[/bold]")
    console.print()

    status_icons = {
        "pass": "[green]\u2713[/green]",
        "fail": "[red]\u2717[/red]",
        "warn": "[yellow]![/yellow]",
        "info": "[blue]i[/blue]",
    }

    for check in checks:
        icon = status_icons.get(check["status"], "?")
        console.print(f"  {icon} [bold]{check['name']}[/bold]: {check['message']}")
        if "fix" in check:
            console.print(f"      [muted]Fix: {check['fix']}[/muted]")

    console.print()
    if all_passed:
        console.print("[success]All checks passed![/success]")
    else:
        console.print("[error]Some checks failed. See above for fixes.[/error]")
    console.print()


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation = {
        "command": "lodestar doctor",
        "purpose": "Check repository health and diagnose issues.",
        "checks": [
            "Repository initialization",
            "spec.yaml validity",
            "Dependency DAG (cycles, missing refs)",
            "Runtime database integrity",
            ".gitignore configuration",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar doctor[/info]")
        console.print()
        console.print("Check repository health and diagnose issues.")
        console.print()
