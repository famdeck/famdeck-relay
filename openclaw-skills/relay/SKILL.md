---
name: relay
description: "Cross-project issue routing — create issues, check status, manage trackers. Routes to GitHub, GitLab, Jira, or Beads based on .claude/relay.yaml config. Trigger phrases — 'file a bug', 'create issue', 'log a task', 'show issues', 'project status', 'configure trackers'. PROACTIVE — trigger when you discover bugs or needed fixes in any project."
metadata: {"openclaw":{"emoji":"🔀","requires":{"anyBins":["gh","bd"]}}}
allowed-tools: "Read,Bash(relay:*),ToolSearch,Bash(which:*)"
---

# Relay — Issue Router

Route issues to the correct tracker via CLI.

## Create issue

```bash
relay issue "TITLE" --type TYPE --priority PRIORITY --body "BODY" [--labels L1 L2] [--tracker NAME] [--project SLUG] [--source human|agent] [--no-beads]
```

## MCP dispatch

If CLI returns `"status": "needs_mcp"`, load the tool via ToolSearch and call it with provided `params`.

## Other commands

```bash
relay route "TITLE" --type bug --priority high   # dry-run routing
relay trackers                                    # show config
relay trackers init                               # auto-detect and create config
relay trackers add --type github --repo org/repo  # add tracker
relay trackers remove --name beads                # remove tracker
relay status [--all] [--tracker NAME]             # issue dashboard
```
