"""CLI templates package."""

from lodestar.cli.templates.agents_md import (
    AGENTS_MD_CLI_TEMPLATE,
    AGENTS_MD_MCP_TEMPLATE,
    render_agents_md_cli,
    render_agents_md_mcp,
)
from lodestar.cli.templates.prd_prompt import (
    PRD_PROMPT_TEMPLATE,
    render_prd_prompt,
)

__all__ = [
    "AGENTS_MD_CLI_TEMPLATE",
    "AGENTS_MD_MCP_TEMPLATE",
    "PRD_PROMPT_TEMPLATE",
    "render_agents_md_cli",
    "render_agents_md_mcp",
    "render_prd_prompt",
]
