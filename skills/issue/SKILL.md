---
name: issue
description: Create and route an issue to the right tracker (GitHub, GitLab, Jira, beads). Trigger phrases — "file a bug", "create issue", "log a task", "feature request", "report a problem", "open a ticket". PROACTIVE — trigger this automatically when you discover a bug, needed fix, or improvement in ANY project, especially one other than the current. Don't silently move on — file the issue so it gets tracked upstream. Use atlas to resolve project slugs.
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
