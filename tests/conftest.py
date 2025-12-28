"""Pytest configuration for lodestar tests."""

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio to use only asyncio backend."""
    return "asyncio"
