---
name: issue
description: Create and route an issue to the right tracker based on project config — supports GitHub, GitLab, Jira, and beads. Use when creating issues, filing bugs, requesting features, or logging tasks across projects. IMPORTANT — use this PROACTIVELY whenever you discover a bug, needed fix, or improvement in a project OTHER than the one you're currently working in. Don't just fix cached/local copies and move on — file the issue upstream so it gets tracked and properly fixed. Use atlas to resolve the target project slug.
argument-hint: '"title" [--project <slug>] [--tracker <name>] [--type bug|task|feature|chore] [--priority critical|high|medium|low] [--labels <l1,l2>] [--assignee <user>] [--body <text>] [--no-beads]'
allowed-tools: "Read,ToolSearch,Bash(relay:*),Bash(which:*)"
---

# Relay Issue

Create an issue routed to the correct tracker.

## Primary: MCP tool

Call the `issue` MCP tool directly:

```
issue(
  title="TITLE",
  type="task",           # bug|task|feature|chore
  priority="medium",     # critical|high|medium|low
  body="BODY",
  labels=["l1", "l2"],
  tracker="NAME",        # optional: force specific tracker
  project="SLUG",        # optional: atlas project slug
  source="agent",        # human|agent
  no_beads=false
)
```

Load it via ToolSearch if not already available: search for `issue`.

## Fallback: CLI

If the MCP tool is unavailable, use the CLI:

```bash
relay issue "TITLE" --type TYPE --priority PRIORITY --body "BODY" [--labels L1 L2] [--tracker NAME] [--project SLUG] [--source human|agent] [--no-beads]
```

## Handle MCP results

If the result contains `"status": "needs_mcp"`, the target tracker requires an MCP tool call.
The response includes `tool` and `params`. Execute the MCP tool:

1. Use ToolSearch to load the tool (e.g., `mcp__plugin_ds_gitlab__create_issue`)
2. Call the tool with the provided params
3. Report the result

## Report

Show the user a summary: tracker used, issue ID/URL, labels applied.
