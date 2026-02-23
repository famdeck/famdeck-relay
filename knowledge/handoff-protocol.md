# Handoff Protocol

Handoffs are **beads issues** with the `relay:handoff` label. They capture work context as structured markdown in the issue description, committed to git and scoped to the current branch.

## Storage

Handoffs live in `.beads/` alongside other beads issues — no separate global directory.

```bash
# Create
bd create --type task --title "Handoff: <objective>" \
  --label relay:handoff --label "handoff:from:<user>" --label "handoff:branch:<branch>"

# List pending
bd list --label relay:handoff --status open

# Pick up
bd update <id> --status in_progress
# ... read description for context ...
bd close <id>

# Show full context
bd show <id>
```

## Description Format

Handoff context goes in the issue description as structured markdown (readable in `bd show`, parseable by skills):

```markdown
## Objective
<what needs to be accomplished>

## Branch
<branch> @ <commit-short> (uncommitted changes: yes|no)

## Summary
<1-2 paragraph overview of current work state>

## Decisions
- <decision>: <rationale>

## Next Steps
1. <step>
2. <step>

## Active Issues
- [<source>] <id>: <title> (<status>)

## Files Touched
- <path> (<action>): <change description>

## Blockers
- <blocker> (or "None")

## Notes
<free-form context, instructions for recipient>
```

## Labels

| Label | Purpose |
|-------|---------|
| `relay:handoff` | Identifies issue as a handoff (required) |
| `handoff:from:<user>` | Who created the handoff |
| `handoff:branch:<branch>` | Branch the handoff was created on |
| `handoff:target:<type>` | Intended recipient type (self, person, agent) |

## Lifecycle

```
open → in_progress → closed
```

- **open**: Created, waiting for pickup.
- **in_progress**: Someone ran `/relay:pickup` — actively working.
- **closed**: Work completed or context no longer needed.

No expiration — beads issues persist until explicitly closed. Branch switching handles visibility (handoff on `feature/jwt` only visible on that branch).

## Artifacts

Git diff and beads export are **not** embedded in the handoff description. Instead:

- **Git diff**: The handoff notes the commit hash and whether uncommitted changes exist. Recipient checks out the branch to get the code state.
- **Beads export**: Active issues are listed by reference (source + ID). Recipient queries them directly.

This keeps handoffs lightweight and avoids stale embedded data.

## Cross-Project Messaging

For cross-project handoffs (different repos), use **mcp_agent_mail** instead:

```
send_message(to="<agent>", subject="Handoff: <objective>", body="<context>", thread_id="handoff-<id>")
```

Beads handoffs are for **within-project** context transfer (same repo, same or different branch). Cross-project messaging is a separate concern handled by the mail system.
