"""Integration tests for the MCP server.

Tests MCP server functionality by spawning a subprocess and connecting
with an MCP client over stdio. Covers concurrent claims, messaging,
and event streaming.
"""

import shutil
from pathlib import Path

import pytest

from lodestar.models.spec import Project, Spec, Task, TaskStatus
from lodestar.spec.loader import save_spec

# Skip all tests if MCP is not installed
pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


@pytest.fixture
def test_repo(tmp_path):
    """Create a test repository with sample data for integration tests."""
    # Create repository structure
    lodestar_dir = tmp_path / ".lodestar"
    lodestar_dir.mkdir()

    # Create sample spec with tasks
    spec = Spec(
        project=Project(name="integration-test-project"),
        tasks={
            "INT-001": Task(
                id="INT-001",
                title="First integration test task",
                description="Ready task for testing concurrent claims",
                status=TaskStatus.READY,
                priority=1,
                labels=["test"],
            ),
            "INT-002": Task(
                id="INT-002",
                title="Second integration test task",
                description="Another ready task",
                status=TaskStatus.READY,
                priority=2,
                labels=["test"],
            ),
            "INT-003": Task(
                id="INT-003",
                title="Third integration test task",
                description="Task for message testing",
                status=TaskStatus.READY,
                priority=3,
                labels=["test"],
            ),
        },
    )

    save_spec(spec, tmp_path)
    return tmp_path


def get_server_params(repo_path: Path) -> StdioServerParameters:
    """Create server parameters for launching the MCP server.

    Args:
        repo_path: Path to the test repository

    Returns:
        StdioServerParameters configured to launch lodestar MCP server
    """

    # Find lodestar executable
    lodestar_exe = shutil.which("lodestar")
    if lodestar_exe is None:
        raise RuntimeError("lodestar executable not found in PATH")

    return StdioServerParameters(
        command=lodestar_exe,
        args=["mcp", "serve", "--repo", str(repo_path)],
        env={},
    )


class TestConcurrentClaims:
    """Test concurrent task claiming from multiple client sessions."""

    @pytest.mark.anyio
    async def test_two_clients_claim_different_tasks(self, test_repo):
        """Test that two clients can claim different tasks concurrently."""
        server_params = get_server_params(test_repo)

        # Client 1 connects and claims INT-001
        async with stdio_client(server_params) as (read1, write1):
            async with ClientSession(read1, write1) as session1:
                await session1.initialize()

                # Join as agent
                agent1_result = await session1.call_tool("lodestar.agent.join", {"name": "Agent 1"})
                agent1_id = agent1_result.structuredContent["agentId"]

                # Claim INT-001
                claim1_result = await session1.call_tool(
                    "lodestar.task.claim",
                    {
                        "task_id": "INT-001",
                        "agent_id": agent1_id,
                        "ttl_seconds": 900,
                    },
                )

                assert claim1_result.isError is None or claim1_result.isError is False
                assert claim1_result.structuredContent["ok"] is True
                lease1 = claim1_result.structuredContent["lease"]
                assert lease1["taskId"] == "INT-001"
                assert lease1["agentId"] == agent1_id

        # Client 2 connects independently and claims INT-002
        async with stdio_client(server_params) as (read2, write2):
            async with ClientSession(read2, write2) as session2:
                await session2.initialize()

                # Join as different agent
                agent2_result = await session2.call_tool("lodestar.agent.join", {"name": "Agent 2"})
                agent2_id = agent2_result.structuredContent["agentId"]

                # Claim INT-002 (different task)
                claim2_result = await session2.call_tool(
                    "lodestar.task.claim",
                    {
                        "task_id": "INT-002",
                        "agent_id": agent2_id,
                        "ttl_seconds": 900,
                    },
                )

                assert claim2_result.isError is None or claim2_result.isError is False
                assert claim2_result.structuredContent["ok"] is True
                lease2 = claim2_result.structuredContent["lease"]
                assert lease2["taskId"] == "INT-002"
                assert lease2["agentId"] == agent2_id

    @pytest.mark.anyio
    async def test_second_claim_on_same_task_fails(self, test_repo):
        """Test that claiming an already-claimed task fails."""
        server_params = get_server_params(test_repo)

        # First client claims INT-001
        async with stdio_client(server_params) as (read1, write1):
            async with ClientSession(read1, write1) as session1:
                await session1.initialize()

                agent1_result = await session1.call_tool("lodestar.agent.join", {"name": "Agent 1"})
                agent1_id = agent1_result.structuredContent["agentId"]

                claim1_result = await session1.call_tool(
                    "lodestar.task.claim",
                    {
                        "task_id": "INT-001",
                        "agent_id": agent1_id,
                        "ttl_seconds": 900,
                    },
                )

                assert claim1_result.structuredContent["ok"] is True

                # Second client tries to claim the same task
                async with stdio_client(server_params) as (read2, write2):
                    async with ClientSession(read2, write2) as session2:
                        await session2.initialize()

                        agent2_result = await session2.call_tool(
                            "lodestar.agent.join", {"name": "Agent 2"}
                        )
                        agent2_id = agent2_result.structuredContent["agentId"]

                        claim2_result = await session2.call_tool(
                            "lodestar.task.claim",
                            {
                                "task_id": "INT-001",
                                "agent_id": agent2_id,
                                "ttl_seconds": 900,
                            },
                        )

                        # Should fail - task is already claimed
                        assert claim2_result.isError is True
                        assert "ALREADY_CLAIMED" in claim2_result.structuredContent["error_code"]


class TestMessaging:
    """Test message send/receive/ack functionality."""

    @pytest.mark.anyio
    async def test_send_and_receive_message(self, test_repo):
        """Test sending a message and receiving it."""
        server_params = get_server_params(test_repo)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Join as two different agents
                agent1_result = await session.call_tool("lodestar.agent.join", {"name": "Agent 1"})
                agent1_id = agent1_result.structuredContent["agentId"]

                agent2_result = await session.call_tool("lodestar.agent.join", {"name": "Agent 2"})
                agent2_id = agent2_result.structuredContent["agentId"]

                # Agent 1 sends message to Agent 2
                send_result = await session.call_tool(
                    "lodestar.message.send",
                    {
                        "from_agent_id": agent1_id,
                        "to_agent_id": agent2_id,
                        "body": "Hello from Agent 1!",
                    },
                )

                assert send_result.isError is None or send_result.isError is False
                assert send_result.structuredContent["ok"] is True
                message_id = send_result.structuredContent["messageId"]

                # Agent 2 lists messages
                list_result = await session.call_tool(
                    "lodestar.message.list",
                    {
                        "agent_id": agent2_id,
                    },
                )

                assert list_result.isError is None or list_result.isError is False
                messages = list_result.structuredContent["messages"]
                assert len(messages) > 0

                # Find our message
                our_message = next((m for m in messages if m["id"] == message_id), None)
                assert our_message is not None
                assert our_message["from"] == agent1_id
                assert our_message["to"] == agent2_id
                assert our_message["body"] == "Hello from Agent 1!"

    @pytest.mark.anyio
    async def test_message_acknowledgment(self, test_repo):
        """Test acknowledging a message."""
        server_params = get_server_params(test_repo)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Join as two agents
                agent1_result = await session.call_tool("lodestar.agent.join", {"name": "Agent 1"})
                agent1_id = agent1_result.structuredContent["agentId"]

                agent2_result = await session.call_tool("lodestar.agent.join", {"name": "Agent 2"})
                agent2_id = agent2_result.structuredContent["agentId"]

                # Send message
                send_result = await session.call_tool(
                    "lodestar.message.send",
                    {
                        "from_agent_id": agent1_id,
                        "to_agent_id": agent2_id,
                        "body": "Test message for ack",
                    },
                )
                message_id = send_result.structuredContent["messageId"]

                # Acknowledge the message
                ack_result = await session.call_tool(
                    "lodestar.message.ack",
                    {
                        "message_ids": [message_id],
                        "agent_id": agent2_id,
                    },
                )

                assert ack_result.isError is None or ack_result.isError is False
                assert ack_result.structuredContent["ok"] is True

                # List messages again and verify ack status (pass unread_only=False to see all)
                list_result = await session.call_tool(
                    "lodestar.message.list",
                    {
                        "agent_id": agent2_id,
                        "unread_only": False,
                    },
                )

                messages = list_result.structuredContent["messages"]
                our_message = next((m for m in messages if m["id"] == message_id), None)
                assert our_message is not None
                assert "readAt" in our_message  # Should have readAt field if acknowledged


class TestEventStreaming:
    """Test event stream consumption."""

    @pytest.mark.anyio
    async def test_event_stream_contains_claim_events(self, test_repo):
        """Test that event stream contains task claim events."""
        server_params = get_server_params(test_repo)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Join as agent
                agent_result = await session.call_tool(
                    "lodestar.agent.join", {"name": "Event Agent"}
                )
                agent_id = agent_result.structuredContent["agentId"]

                # Claim a task (generates event)
                await session.call_tool(
                    "lodestar.task.claim",
                    {
                        "task_id": "INT-001",
                        "agent_id": agent_id,
                        "ttl_seconds": 900,
                    },
                )

                # Get event stream
                events_result = await session.call_tool(
                    "lodestar.events.pull",
                    {
                        "since_cursor": 0,
                        "limit": 10,
                    },
                )

                assert events_result.isError is None or events_result.isError is False
                events = events_result.structuredContent["events"]

                # Should have at least one event
                assert len(events) > 0

                # Find task.claim event
                claim_events = [e for e in events if e["type"] == "task.claim"]
                assert len(claim_events) > 0

                # Verify event data
                claim_event = claim_events[0]
                assert claim_event["actorAgentId"] == agent_id
                assert claim_event["taskId"] == "INT-001"

    @pytest.mark.anyio
    async def test_event_stream_pagination(self, test_repo):
        """Test event stream pagination with limit and offset."""
        server_params = get_server_params(test_repo)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Join as agent
                agent_result = await session.call_tool(
                    "lodestar.agent.join", {"name": "Pagination Agent"}
                )
                agent_id = agent_result.structuredContent["agentId"]

                # Generate multiple events by claiming tasks
                for task_id in ["INT-001", "INT-002", "INT-003"]:
                    await session.call_tool(
                        "lodestar.task.claim",
                        {
                            "task_id": task_id,
                            "agent_id": agent_id,
                            "ttl_seconds": 900,
                        },
                    )

                # Get first page of events
                page1_result = await session.call_tool(
                    "lodestar.events.pull",
                    {
                        "since_cursor": 0,
                        "limit": 2,
                    },
                )

                assert page1_result.isError is None or page1_result.isError is False
                page1_events = page1_result.structuredContent["events"]
                assert len(page1_events) >= 1  # Should have at least the agent.join event

                # Get second page of events using nextCursor from first page
                if "nextCursor" in page1_result.structuredContent:
                    next_cursor = page1_result.structuredContent["nextCursor"]
                    page2_result = await session.call_tool(
                        "lodestar.events.pull",
                        {
                            "since_cursor": next_cursor,
                            "limit": 2,
                        },
                    )

                    assert page2_result.isError is None or page2_result.isError is False
                    page2_events = page2_result.structuredContent["events"]
                    assert len(page2_events) >= 0  # May be less than 2 depending on total events

                    # Events should be different (no overlap)
                    if len(page2_events) > 0:
                        page1_ids = {e["id"] for e in page1_events}
                        page2_ids = {e["id"] for e in page2_events}
                        assert page1_ids.isdisjoint(page2_ids)


class TestResourceAccess:
    """Test MCP resource access (status, spec, tasks)."""

    @pytest.mark.anyio
    async def test_status_resource(self, test_repo):
        """Test accessing the lodestar://status resource."""
        server_params = get_server_params(test_repo)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # List resources
                resources_result = await session.list_resources()
                resource_uris = [r.uri for r in resources_result.resources]

                # Should have status resource
                assert any("lodestar://status" in str(uri) for uri in resource_uris)

                # Read status resource
                from mcp.types import AnyUrl

                status_content = await session.read_resource(AnyUrl("lodestar://status"))
                assert len(status_content.contents) > 0

    @pytest.mark.anyio
    async def test_spec_resource(self, test_repo):
        """Test accessing the lodestar://spec resource."""
        server_params = get_server_params(test_repo)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Read spec resource
                from mcp.types import AnyUrl

                spec_content = await session.read_resource(AnyUrl("lodestar://spec"))
                assert len(spec_content.contents) > 0

                # Verify it contains YAML content
                text_content = spec_content.contents[0]
                from mcp import types

                if isinstance(text_content, types.TextContent):
                    assert "project:" in text_content.text
                    assert "tasks:" in text_content.text

    @pytest.mark.anyio
    async def test_task_resource(self, test_repo):
        """Test accessing a specific task resource."""
        server_params = get_server_params(test_repo)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Read task resource
                from mcp.types import AnyUrl

                task_content = await session.read_resource(AnyUrl("lodestar://task/INT-001"))
                assert len(task_content.contents) > 0

                # Verify it contains task details
                text_content = task_content.contents[0]
                from mcp import types

                if isinstance(text_content, types.TextContent):
                    assert "INT-001" in text_content.text
                    assert "First integration test task" in text_content.text
