# Relay — Handoff Protocol

## Overview

Handoffs capture work context as **beads issues** with the `relay:handoff` label. They are committed to git, branch-scoped, and readable via `bd show`.

For cross-project messaging (between different repos/agents), use **mcp_agent_mail** instead. See `spec/MESSAGING.md`.

## Storage Model

| Aspect | Value |
|--------|-------|
| Storage | `.beads/` directory (same as all beads issues) |
| Scoping | Branch-scoped (committed to git) |
| Format | Structured markdown in issue description |
| Discovery | `bd list --label relay:handoff --status open` |
| Lifecycle | open → in_progress → closed |

### Why Beads, Not Global Files?

The previous design stored handoffs as JSON envelopes in `~/.claude/relay/handoffs/`. Problems:
- Detached from project — no branch context
- No transport — couldn't switch branches and see relevant handoffs
- No acknowledgment — status tracking was fragile
- Not committed — lost on machine changes

Beads issues solve all of these: they're in-project, branch-scoped, committed, and have built-in status management.

## Handoff Context

The issue description uses structured markdown (see `knowledge/handoff-protocol.md` for full schema):

```markdown
## Objective
JWT token refresh implementation

## Branch
feature/jwt @ abc123 (uncommitted changes: yes)

## Summary
Implemented refresh token rotation. Need to add tests.

## Decisions
- Use refresh token rotation (better security against token theft)

## Next Steps
1. Add unit tests for token rotation
2. Test with mock clock
3. Update API docs

## Active Issues
- [beads] bd-xyz: Implement token rotation (in_progress)

## Files Touched
- src/auth-service.ts (modified): Added rotation logic
- src/token-store.ts (created): New token persistence

## Notes
Free-form context...
```

### Why Structured Markdown?

- **Human-readable**: `bd show` displays it directly
- **Parseable**: Skills can extract sections by heading
- **Lightweight**: No embedded base64 diffs or JSONL exports

## Labels

| Label | Purpose |
|-------|---------|
| `relay:handoff` | Identifies as handoff (required) |
| `handoff:from:<user>` | Creator |
| `handoff:branch:<branch>` | Source branch |
| `handoff:target:<type>` | Intended recipient type |

## Flows

### Creating a Handoff

```
/relay:handoff
/relay:handoff --summary "JWT refresh implementation"
/relay:handoff --instructions "Focus on test coverage"
```

1. Gather project context (atlas + git state)
2. Summarize work (objective, decisions, next steps, files)
3. Create beads issue with `relay:handoff` label
4. Print handoff ID and summary

### Picking Up a Handoff

```
/relay:pickup
/relay:pickup bd-abc123
/relay:pickup --list
```

1. Query beads for `relay:handoff` labeled open issues
2. Select (interactive if multiple)
3. Display full context from description
4. Check branch match
5. Mark as `in_progress`

### Completing a Handoff

```bash
bd close <id>
```

No special skill needed — standard beads lifecycle.

## Branch Scoping

Handoffs are committed with the beads data. When you switch branches:
- `post-checkout` hook imports the target branch's beads state
- Handoffs created on `feature/jwt` are only visible on that branch (and descendants)
- After merging `feature/jwt` → `main`, the handoff appears on `main` too

## Artifacts

Handoffs do **not** embed git diffs or beads exports. Instead:
- The description records the commit hash and uncommitted-changes flag
- Active issues are listed by reference (source + ID)
- The recipient checks out the branch to get the full code state

This avoids stale embedded data and keeps handoffs small.

## Cross-Project Handoffs

For handing off work to a different project/repo, use mcp_agent_mail messaging:

```
send_message(to="agent", subject="Handoff: ...", body="...", thread_id="handoff-...")
```

Beads handoffs are strictly **within-project**. Cross-project coordination is a messaging concern, not a task-tracking concern.
