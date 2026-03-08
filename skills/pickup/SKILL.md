---
name: pickup
description: Resume work from a handoff — lists pending handoffs or restores full context from a specific one. Trigger phrases — "pick up where I left off", "resume work", "what's waiting for me", "continue from handoff", "check pending handoffs", "what was I working on".
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
