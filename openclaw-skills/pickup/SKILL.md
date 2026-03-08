---
name: pickup
description: "Resume work from a handoff — lists pending handoffs or restores full context. Trigger phrases — 'pick up where I left off', 'resume work', 'what's waiting', 'continue from handoff', 'check pending handoffs'."
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
