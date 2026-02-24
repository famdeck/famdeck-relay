---
name: status
description: Cross-project issue dashboard — shows issues across all configured trackers (GitHub, GitLab, Jira, beads) in a unified view. Use when checking issue status, reviewing open work, or getting an overview of project issues.
argument-hint: "[--all] [--project <slug>] [--tracker <name>] [--status open|closed|all] [--limit <n>]"
allowed-tools: "Bash(relay:*),ToolSearch"
---

# Relay Status

Show unified issue dashboard via the `relay` CLI.

```bash
relay status [--all] [--project SLUG] [--tracker NAME] [--status open|closed|all] [--limit N]
```

Parse `$ARGUMENTS` and run. The CLI queries all configured trackers.

If any tracker returns `"status": "needs_mcp"`, execute the MCP tool call with the provided params and report results.

Format the output as a readable table grouped by project and tracker.
