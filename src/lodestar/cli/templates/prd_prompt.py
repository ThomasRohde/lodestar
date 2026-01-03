"""PRD-PROMPT.md template for lodestar init --prd command.

This template provides instructions for AI agents generating PRDs
in Lodestar's reference format. The output PRD should be suitable
for task decomposition and PRD context delivery.
"""

from __future__ import annotations

PRD_PROMPT_TEMPLATE = """# PRD Generation Instructions for {project_name}

You are generating a Product Requirements Document (PRD) for a project managed by [Lodestar](https://github.com/lodestar-cli/lodestar), a multi-agent task coordination system.

The PRD you create will be the source of truth for task generation. Agents will claim tasks that reference specific sections of your PRD, so **structure is critical**.

---

## Output Requirements

Generate a file named `PRD.md` in the repository root with the following characteristics:

### 1. Explicit Section Anchors

Every heading must have an explicit anchor using `{{#anchor-name}}` syntax:

```markdown
## Feature Name {{#feature-name}}
```

**Why?** Tasks reference PRD sections by anchor. Explicit anchors survive heading renames.

**Anchor conventions:**
- Lowercase with hyphens: `{{#user-authentication}}`
- Feature sections: `{{#feature-name}}`
- Requirements: `{{#feature-name-requirements}}`
- Acceptance criteria: `{{#feature-name-criteria}}`
- Cross-cutting: `{{#constraints}}`, `{{#success-metrics}}`

### 2. 15-Minute Scope Per Section

Each feature section should be implementable in approximately 15 minutes. This is Lodestar's lease duration.

**Signs a section is too large:**
- More than 5 requirements
- Would touch more than 3-4 files
- Contains "and also" connecting unrelated features

**If too large:** Break into subsections, each with its own anchor.

### 3. Testable Acceptance Criteria

Every feature section MUST include acceptance criteria that can be:
- Verified programmatically (tests, linting, type checks)
- Observed in behavior (API returns X, UI shows Y)
- Measured (latency < 100ms, 95th percentile)

**Bad:** "Works correctly", "Handles errors gracefully"
**Good:** "Returns 200 OK with JSON body", "Returns 400 for invalid input with error message"

### 4. Implementation Notes

Include hints about:
- File paths to modify
- Patterns to follow from existing code
- Dependencies between sections
- Related sections for context

---

## PRD Template

Use this structure:

```markdown
# {project_name} - Product Requirements Document

## Overview {{#overview}}

<1-2 paragraphs describing the product/feature>

## Goals {{#goals}}

1. <Primary goal>
2. <Secondary goal>
3. <Tertiary goal>

## Non-Goals {{#non-goals}}

- <What this project explicitly will NOT do>
- <Scope boundaries>

---

## Feature: <Feature 1 Name> {{#feature-1}}

<Summary paragraph>

### Requirements {{#feature-1-requirements}}

1. <Requirement>
2. <Requirement>
3. <Requirement>

### Acceptance Criteria {{#feature-1-criteria}}

- [ ] <Testable criterion>
- [ ] <Testable criterion>
- [ ] <Testable criterion>

### Implementation Notes {{#feature-1-notes}}

<Files to modify, patterns to follow, dependencies>

---

## Feature: <Feature 2 Name> {{#feature-2}}

<Same structure as above>

---

## Constraints {{#constraints}}

Technical and business constraints that apply across features.

### Performance {{#constraints-performance}}

- <Performance requirement>

### Security {{#constraints-security}}

- <Security requirement>

---

## Success Metrics {{#success-metrics}}

How we measure success after implementation.

- <Metric 1>
- <Metric 2>

---

## Implementation Order {{#implementation-order}}

Suggested sequence for task creation:

1. <Phase 1: Foundation>
2. <Phase 2: Core features>
3. <Phase 3: Polish>

## References {{#references}}

- <Link to related docs>
- <Link to design files>
```

---

## Example: Well-Structured Section

```markdown
## Feature: Password Reset {{#password-reset}}

Users can reset their password via email-verified token.

### Requirements {{#password-reset-requirements}}

1. Forgot password link on login page sends reset email
2. Reset tokens expire after 15 minutes
3. Tokens are single-use (invalidated after use)
4. Password strength rules apply to new password

### Acceptance Criteria {{#password-reset-criteria}}

- [ ] Email sent within 5 seconds of request
- [ ] Token stored as hashed value (not plain text)
- [ ] Expired/used tokens return 400 with clear error message
- [ ] Rate limited to 3 requests per email per hour
- [ ] New password must meet strength requirements

### Implementation Notes {{#password-reset-notes}}

- See existing email service in `src/services/email.py`
- Token generation: use `secrets.token_urlsafe(32)`
- Follow validation pattern from `src/auth/validators.py`
- Depends on: User model (Feature #user-management)
```

This section would spawn 2-3 tasks:
1. Token generation and storage
2. Email sending with reset link
3. Reset endpoint and validation

---

## Task Creation from PRD

After generating the PRD, tasks are created with references:

```bash
lodestar task create \\
    --id "F001" \\
    --title "Implement password reset tokens" \\
    --description "WHAT: Generate secure reset tokens with 15-min expiry.
WHERE: src/auth/tokens.py, src/models/reset_token.py
WHY: Users need self-service password recovery
SCOPE: Token generation only. Email sending is F002.
ACCEPT: See PRD #password-reset-criteria" \\
    --prd-source "PRD.md" \\
    --prd-ref "#password-reset-requirements" \\
    --prd-ref "#password-reset-criteria" \\
    --accept "Tokens are 32+ bytes of cryptographic randomness" \\
    --accept "Tokens stored as hashed values" \\
    --accept "Tokens expire after 15 minutes" \\
    --lock "src/auth/tokens.py" \\
    --priority 2
```

---

## Verification Checklist

Before finalizing the PRD, verify:

- [ ] Every section has an explicit `{{#anchor}}`
- [ ] Each feature section is implementable in ~15 minutes
- [ ] Acceptance criteria are testable (not subjective)
- [ ] No section has more than 5 requirements
- [ ] Implementation notes include file paths where relevant
- [ ] Anchors use lowercase-with-hyphens convention
- [ ] Non-goals clearly state what's out of scope
- [ ] Implementation order reflects dependencies

---

## Anti-Patterns to Avoid

### Bad: Monolithic Sections

```markdown
## Authentication {{#auth}}

Complete authentication with login, registration, password reset,
OAuth, session management, and role-based access control.
```

**Fix:** Break into 5+ separate feature sections.

### Bad: Vague Criteria

```markdown
### Acceptance Criteria
- Works correctly
- Handles errors
- Good performance
```

**Fix:** Quantify everything. "Returns 200 in <100ms", "400 for invalid input".

### Bad: Implicit Anchors

```markdown
## User Authentication
```

**Fix:** Add explicit anchor: `## User Authentication {{#user-auth}}`

### Bad: Missing Implementation Notes

```markdown
## Feature: API Rate Limiting {{#rate-limiting}}

Limit API requests to prevent abuse.

### Acceptance Criteria
- [ ] Requests over limit return 429
```

**Fix:** Add notes about files, middleware patterns, existing rate limiting code.

---

## Output

Generate `PRD.md` following this guide. The document should:

1. Cover all features the user described
2. Use explicit anchors on every section
3. Keep each section to ~15-minute implementation scope
4. Include testable acceptance criteria
5. Provide implementation notes with file paths
6. Suggest an implementation order

The PRD will be committed to the repository and used as the source of truth for Lodestar task management.
"""


def render_prd_prompt(project_name: str) -> str:
    """Render PRD prompt template for a project."""
    return PRD_PROMPT_TEMPLATE.format(project_name=project_name)
