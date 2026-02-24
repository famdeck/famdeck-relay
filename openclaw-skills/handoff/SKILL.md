---
name: handoff
description: "Capture current work context as a beads issue for later pickup — records branch state, decisions, next steps, and active issues."
metadata: {"openclaw":{"emoji":"📦","requires":{"bins":["bd"]}}}
allowed-tools: "Bash(relay:*),Bash(bd:*),Bash(git:*)"
---

# Relay Handoff

Create a work handoff via the `relay` CLI.

## Quick Handoff

```bash
relay handoff --summary "SUMMARY" [--instructions "INSTRUCTIONS"] [--project SLUG]
```

The CLI captures git state and creates a beads issue with `relay:handoff` label.

## Rich Handoff

If no `--summary` is provided, build one from conversation context before calling the CLI:

1. Review what was discussed/decided in the session
2. Check `git diff --name-status HEAD` for changed files
3. Check `bd list --status in_progress` for active issues
4. Compose a summary covering: objective, decisions, next steps, blockers
5. Pass via `--summary`

## Output

The CLI returns the created handoff issue ID. Tell the user:
```
Handoff created: {id}
Pick up later with: /relay:pickup
```
