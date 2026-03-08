---
name: handoff
description: "Save current work context as a beads issue for later pickup — captures branch, decisions, next steps, active issues. Trigger phrases — 'save my progress', 'hand off work', 'I'm done for now', 'park this work', 'wrap up session', 'context dump'. Use proactively when a session is ending or switching to a different task."
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

Report the created handoff ID and remind: `Pick up later with: /relay:pickup`
