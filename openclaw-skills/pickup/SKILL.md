---
name: pickup
description: "Resume work from a handoff — list pending handoffs or restore full context from a specific one. Use when continuing from a previous session or checking what work is parked. Do NOT use for creating new handoffs (use handoff) or routing issues (use relay)."
metadata: {"openclaw":{"emoji":"📥","requires":{"bins":["bd"]}}}
allowed-tools: "Bash(relay:*)"
---

# Relay Pickup

Resume from a handoff via CLI (primary method for openclaw/Telegram context).

## Usage

```bash
relay pickup --list [--project SLUG]     # list pending
relay pickup ISSUE_ID [--project SLUG]   # restore specific
```

The CLI reads the handoff, marks it `in_progress`, and returns full context.

## After pickup

Present: objective, branch, decisions, next steps, notes. Warn if current branch differs from handoff branch.
