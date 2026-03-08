---
name: pickup
description: Resume work from a handoff — list pending handoffs or restore full context from a specific one. Use when the user wants to continue where they left off, check what work is parked, or restore context from a previous session. Do NOT trigger for creating new handoffs (use relay:context-gatherer), checking issue status (use relay:status), or general session questions unrelated to a relay handoff.
argument-hint: "[<issue_id>] [--list]"
allowed-tools: "ToolSearch,Bash(relay:*)"
---

# Relay Pickup

Resume from a handoff. Uses MCP tool as primary method.

## Primary: MCP tool

Load via ToolSearch (`search for "pickup"`) if not available, then call:

```
pickup(issue_id="BEADS-123", list=false, project="SLUG")
```

- Omit `issue_id` and set `list=true` to list pending handoffs.
- Provide `issue_id` to restore a specific handoff's context.

## Fallback: CLI

```bash
relay pickup --list [--project SLUG]
relay pickup ISSUE_ID [--project SLUG]
```

## After pickup

Present: objective, branch info, decisions, next steps, notes. If current branch differs from the handoff branch, warn the user.
