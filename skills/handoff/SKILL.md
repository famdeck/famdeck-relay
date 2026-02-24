---
name: handoff
description: Capture current work context as a beads issue for later pickup — records branch state, decisions, next steps, and active issues. Use when switching context, delegating work, or saving progress for later.
argument-hint: "[--summary <text>] [--instructions <text>]"
allowed-tools: "Bash(relay:*)"
---

# Relay Handoff

Create a work handoff via the `relay` CLI.

## Basic Usage

```bash
relay handoff [--summary "SUMMARY"] [--instructions "INSTRUCTIONS"] [--project SLUG]
```

The CLI automatically captures git state (branch, commit, dirty files) and creates a beads issue with `relay:handoff` label.

## Enriching the Handoff

If no `--summary` is provided, generate one from the current conversation context:
- What was the objective?
- Key decisions made
- What's left to do

Pass it via `--summary`.

If there are special instructions for the next person/session, pass via `--instructions`.

Report the created handoff issue ID to the user.
