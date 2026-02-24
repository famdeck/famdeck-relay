---
name: pickup
description: "Resume work from a handoff — lists pending handoffs or restores full context from a specific one."
metadata: {"openclaw":{"emoji":"📥","requires":{"bins":["bd"]}}}
allowed-tools: "Bash(relay:*)"
---

# Relay Pickup

Resume from a handoff via the `relay` CLI.

## List Pending Handoffs

```bash
relay pickup --list [--project SLUG]
```

## Pick Up a Specific Handoff

```bash
relay pickup ISSUE_ID [--project SLUG]
```

The CLI reads the handoff, marks it as `in_progress`, and returns the full context.

Present the restored context to the user: objective, branch, decisions, next steps, notes.

If on a different branch than the handoff, inform the user.
