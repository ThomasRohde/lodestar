# Lodestar Build, Test & Publish Automation PRD

## Overview

Lodestar (packaged as `lodestar-cli`) is a Python CLI tool that enables multi-agent coordination in Git repositories. This PRD outlines the requirements for automating the build, testing, and publishing processes of Lodestar using GitHub Actions. The objective is to ensure every change is validated for quality and that releasing new versions to PyPI is streamlined and secure. All automation is designed around **Python 3.13** as the target runtime.

## Build

Building Lodestar should yield standard Python distribution packages and focus on the intended Python version.

- **Python 3.13 Only**: The project supports and is tested with **Python 3.13** exclusively. The CI build environment will run on Python 3.13, and the package metadata (e.g., `python_requires`) should enforce Python >= 3.13 as the minimum required version.
- **Wheel and Source Distribution**: The build must produce both a compiled wheel (*.whl*) and a source distribution (*.tar.gz*). This ensures users can install the package either via pre-built wheel or from source. Both artifacts should be generated for each release.
- **Standard Build Process**: Utilize a PEP 517–compliant build backend (as configured in `pyproject.toml`, e.g. **Hatchling**) to create the distributions. Running `pip install build` followed by `python -m build` should output the wheel and sdist into a `dist/` directory. The build process should be consistent locally and in CI.

## Test and Code Quality

To maintain code quality, the project will include automated testing and static analysis. The following tools and checks will be integrated:

- **Pytest for Tests**: All test cases must run and pass using **pytest**. The test suite (e.g., the `tests/` directory) should execute on Python 3.13 with no failures. Test execution can be combined with coverage measurement to assess code coverage.
- **Flake8 Linting**: Code style and quality will be checked with **Flake8**. The codebase must adhere to PEP8 and pass all Flake8 checks (no errors or warnings), ensuring a consistent style and catching common issues early.
- **MyPy Type Checking**: Static type checking is enforced with **MyPy**. All code (and relevant dependencies) should be type-annotated such that `mypy` reports no type errors. This guarantees type safety and helps prevent bugs related to mismatched types.
- **Coverage Reporting**: Test coverage will be measured using the **coverage** tool (e.g., via `coverage.py` or the `pytest-cov` plugin). After running tests, a coverage report should be generated. The project should aim for a high coverage percentage (e.g., 80% or higher); a minimum coverage threshold can be set to fail the build if coverage is too low, ensuring critical code paths are tested.

## Continuous Integration Workflow (ci.yml)

A GitHub Actions workflow will run on each commit to automatically build and test the project. The `ci.yml` workflow ensures that no code is merged without passing all quality gates.

- **Trigger Conditions**: The CI workflow triggers on **every push** (to any branch) and on **every pull request**. This guarantees that both direct commits and incoming PRs are validated.
- **Environment Setup**: The workflow runs on an Ubuntu runner (e.g., `ubuntu-latest`) with **Python 3.13**. Use `actions/setup-python` to install Python 3.13 in the job environment. (No other Python versions are needed in the matrix, since 3.13 is the target.)
- **Dependency Installation**: Install all necessary dependencies before running checks. This includes the project’s runtime requirements as well as dev/test tools (Pytest, Flake8, MyPy, coverage). The workflow can install these via pip, using `pyproject.toml` (project and optional dev dependencies) or a dedicated requirements file.
- **Lint & Type Check Steps**: The workflow should have separate steps to run **Flake8** and **MyPy**. These will lint the code and perform type checking, respectively. If either step finds issues (lint errors or type errors), it should cause the workflow to fail fast.
- **Testing & Coverage**: A step will run the test suite with **pytest** (on Python 3.13). Tests should be run with coverage enabled (for example, using `coverage run -m pytest` or `pytest --cov`). This will execute all tests and collect code coverage metrics.
- **Coverage Results**: After tests, the workflow should produce a coverage report. This could be output to the console (showing the percentage) or saved as an artifact (e.g., an XML/HTML report for inspection). While not mandatory, enforcing a minimum coverage (via a coverage plugin or script) is recommended to maintain quality.
- **Outcome**: The CI workflow must pass all steps for a given commit to be considered successful. A failure in linting, type checking, testing, or coverage requirements will mark the build as failed. Only when all checks pass does the CI status turn green, indicating the code meets the quality standards and can be merged.

## Release Workflow (publish.yml)

Publishing new releases will be handled by an automated GitHub Actions workflow. The `publish.yml` workflow package and upload the library to PyPI, leveraging secure OIDC authentication instead of static API tokens.

- **Release Trigger**: The publish workflow triggers when a new Git tag is pushed that matches the version pattern `v*.*.*` (for example, `v1.0.0`). Pushing a tag like this indicates a release, and the workflow will run to deploy the corresponding version.
- **Build on Tag**: The release job will run on an Ubuntu runner with Python 3.13. It will check out the repository at the tagged commit and build the project artifacts (wheel and sdist) for release. This uses the same build process as in CI, ensuring the distributables (`*.whl` and `*.tar.gz`) are created for the tagged version.
- **PyPI Publishing via OIDC**: The workflow will authenticate to PyPI using PyPI’s *Trusted Publishers* feature (OpenID Connect), eliminating the need for a stored API token. Specifically:  
    - Include **OIDC permissions** in the workflow job: in the `publish.yml`, set `permissions: id-token: write` (and `contents: read`) for the job. This allows GitHub Actions to generate a short-lived OIDC identity token.  
    - Use the repository’s **`pypi` environment** (if configured) in the workflow. The job can specify `environment: pypi` to match what’s set up in PyPI’s trusted publisher settings (owner: `ThomasRohde`, repo: `lodestar`, workflow: `publish.yml`, environment: `pypi`). This ties the workflow run to the trusted context approved on PyPI.  
    - Invoke the PyPI publish action without any hard-coded credentials. For example, use **pypa/gh-action-pypi-publish** (latest version) in a step to upload to PyPI. This action will detect the OIDC token and request a temporary upload API key from PyPI. PyPI verifies the token (ensuring the workflow run is from the authorized repo/workflow) and returns a short-lived credential, which the action uses to upload the wheel and sdist.  
    - The first time this workflow runs, the PyPI project’s trusted publisher status will move from “pending” to active upon successful verification. Subsequent releases will use the established trust with no human intervention.
- **Post-publish**: If the upload to PyPI succeeds, the new version of the package **lodestar-cli** becomes available on PyPI for users (`pip install lodestar-cli` will fetch the new release). The workflow can also optionally create a corresponding GitHub Release or tag annotation for record-keeping (not strictly required for PyPI publishing). The key outcome is that the package is published to PyPI automatically upon tagging, without any manual steps.

## Secrets Management

- **No Secrets Required**: No sensitive secrets (like PyPI API tokens) are needed in the repository for this automation. The PyPI publishing process uses OpenID Connect to obtain credentials at runtime, so **no `PYPI_API_TOKEN`** is stored in GitHub. This improves security by removing long-lived credentials. All other CI steps (tests, linting, etc.) also run without requiring secret keys or tokens.

## Package Metadata

Proper package metadata must be defined in the `pyproject.toml` to ensure successful building and publishing to PyPI:

- **Name**: The distribution name is **`lodestar-cli`**. This is the name under which the package will be published on PyPI. (The CLI tool itself will be invoked as `lodestar` via the console entry point.)
- **Version**: The project version should follow semantic versioning (e.g., 0.1.0, 1.0.0). Each release tag pushed (vX.Y.Z) must correspond exactly to the version in `pyproject.toml` for that commit. Updating this version number and tagging the commit are what trigger a new release.
- **Description**: Include a short description of the project. This will appear on PyPI. For example, “Agent-native repo orchestration for multi-agent coordination in Git repositories.” The description should give users a clear, concise summary of Lodestar’s purpose.
- **License**: Specify the project’s license (e.g., MIT License). The license type should be included in the package metadata and a corresponding Trove classifier (e.g., `License :: OSI Approved :: MIT License`). A LICENSE file should be present in the repository as well.
- **Classifiers**: Provide appropriate PyPI classifiers to categorize the project. For example:  
    - *Development Status* :: 3 - Alpha (or appropriate status)  
    - *Intended Audience* :: Developers  
    - *Environment* :: Console  
    - *License* :: OSI Approved :: MIT License  
    - *Programming Language* :: Python :: 3  
    - *Programming Language* :: Python :: 3.13  
    - *Topic* :: Software Development :: Libraries :: Python Modules  
    - (etc., as applicable to Lodestar)
- **Dependencies**: List all required runtime dependencies in the metadata. When users install `lodestar-cli`, these dependencies should be pulled in automatically. (For example, Lodestar likely depends on Typer, Rich, Pydantic, PyYAML, SQLAlchemy, etc. with specific version ranges. These belong in the `project.dependencies` section of pyproject.toml.)
- **Entry Point**: Define a console script entry point for the CLI. In the pyproject, under `[project.scripts]`, there should be an entry like `"lodestar": "lodestar.cli:app"`. This maps the command `lodestar` to the Python function that runs the CLI (using Typer’s `app`). As a result, after installation, users can simply run `lodestar` in the shell to use the tool.

## Acceptance Criteria

The implementation will be considered successful when the following are true:

- **CI Pipeline Enforcement**: On any push or pull request, the CI workflow runs automatically and all checks pass. If a linting error, type error, test failure, or insufficient coverage is detected, the workflow fails and prevents the merge. Only code that passes Flake8, MyPy, and all Pytest tests (with adequate coverage) can be merged into the main branch.
- **Automated Release**: Pushing a new version tag (e.g., `v1.0.0`) triggers the publish workflow and it completes successfully. The workflow logs should show that the package was built and uploaded to PyPI without errors.
- **PyPI Release Verification**: After the workflow runs, the new version of **lodestar-cli** is available on PyPI. The package metadata on PyPI (name, version, description, classifiers, etc.) matches the information from the repository’s `pyproject.toml`, and users are able to `pip install` the new release. This confirms the build and upload steps worked correctly.
- **No Manual Credentials**: No manual intervention or stored credentials were needed for the release. The PyPI Trusted Publisher configuration is confirmed to be working if the upload succeeds with OIDC. The repository contains no PyPI API token, and the security of the publishing process is maintained via GitHub OIDC authentication.
