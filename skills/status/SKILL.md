---
name: status
description: Cross-project issue dashboard — shows issues across all configured trackers (GitHub, GitLab, Jira, beads) in a unified view. Use when checking issue status, reviewing open work, or getting an overview of project issues.
argument-hint: "[--all] [--project <slug>] [--tracker <name>] [--status open|closed|all] [--limit <n>]"
allowed-tools: "ToolSearch,Bash(relay:*)"
---

# Relay Status

Show unified issue dashboard.

## Primary: MCP tool

Call the `status` MCP tool directly:

```
status(
  all=false,             # true to show all atlas projects
  project="SLUG",        # optional: atlas project slug
  tracker="NAME",        # optional: filter to specific tracker
  status="open",         # open|closed|all
  limit=20
)
```

Load it via ToolSearch if not already available: search for `status`.

## Fallback: CLI

```bash
relay status [--all] [--project SLUG] [--tracker NAME] [--status open|closed|all] [--limit N]
```

If any tracker returns `"status": "needs_mcp"`, execute the MCP tool call with the provided params.

Format the output as a readable table grouped by project and tracker.
