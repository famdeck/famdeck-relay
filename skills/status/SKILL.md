---
name: status
description: Cross-project issue dashboard — unified view of issues across all configured trackers (GitHub, GitLab, Jira, beads). Trigger phrases — "show issues", "what's open", "issue dashboard", "project status", "review open work", "what needs attention".
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
