---
name: pickup
description: Resume work from a handoff — lists pending handoffs or restores full context from a specific one. Use when picking up handed-off work, resuming after a break, or checking what's waiting.
argument-hint: "[<issue_id>] [--list]"
allowed-tools: "ToolSearch,Bash(relay:*)"
---

# Relay Pickup

Resume from a handoff.

## Primary: MCP tool

Call the `pickup` MCP tool directly:

```
pickup(
  issue_id="BEADS-123",  # optional: specific handoff to pick up
  list=false,            # true to list pending handoffs
  project="SLUG"         # optional: atlas project slug
)
```

Load it via ToolSearch if not already available: search for `pickup`.

## Fallback: CLI

List pending handoffs:
```bash
relay pickup --list [--project SLUG]
```

Pick up a specific handoff:
```bash
relay pickup ISSUE_ID [--project SLUG]
```

Present the restored context to the user: objective, branch info, decisions, next steps, and any notes.

If on a different branch than the handoff, inform the user.
