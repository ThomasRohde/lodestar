"""Integration tests for MCP HTTP transport.

Tests that the HTTP server starts correctly and handles basic requests.
Uses raw HTTP requests rather than the MCP SDK client to avoid
complex async context manager issues on Windows.
"""

import json
import subprocess
import sys
import time

import pytest

from lodestar.models.spec import Project, Spec, Task, TaskStatus
from lodestar.spec.loader import save_spec

# Skip all tests if MCP dependencies are not installed
pytest.importorskip("mcp")
httpx = pytest.importorskip("httpx")


@pytest.fixture
def test_repo(tmp_path):
    """Create a test repository with sample data for integration tests."""
    lodestar_dir = tmp_path / ".lodestar"
    lodestar_dir.mkdir()

    spec = Spec(
        project=Project(name="http-integration-test"),
        tasks={
            "HTTP-T01": Task(
                id="HTTP-T01",
                title="First HTTP test task",
                description="Ready task for concurrent testing",
                status=TaskStatus.READY,
                priority=1,
                labels=["test"],
            ),
            "HTTP-T02": Task(
                id="HTTP-T02",
                title="Second HTTP test task",
                description="Another ready task",
                status=TaskStatus.READY,
                priority=2,
                labels=["test"],
            ),
        },
    )

    save_spec(spec, tmp_path)
    return tmp_path


@pytest.fixture
def http_server(test_repo):
    """Start the MCP HTTP server and yield the URL."""
    port = 18765

    print(f"\n[fixture] Starting server on port {port}...")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lodestar.cli.app",
            "mcp",
            "serve",
            "--transport",
            "streamable-http",
            "--port",
            str(port),
            "--repo",
            str(test_repo),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url = f"http://127.0.0.1:{port}/mcp"

    # Wait for server to be ready
    print("[fixture] Waiting for server startup...")
    time.sleep(3)

    if proc.poll() is not None:
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(f"Server exited prematurely: {stderr}")

    print(f"[fixture] Server ready at {url}")
    yield url

    print("[fixture] Stopping server...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    print("[fixture] Server stopped")


def make_sse_request(url: str, payload: dict, timeout: float = 10.0) -> dict | None:
    """Make an HTTP request and parse the SSE response."""
    with httpx.stream(
        "POST",
        url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        timeout=timeout,
    ) as response:
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}"}

        # Read SSE events
        for line in response.iter_lines():
            if line.startswith("data: "):
                return json.loads(line[6:])

    return None


class TestHTTPServerBasics:
    """Test HTTP server startup and basic responses."""

    def test_server_accepts_initialize(self, http_server):
        """Test that the HTTP server accepts MCP initialize requests.

        This test verifies:
        1. The server starts correctly with streamable-http transport
        2. The server accepts MCP protocol initialize requests
        3. The server returns proper lodestar server info
        """
        print("\n[test] Sending initialize request...")

        result = make_sse_request(
            http_server,
            {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )

        print(f"[test] Got response: {result}")

        assert result is not None, "No response received from server"
        assert "result" in result, f"Expected 'result' in response, got: {result}"
        assert result["result"]["serverInfo"]["name"] == "lodestar"
        assert result["result"]["protocolVersion"] == "2024-11-05"
        print("[test] HTTP server responded correctly to initialize request")
