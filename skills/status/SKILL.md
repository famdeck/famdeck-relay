---
name: status
description: Show a unified issue dashboard across all configured trackers — GitHub, GitLab, Jira, beads. Use when the user wants to see what's open, review work across projects, or get a cross-tracker overview. Do NOT trigger for creating issues (use relay:issue), configuring trackers (use relay:trackers), or picking up handoffs (use relay:pickup).
argument-hint: "[--all] [--project <slug>] [--tracker <name>] [--status open|closed|all] [--limit <n>]"
allowed-tools: "ToolSearch,Bash(relay:*)"
---

# Relay Status

Show unified issue dashboard.

## Primary: MCP tool

Load via ToolSearch (`search for "status"`) if not available, then call:

```
status(all=false, project="SLUG", tracker="NAME", status="open", limit=20)
```

## Fallback: CLI

```bash
relay status [--all] [--project SLUG] [--tracker NAME] [--status open|closed|all] [--limit N]
```

## MCP dispatch

If any tracker returns `"status": "needs_mcp"`, execute the MCP tool call with the provided params.

## Output

Format as a readable table grouped by project and tracker.
