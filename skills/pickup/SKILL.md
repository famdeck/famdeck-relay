---
name: pickup
description: Resume work from a handoff — lists pending handoffs or restores full context from a specific one. Use when picking up handed-off work, resuming after a break, or checking what's waiting.
argument-hint: "[<issue_id>] [--list]"
allowed-tools: "Bash(relay:*)"
---

# Relay Pickup

Resume from a handoff via the `relay` CLI.

## List pending handoffs

```bash
relay pickup --list [--project SLUG]
```

## Pick up a specific handoff

```bash
relay pickup ISSUE_ID [--project SLUG]
```

The CLI reads the handoff issue, marks it as in_progress, and returns the full context.

Present the restored context to the user: objective, branch info, decisions, next steps, and any notes.

If on a different branch than the handoff, inform the user.
