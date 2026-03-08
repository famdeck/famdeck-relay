---
name: issue
description: Create and route an issue to the correct tracker — GitHub, GitLab, Jira, or beads — based on the project's relay config. Use when the user wants to file a bug, log a task, request a feature, or report a problem. PROACTIVE — trigger automatically when you discover a bug or needed fix in any project, especially cross-project; do not silently move on. Do NOT trigger for checking what issues are open (use relay:status), configuring trackers (use relay:trackers), or creating handoffs.
argument-hint: '"title" [--project <slug>] [--tracker <name>] [--type bug|task|feature|chore] [--priority critical|high|medium|low] [--labels <l1,l2>] [--assignee <user>] [--body <text>] [--no-beads]'
allowed-tools: "Read,ToolSearch,Bash(relay:*),Bash(which:*)"
---

# Relay Issue

Create an issue routed to the correct tracker.

## Primary: MCP tool

Load via ToolSearch (`search for "issue"`) if not available, then call:

```
issue(title, type, priority, body, labels=[], tracker="", project="", source="agent", no_beads=false)
```

## Fallback: CLI

```bash
relay issue "TITLE" --type TYPE --priority PRIORITY --body "BODY" [--labels L1 L2] [--tracker NAME] [--project SLUG] [--source human|agent] [--no-beads]
```

## MCP dispatch

If result contains `"status": "needs_mcp"`, the response includes `tool` and `params`:
1. Load the tool via ToolSearch (e.g., `mcp__plugin_ds_gitlab__create_issue`)
2. Call it with the provided params
3. Report the result

## Report

Show: tracker used, issue ID/URL, labels applied.
