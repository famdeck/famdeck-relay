---
name: handoff
description: "Save current work context as a handoff for later pickup — captures branch, uncommitted changes, decisions, next steps, and active issues. Use when the session is ending, switching to a different task, or parking work. Trigger proactively when work is being paused. Do NOT use for picking up existing handoffs (use pickup) or cross-project issue routing (use relay)."
metadata: {"openclaw":{"emoji":"📦","requires":{"bins":["bd"]}}}
allowed-tools: "Bash(relay:*),Bash(bd:*),Bash(git:*)"
---

# Relay Handoff

Create a work handoff via CLI.

## Usage

```bash
relay handoff --summary "SUMMARY" [--instructions "INSTRUCTIONS"] [--project SLUG]
```

## Building the summary

If no `--summary` provided, build one from session context:
1. Review what was discussed/decided
2. Check `git diff --name-status HEAD` for changed files
3. Check `bd list --status in_progress` for active issues
4. Compose: objective, decisions, next steps, blockers
5. Pass via `--summary`

## Output

Report the created handoff ID and remind: `Pick up later with: /pickup`
