---
name: handoff
description: Capture current work context as a beads issue for later pickup — records branch state, decisions, next steps, and active issues. Use when switching context, delegating work, or saving progress for later.
argument-hint: "[--summary <text>] [--instructions <text>]"
---

# Relay Handoff

Create a beads issue with `relay:handoff` label that captures the current work context.

Refer to `knowledge/handoff-protocol.md` for the description format and label conventions.

## Parse Arguments

Parse `$ARGUMENTS`:
- `--summary <text>`: Override auto-generated work summary.
- `--instructions <text>`: Instructions for the recipient (added to Notes section).

## Step 1: Check Prerequisites

Verify `bd` CLI is available (`which bd`). If not: "Beads CLI required for handoffs. Install beads first."

## Step 2: Gather Project Context

1. Detect current project:
   - Try atlas: read `~/.claude/atlas/registry.yaml`, match cwd
   - If no atlas: use cwd directory name as slug
2. Collect git state:
   - `branch`: `git branch --show-current`
   - `commit`: `git rev-parse --short HEAD`
   - `has_uncommitted`: `git status --porcelain` (non-empty = yes)
   - `files_changed`: `git diff --name-status HEAD` (list of modified files)

## Step 3: Build Context Summary

If `--summary` provided, use it.

Otherwise, generate by reviewing:
- Recent conversation history (what was discussed/decided)
- Files modified (from git diff)
- Active beads issues (`bd list --status in_progress`)

Produce these fields:
- **objective**: What needs to be accomplished (1 line)
- **summary**: 1-2 paragraph overview of current work state
- **files_touched**: List of modified files with brief change descriptions
- **decisions**: Key decisions with rationale
- **next_steps**: Ordered list of remaining work
- **blockers**: Any blockers (or "None")

## Step 4: Gather Active Issues

Collect from beads: `bd list --status in_progress --status open`

Format each as: `- [beads] <id>: <title> (<status>)`

If external issues were referenced in conversation, include those too with their source.

## Step 5: Create Beads Issue

Build the description following `knowledge/handoff-protocol.md` format:

```markdown
## Objective
{objective}

## Branch
{branch} @ {commit} (uncommitted changes: {yes|no})

## Summary
{summary}

## Decisions
{decisions as bullet list, or "None"}

## Next Steps
{next_steps as numbered list}

## Active Issues
{issues as bullet list, or "None"}

## Files Touched
{files as bullet list with action and description}

## Blockers
{blockers or "None"}

## Notes
{--instructions text if provided, otherwise free-form context}
```

Create the issue:
```bash
bd create \
  --type task \
  --title "Handoff: {objective}" \
  --description "{description}" \
  --label relay:handoff \
  --label "handoff:from:{user}" \
  --label "handoff:branch:{branch}"
```

Capture the created issue ID from bd output.

## Output

```
Handoff created: {issue_id}
  Branch: {branch} @ {commit}
  Objective: {objective}
  Files: {N} changed
  Next steps: {N} items

Pick up with: /relay:pickup
```
