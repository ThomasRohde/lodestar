# PRD Authoring Guide

This guide covers how to write Product Requirements Documents (PRDs) that work well with Lodestar's task management and PRD context delivery features. Whether you're a human writing requirements or an AI agent generating a PRD, these patterns ensure clean task decomposition and reliable context extraction.

## Why PRD Structure Matters

Lodestar enables tasks to reference specific PRD sections via anchors. When an executing agent claims a task, the relevant PRD context is extracted and delivered automatically. This only works well when:

1. Sections have stable, explicit anchors
2. Each section maps to one or more tasks
3. Content is scoped to ~15-minute implementation chunks
4. Acceptance criteria are embedded in each section

A well-structured PRD isn't just documentation—it's the source of truth that flows into every task.

## Section Anchoring

### Use Explicit Anchors

PRD sections should use explicit anchors for stable references:

```markdown
## Caching Requirements {#caching-requirements}

The system must cache API responses to reduce latency.
```

The `{#caching-requirements}` syntax creates an anchor that won't change even if you rename the heading.

### Why Explicit Anchors?

| Approach | Anchor | Risk |
|----------|--------|------|
| Implicit | `#caching-requirements` (from heading text) | Breaks if heading renamed |
| Explicit | `{#caching-requirements}` | Stable through refactoring |

Tasks reference anchors:

```bash
lodestar task create \
    --title "Implement response caching" \
    --prd-source "PRD.md" \
    --prd-ref "#caching-requirements"
```

If you later rename "Caching Requirements" to "Response Caching Strategy", the explicit anchor stays `#caching-requirements` and existing tasks still resolve.

### Anchor Naming Conventions

| Pattern | Example | Use For |
|---------|---------|---------|
| `#<feature>-requirements` | `#auth-requirements` | Feature specs |
| `#<feature>-<aspect>` | `#auth-security` | Subsections |
| `#<category>` | `#constraints` | Cross-cutting concerns |
| `#success-metrics` | `#success-metrics` | Measurable outcomes |

Keep anchors lowercase with hyphens. Avoid underscores, camelCase, or special characters.

## Task-Aligned Structure

Each PRD section should align with potential tasks. Think: "Can an agent implement this section in 15 minutes?"

### Section Template

```markdown
## <Feature Name> {#feature-anchor}

<2-3 sentence summary of what this feature does>

### Requirements

1. <Specific requirement 1>
2. <Specific requirement 2>
3. <Specific requirement 3>

### Acceptance Criteria

- [ ] <Testable criterion 1>
- [ ] <Testable criterion 2>
- [ ] <Testable criterion 3>

### Implementation Notes (Optional)

<Hints about files, patterns, dependencies>
```

### Example: Well-Structured Section

```markdown
## Password Reset Flow {#password-reset}

Users must be able to reset their password via email-verified token.

### Requirements

1. Forgot password link on login page sends reset email
2. Reset tokens expire after 15 minutes
3. Tokens are single-use (invalidated after use)
4. Password strength rules apply to new password

### Acceptance Criteria

- [ ] Email sent within 5 seconds of request
- [ ] Token stored as hashed value (not plain text)
- [ ] Expired/used tokens return clear error message
- [ ] Rate limited to 3 requests per email per hour

### Implementation Notes

See existing email service in `src/services/email.py`.
Token generation should use `secrets.token_urlsafe(32)`.
```

This section could spawn 2-3 tasks:
- Task 1: Token generation and storage
- Task 2: Email sending with reset link  
- Task 3: Reset endpoint and validation

## Scope Bounding

Each section should be implementable in roughly 15 minutes. If larger, break into subsections.

### Signs a Section Is Too Large

- More than 5 requirements
- More than 5 acceptance criteria
- Would touch more than 3-4 files
- Contains "and also" or multiple distinct features

### Breaking Down Large Sections

**Before (too large):**

```markdown
## User Authentication {#auth}

Complete authentication system with login, registration, 
password reset, OAuth, and session management.
```

**After (properly scoped):**

```markdown
## Authentication Overview {#auth-overview}

Authentication uses email/password with optional OAuth.
See subsections for specific features.

### Login Flow {#auth-login}

Email/password authentication with rate limiting.
...

### Registration Flow {#auth-registration}

New user signup with email verification.
...

### Password Reset {#auth-reset}

Email-based password reset with secure tokens.
...

### OAuth Integration {#auth-oauth}

Google and GitHub OAuth providers.
...

### Session Management {#auth-sessions}

JWT-based sessions with refresh tokens.
...
```

Each subsection becomes a claimable task with its own anchor.

## Drift-Resistant Writing

PRD content ages. Write in a way that minimizes drift issues.

### Stable Anchors

Never rename anchors once tasks reference them:

```markdown
<!-- DO: Keep original anchor -->
## Response Caching Strategy {#caching-requirements}

<!-- DON'T: Change anchor when renaming -->
## Response Caching Strategy {#response-caching-strategy}
```

### Version-Independent Language

Avoid specific versions, dates, or temporary states:

```markdown
<!-- DON'T -->
As of v2.3.1, the cache uses Redis...
After the March refactor, we...

<!-- DO -->
The cache uses Redis for...
The current implementation...
```

### Clear Acceptance Criteria Per Section

Each section should have acceptance criteria that can be evaluated independently:

```markdown
### Acceptance Criteria

- [ ] Cache hit returns data in <10ms
- [ ] Cache miss fetches from database
- [ ] TTL of 5 minutes for all cached items
- [ ] Cache invalidation on data mutation
```

These criteria can be copied directly into task `--accept` flags.

## PRD Template

Here's a complete PRD template optimized for Lodestar:

```markdown
# <Project Name> - Product Requirements Document

## Overview {#overview}

<1-2 paragraphs describing the product/feature>

## Goals {#goals}

1. <Primary goal>
2. <Secondary goal>
3. <Tertiary goal>

## Non-Goals {#non-goals}

- <What this project explicitly will NOT do>
- <Scope boundaries>

---

## Feature: <Feature 1 Name> {#feature-1}

<Summary paragraph>

### Requirements {#feature-1-requirements}

1. <Requirement>
2. <Requirement>

### Acceptance Criteria {#feature-1-criteria}

- [ ] <Testable criterion>
- [ ] <Testable criterion>

### Implementation Notes {#feature-1-notes}

<Optional hints about files, patterns, dependencies>

---

## Feature: <Feature 2 Name> {#feature-2}

<Same structure as above>

---

## Constraints {#constraints}

Technical and business constraints that apply across features.

### Performance {#constraints-performance}

- <Performance requirement>

### Security {#constraints-security}

- <Security requirement>

---

## Success Metrics {#success-metrics}

How we measure success after implementation.

- <Metric 1>
- <Metric 2>

---

## Implementation Order {#implementation-order}

Suggested sequence for task creation:

1. <Phase 1: Foundation>
2. <Phase 2: Core features>
3. <Phase 3: Polish>

## References {#references}

- <Link to related docs>
- <Link to design files>
- <Link to prior art>
```

## Creating Tasks from PRDs

Once your PRD is structured, create tasks that reference it:

```bash
# Basic task with PRD reference
lodestar task create \
    --title "Implement password reset tokens" \
    --prd-source "PRD.md" \
    --prd-ref "#auth-reset"

# Full task with all context
lodestar task create \
    --id "F003" \
    --title "Implement password reset tokens" \
    --description "WHAT: Generate secure reset tokens with 15-min expiry.
WHERE: src/auth/tokens.py, src/models/reset_token.py
WHY: Users need self-service password recovery (PRD #auth-reset)
SCOPE: Token generation only. Email sending is F004.
ACCEPT: See PRD #auth-reset acceptance criteria
REFS: Use secrets.token_urlsafe(32) per PRD notes" \
    --prd-source "PRD.md" \
    --prd-ref "#auth-reset" \
    --prd-ref "#constraints-security" \
    --accept "Tokens are 32+ bytes of cryptographic randomness" \
    --accept "Tokens stored as hashed values" \
    --accept "Tokens expire after 15 minutes" \
    --lock "src/auth/tokens.py" \
    --depends-on "F002" \
    --label feature \
    --priority 2
```

## AI Agent Guidelines

When an AI agent generates a PRD:

### Do

- Use explicit `{#anchor}` syntax on all sections
- Keep sections to 15-minute implementation scope
- Include acceptance criteria in every feature section
- Add implementation notes with file paths and patterns
- Structure for progressive disclosure (overview first, details later)
- Use tables for structured information

### Don't

- Create monolithic sections covering multiple features
- Use implicit anchors (heading-text-based)
- Omit acceptance criteria
- Write vague requirements ("should work well")
- Include temporary dates or version numbers in anchors
- Nest more than 3 heading levels deep

### Verification Checklist

Before finalizing a PRD, verify:

- [ ] Every section has an explicit `{#anchor}`
- [ ] Each section is implementable in ~15 minutes
- [ ] Acceptance criteria are testable (not subjective)
- [ ] No section has more than 5 requirements
- [ ] Implementation notes include file paths where relevant
- [ ] Anchors use lowercase-with-hyphens convention
- [ ] Non-goals clearly state what's out of scope

## Summary

Well-structured PRDs enable:

- **Clean task decomposition**: Each section maps to tasks
- **Reliable context delivery**: Explicit anchors resolve correctly
- **Drift resistance**: Stable anchors survive refactoring
- **Self-documenting tasks**: PRD refs provide the "why"

The effort invested in PRD structure pays off in every task created from it.
