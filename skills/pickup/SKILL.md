---
name: pickup
description: Resume work from a handoff — lists pending handoffs or restores full context from a specific one. Use when picking up handed-off work, resuming after a break, or checking what's waiting.
argument-hint: "[<issue_id>] [--list]"
---

# Relay Pickup

Resume work from a handoff beads issue.

Refer to `knowledge/handoff-protocol.md` for the description format and label conventions.

## Parse Arguments

Parse `$ARGUMENTS`:
- Positional: `issue_id` (beads issue ID). If omitted → list and select interactively.
- `--list`: List pending handoffs without picking one up.

## Step 1: Check Prerequisites

Verify `bd` CLI is available (`which bd`). If not: "Beads CLI required for handoffs. Install beads first."

## Step 2: List Handoff Issues

Query beads for handoff issues:
```bash
bd list --label relay:handoff --status open
```

If no results: "No pending handoffs on this branch."

## Step 3: Display Pending Handoffs

Show a table of pending handoffs:
```
Pending Handoffs:
  ID          Title                                    From        Branch
  bd-abc123   Handoff: JWT token refresh               ivintik     feature/jwt
  bd-def456   Handoff: Session cleanup refactoring     colleague   main
```

Extract "from" and "branch" from labels (`handoff:from:*`, `handoff:branch:*`).

If `--list` was passed, stop here.

## Step 4: Select Handoff

- If `issue_id` provided: use it directly
- If multiple pending: use AskUserQuestion to let user pick
- If exactly one: confirm with user before proceeding

## Step 5: Restore Context

Read the full issue: `bd show {issue_id}`

Parse the structured markdown description and present it clearly:

```
Picking up: {issue_id} — {title}

Objective:
  {objective}

Branch: {branch} @ {commit} (uncommitted: {yes|no})

Summary:
  {summary}

Decisions:
  - {decision}: {rationale}

Active Issues:
  - [{source}] {id}: {title} ({status})

Next Steps:
  1. {step}
  2. {step}

Blockers:
  {blockers or "None"}

Notes:
  {notes}
```

## Step 6: Check Branch Match

1. Get current branch: `git branch --show-current`
2. Compare with handoff's branch (from `handoff:branch:*` label or description)
3. If different: "This handoff was created on branch '{branch}'. You're on '{current}'."

## Step 7: Mark as Picked Up

Update the beads issue status:
```bash
bd update {issue_id} --status in_progress
```

## Output

```
Handoff {issue_id} picked up.
  Context restored — see summary above.
  Currently on branch: {current_branch}

Ready to continue. Start with the next steps listed above.
When done, close the handoff: bd close {issue_id}
```
