---
name: relay
description: "Cross-project issue routing. Create issues in the right tracker (GitHub, GitLab, Jira, Beads) based on per-project .claude/relay.yaml config."
metadata: {"openclaw":{"emoji":"🔀","requires":{"anyBins":["gh","bd"]}}}
allowed-tools: "Read,Bash(relay:*),ToolSearch,Bash(which:*)"
---

# Relay — Issue Router

Route issues to the correct tracker via the `relay` CLI.

## Creating an Issue

```bash
relay issue "TITLE" --type TYPE --priority PRIORITY --body "BODY" [--labels L1 L2] [--tracker NAME] [--project SLUG] [--source human|agent] [--no-beads]
```

The CLI handles config reading, routing rules, adapter dispatch (gh/bd directly), and beads cross-referencing.

## Handling MCP Results

If CLI returns `"status": "needs_mcp"`, the target tracker requires an MCP tool:
1. Use ToolSearch to load the tool from the response's `tool` field
2. Call the MCP tool with the provided `params`
3. Report the result

## Dry-Run Routing

```bash
relay route "TITLE" --type bug --priority high [--source agent]
```

Shows which tracker would be chosen without creating anything.

## Tracker Management

```bash
relay trackers                    # Show config
relay trackers init               # Auto-detect and create config
relay trackers add --type github --repo org/repo
relay trackers remove --name beads
```

## Status Dashboard

```bash
relay status                      # Current project
relay status --all                # All atlas projects
relay status --tracker github     # Specific tracker only
```
