# PRD: Task Creation Guidance & PRD Authoring {#overview}

**Status**: In Progress  
**Priority**: High  
**Owner**: Copilot-TaskCreation (ABF1D05AD)

## Problem Statement {#problem}

Task creation is the most critical bottleneck in Lodestar's multi-agent coordination. Poorly structured tasks cause:

1. **Context loss** — Executing agents lack the "why" behind their work
2. **Scope creep** — Tasks exceed the 15-minute lease window
3. **Missing references** — No link to PRD/spec for traceability
4. **Verification failures** — No clear acceptance criteria
5. **Coordination failures** — No file locks declared for concurrent work

The current AGENTS.md templates provide minimal guidance. AI agents creating tasks need comprehensive, structured guidance to produce well-formed tasks.

## Goals {#goals}

1. Provide comprehensive task creation guidance in AGENTS.md templates
2. Add CLI options for all Task model fields (`--lock`, `--accept`, `--validate-prd`)
3. Document how AI agents should author PRDs for Lodestar consumption
4. Ensure all guidance follows software engineering best practices (INVEST, etc.)

## Non-Goals {#non-goals}

- Automated task generation from PRDs (future feature)
- Task quality scoring/validation (deferred to `lodestar task validate` command)
- GUI or web interface for task creation

## Requirements {#requirements}

### R1: CLI Option Additions {#cli-options}

Add the following CLI options to `lodestar task create`:

| Option | Type | Description |
|--------|------|-------------|
| `--lock` | repeatable | Glob patterns for file ownership (e.g., `--lock "src/auth/**"`) |
| `--accept` | repeatable | Acceptance criteria (e.g., `--accept "Tests pass"`) |
| `--validate-prd` | flag | Validate PRD file exists and anchors resolve (default: true) |
| `--no-validate-prd` | flag | Skip PRD validation |

Validation behavior:
- If `--prd-source` is provided, verify file exists
- If `--prd-ref` anchors are provided, verify they exist in the PRD
- Fail with clear error if validation fails
- `--no-validate-prd` bypasses these checks

### R2: MCP Tool Additions {#mcp-tools}

Add corresponding parameters to MCP task creation tools (if they exist) or document that task creation is CLI-only.

The `locks` parameter should be added to `lodestar_task_claim` warnings if not already present.

### R3: AGENTS.md Template Rewrite {#agents-md}

Rewrite both `_agents_md_content()` and `_agents_md_content_mcp()` to include:

#### Task Design Principles Section {#task-principles}

- **15-Minute Rule**: Every task must be completable within a single 15-minute lease
- **INVEST Criteria**: Independent, Negotiable, Valuable, Estimable, Small, Testable
- **PRD Mandate**: All tasks MUST reference a spec/PRD file if one exists
- **Self-Contained**: Task description + PRD excerpt must contain everything needed

#### Task Description Format {#task-format}

Recommended format for task descriptions:

```
WHAT:   Concise statement of what to build/fix
WHERE:  File paths or modules to modify
WHY:    Business context or motivation (link to PRD section)
SCOPE:  Explicit boundaries (what NOT to do)
ACCEPT: Testable acceptance criteria (numbered list)
REFS:   Related tasks, docs, or code patterns to follow
```

#### Task Decomposition Patterns {#decomposition}

Guidance on breaking large work into 15-minute tasks:
- Vertical slicing (end-to-end thin features)
- Horizontal layering (infrastructure → logic → UI)
- Test-first approach (write tests, then implementation)

#### Acceptance Criteria Writing {#acceptance-criteria}

Good acceptance criteria are:
- **Testable**: Can be verified programmatically
- **Specific**: No ambiguous terms
- **Independent**: Each criterion is a single check
- **Complete**: Cover happy path, edge cases, error handling

Examples:
```bash
--accept "Unit tests pass: pytest tests/auth/"
--accept "No regressions: existing tests still pass"
--accept "Lint clean: ruff check returns 0"
--accept "Error case: invalid token returns 401"
```

### R4: PRD Authoring Guide {#prd-authoring}

Create `docs/guides/prd-authoring.md` documenting:

#### Section Anchoring {#prd-anchoring}

PRDs should use explicit anchors for stable references:
```markdown
## Caching Requirements {#caching-requirements}
```

#### Task-Aligned Structure {#prd-structure}

PRD sections should align with potential tasks:
- Each section = one or more tasks
- Clear scope boundaries per section
- Include "done" criteria in each section

#### Scope Bounding {#prd-scope}

Each section should be implementable in ~15 minutes:
- If larger, break into subsections
- Include implementation hints
- Reference related sections

#### Drift-Resistant Writing {#prd-drift}

PRD content that ages well:
- Stable anchors (don't rename sections)
- Version-independent language
- Clear acceptance criteria per section

### R5: Template Extraction {#template-extraction}

Extract AGENTS.md templates from `init.py` to `src/lodestar/cli/templates/agents_md.py`:
- `AGENTS_MD_CLI_TEMPLATE` — f-string template for CLI-only version
- `AGENTS_MD_MCP_TEMPLATE` — f-string template for MCP version
- Update `init.py` to import from templates module

## Implementation Order {#implementation-order}

1. Create templates module and extract existing templates
2. Add `--lock`, `--accept`, `--validate-prd` to task.py
3. Add lock parameter to MCP tools
4. Rewrite CLI template with comprehensive guidance
5. Rewrite MCP template with comprehensive guidance  
6. Create PRD authoring guide
7. Update mkdocs.yml and guides index

## Success Metrics {#success}

- All new CLI options have tests
- PRD validation catches missing files/anchors
- AGENTS.md templates exceed 200 lines of comprehensive guidance
- PRD authoring guide provides actionable patterns

## References {#references}

- [docs/concepts/prd-context.md](../concepts/prd-context.md) — How PRD context works
- [docs/guides/agent-workflow.md](../guides/agent-workflow.md) — Current agent workflow
- [INVEST criteria](https://en.wikipedia.org/wiki/INVEST_(mnemonic)) — User story quality criteria
