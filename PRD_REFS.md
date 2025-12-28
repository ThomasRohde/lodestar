Our underlying goal here is “make every claimed task come with just-enough product intent, reliably, without re-reading a giant doc.” The PRD should stay the source of truth, but tasks should be the delivery mechanism for context.

A good mental model is: PRD = encyclopedia, task = mission card. Mission cards should either (a) embed what you need, or (b) point to exactly where to fetch it (and Lodestar should make that fetch automatic).

Here are strategies, ranging from simplest/most robust to more ambitious.

1. Make tasks self-contained (PRD → task distillation at creation time)
   When an agent generates tasks from the PRD (the moment it has full context), have it copy the relevant intent into the task itself:

* “Why” (1–2 sentences)
* constraints (perf, compat, UX rules, non-goals)
* acceptance criteria (checklist)
  This is boring-but-effective: future sessions never need the PRD at all for most tasks. It also fits Lodestar’s “spec plane” idea where task definitions are committed and shared. ([GitHub][1])

2. PRD section pointers (stable anchors) + “task context” command
   Add an explicit field on each task like `prd_refs`, containing stable references:

* file path: `PRD.md`
* section anchor: `#task-claiming` (or generated IDs)
* optional line/byte ranges (more stable than GitHub anchors if the PRD changes formatting)
  Then implement `lodestar task context TASK-123` that prints only the referenced sections (and nothing else), ideally with a token/char budget and `--json` output (consistent with your self-documenting CLI approach). ([GitHub][1])

Key detail: don’t rely on humans/agents to “remember to open the PRD.” Make the *default workflow* surface context.

3. Auto-attach a “context excerpt” snapshot to each task
   Pointers are great until the PRD changes. So also store a small excerpt snapshot captured at task creation time:

* `prd_excerpt`: a few paragraphs copied verbatim
* `prd_excerpt_hash`: to detect drift
  This gives you a “frozen intent” that’s stable across sessions, while still allowing a “jump to source” when needed.

4. Add PRD digests and mismatch warnings (cheap guardrail)
   Store a PRD content hash (or git blob hash) on:

* the whole task set (spec-level metadata), and/or
* per task
  On `lodestar task claim`, if the PRD has changed since the task was created, emit a loud warning:
* “This task was derived from PRD hash X, current PRD hash is Y. Run `lodestar prd sync` or review refs.”
  This is the “don’t silently do the wrong thing” strategy.

5. “Epic” (or “Feature”) nodes that hold shared PRD context; tasks inherit
   Instead of linking every task directly to the PRD, introduce one level up:

* Epic/Feature has `prd_refs`, `summary`, constraints, non-goals
* Tasks reference the epic and inherit that context automatically in `task context`
  This avoids duplicating the same PRD excerpt across 12 tasks and keeps context lean.

6. Requirement IDs in the PRD (REQ-###) and task-to-requirement linking
   If you label requirements in the PRD (even lightly), tasks can link to `REQ-014`, `REQ-027`.
   Then `lodestar prd show REQ-014` or `lodestar task context` can pull exactly those requirement blocks.

This is especially strong when you later want traceability views:

* “Which tasks implement REQ-014?”
* “Which requirements are still uncovered?”

7. Deterministic PRD retrieval: build a local PRD index (SQLite FTS5) and store queries on tasks
   Because Lodestar already leans on SQLite for race-free local coordination ([GitHub][1]), you can add an optional *read-only* PRD index:

* build an FTS index over PRD sections/paragraphs
* each task stores `prd_query` terms (auto-generated at creation time)
* `lodestar task context` runs the query, returns top N snippets within a strict size budget
  This avoids embeddings/model variance and still gives “RAG-like” behavior.

8. Make context delivery part of the claim flow (remove reliance on agent discipline)
   Even with `AGENTS.md`/`CLAUDE.md`, some agents won’t read them. The more reliable pattern:

* `lodestar task claim` prints the task plus its computed context bundle by default
* `--no-context` exists, but is opt-out
  For programmatic agents, `lodestar task claim --json` should include a `context` object, so orchestrators can inject it without extra steps. ([GitHub][1])

9. Generate “task brief” files (small, dedicated docs) and link them
   When tasks are created, write a brief file per task:

* `.lodestar/briefs/TASK-123.md` (committed) or `docs/briefs/...`
  This is basically “self-contained task cards” but keeps spec.yaml from ballooning.

Bonus: agents can open one small markdown file and get everything.

10. “Progressive context levels” (what agents need differs by phase)
    Encode three levels of context and teach the CLI to serve the right one:

* Level 0: one-line product goal (global, always shown)
* Level 1: task brief (default on claim)
* Level 2: PRD excerpts (on demand)
* Level 3: full PRD (rare)
  This matches your progressive-discovery philosophy. ([GitHub][1])

11. (More ambitious) Agent-generated micro-summaries, stored once, used forever
    At task creation time, the agent can generate:

* `task_brief`: 150–300 tokens
* `gotchas`: 5 bullets
* `definition_of_done`: checklist
  Store these in the spec plane. Later sessions never need the PRD unless something is ambiguous.
  This is like strategy #1, but intentionally “budgeted” for context windows.

We are going to implement this recommendation:

A concrete shape that combines the strongest ideas
If I were designing the default Lodestar path, I’d implement:

* `prd_refs` + `prd_excerpt` + `prd_hash` on tasks (direct link + frozen snapshot + drift detection)
* `lodestar task context <id>` (always returns a strict-size bundle)
* `lodestar task claim` includes that bundle by default (so agents don’t have to remember)
* optional epic-level inheritance if you see duplication pressure

Example (illustrative YAML, not assuming your exact schema):

```yaml
tasks:
  - id: TASK-042
    title: "Add lease-aware atomic claim"
    description: "Implement task claiming with TTL leases."
    why: "Prevents two agents from working the same task concurrently."
    acceptance:
      - "Claim is atomic under concurrent attempts"
      - "Lease expires and task becomes claimable again"
    prd:
      source: PRD.md
      refs:
        - anchor: "#task-claiming-with-leases"
          lines: [280, 335]
      excerpt: |
        (copied relevant PRD paragraphs here)
      prd_hash: "sha256:…"
```

This aligns cleanly with Lodestar’s two-plane model: all of this belongs in the committed spec plane so every machine/agent gets the same context contract. ([GitHub][1])

One more “meta” tactic: make task generation produce context, not just tasks
Right now you do: PRD → tasks.
Change it to: PRD → (tasks + context bundles + trace map).
Because, like you said, the task-creating agent is the only one guaranteed to have read the PRD — so squeeze value out of that moment.

