---
name: handoff
description: Capture current work context as a beads issue for later pickup — records branch state, decisions, next steps, and active issues. Use when switching context, delegating work, or saving progress for later.
argument-hint: "[--summary <text>] [--instructions <text>]"
allowed-tools: "ToolSearch,Bash(relay:*)"
---

# Relay Handoff

Create a work handoff capturing current context.

## Primary: MCP tool

Call the `handoff` MCP tool directly:

```
handoff(
  summary="What was being worked on",
  instructions="Special notes for next person",
  project="SLUG"         # optional: atlas project slug
)
```

Load it via ToolSearch if not already available: search for `handoff`.

## Fallback: CLI

```bash
relay handoff [--summary "SUMMARY"] [--instructions "INSTRUCTIONS"] [--project SLUG]
```

## Enriching the Handoff

If no summary is provided, generate one from the current conversation context:
- What was the objective?
- Key decisions made
- What's left to do

Report the created handoff issue ID to the user.
