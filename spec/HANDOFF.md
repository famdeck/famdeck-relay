# Relay — Handoff Protocol

## Overview

Handoff is the mechanism for transferring work context between sessions, tools, and people. The handoff envelope is a self-contained JSON document that captures everything needed to resume work.

## Use Cases

| From | To | Transfer Method | Example |
|---|---|---|---|
| Claude Code | ClawRig/OpenClaw | ClawRig API | "Continue this in chat" |
| Claude Code (PC1) | Claude Code (PC2) | Git sync / shared store | "Pick up on my desktop" |
| Person A | Person B | Git / shared store | "Can you finish this?" |
| Claude Code | Autonomous agent | Beads issue + handoff | "Agent, handle this" |
| Session | Same session later | Local store | "I'll continue tomorrow" |

## Handoff Envelope Schema

```json
{
  "$schema": "relay/handoff-v1",
  "handoff_id": "hf-a1b2c3d4",
  "version": 1,
  "created_at": "2026-02-22T10:30:00Z",
  "expires_at": "2026-03-01T10:30:00Z",
  "status": "pending",

  "from": {
    "tool": "claude-code",
    "user": "ivintik",
    "machine": "macbook-pro",
    "session_id": "abc123",
    "working_directory": "/Users/ivintik/dev/digital/web-sdk"
  },

  "project": {
    "slug": "digital-web-sdk",
    "name": "Digital Personalization Web SDK",
    "repo_url": "https://git.angara.cloud/digital/web-sdk",
    "repo_type": "gitlab",
    "branch": "feature/jwt-refresh",
    "commit": "a1b2c3d4e5f6",
    "has_uncommitted_changes": true
  },

  "context": {
    "summary": "Working on JWT token refresh bug. Root cause: refresh token isn't rotated on use, causing replay attacks after expiry.",

    "objective": "Implement refresh token rotation in auth-service.ts",

    "files_touched": [
      {
        "path": "src/auth-service.ts",
        "action": "modified",
        "summary": "Added rotation logic in refreshToken() method"
      },
      {
        "path": "src/token-store.ts",
        "action": "modified",
        "summary": "Added invalidateToken() for old refresh tokens"
      }
    ],

    "decisions_made": [
      {
        "decision": "Use refresh token rotation instead of sliding expiry",
        "rationale": "Rotation provides better security against token theft",
        "alternatives_considered": ["Sliding window expiry", "Short-lived tokens only"]
      }
    ],

    "issues_active": [
      {
        "source": "beads",
        "id": "bd-x1y2",
        "title": "Implement token rotation",
        "status": "in_progress"
      },
      {
        "source": "gitlab",
        "id": "42",
        "url": "https://git.example.com/project/-/issues/42",
        "title": "JWT refresh broken after 24h",
        "status": "open"
      }
    ],

    "next_steps": [
      "Complete refreshToken() implementation in auth-service.ts:142",
      "Add unit tests in auth-service.test.ts",
      "Test with expired tokens (use mock clock)",
      "Update API docs for new refresh behavior"
    ],

    "blockers": [],

    "notes": "Token store uses IndexedDB in browser, AsyncStorage in React Native. Both paths need testing."
  },

  "target": {
    "type": "person",
    "identifier": "colleague@email.com",
    "tool_preference": "claude-code",
    "instructions": "Focus on the test coverage, I've done the implementation."
  },

  "artifacts": {
    "git_diff": "base64-encoded unified diff of uncommitted changes",
    "beads_export": "JSONL export of related beads issues",
    "files_snapshot": {}
  }
}
```

## Handoff Flow

### Creating a Handoff

```
/relay:handoff
/relay:handoff --to clawrig
/relay:handoff --to person:colleague@email.com
/relay:handoff --to agent:task-agent
/relay:handoff --save-only                     # Don't transfer, just save
```

**Steps:**

1. **Gather Context**
   - Read atlas project info for current cwd
   - Get git status (branch, commit, uncommitted changes)
   - Get active beads issues (`bd list --status in_progress`)
   - Ask Claude to summarize current work (objective, decisions, next steps)

2. **Build Envelope**
   - Populate all fields from gathered context
   - Generate `handoff_id` (hash-based, like beads)
   - Capture git diff if uncommitted changes exist
   - Export related beads issues to JSONL

3. **Transfer**
   - **ClawRig**: POST envelope to ClawRig API → spawns session
   - **Local**: Save to `~/.claude/relay/handoffs/`
   - **Git sync**: Commit envelope to shared handoffs repo
   - **Person**: Save locally + print instructions for recipient

4. **Confirm**
   - Print handoff ID and summary
   - If beads active: update beads issue notes with handoff reference

### Picking Up a Handoff

```
/relay:pickup
/relay:pickup hf-a1b2c3d4
/relay:pickup --list                           # Show all pending handoffs
```

**Steps:**

1. **Discover**
   - List pending handoffs from `~/.claude/relay/handoffs/`
   - If git sync configured: pull latest handoffs
   - Show summary of each (project, summary, from, created_at)

2. **Select** (if multiple)
   - User picks which handoff to resume

3. **Restore Context**
   - Print project info (from envelope)
   - Print summary, decisions, next steps
   - If git diff included: offer to apply it
   - If beads export included: import issues (`bd import`)
   - If different project: suggest `cd` to project path

4. **Mark as Picked Up**
   - Update envelope status: `pending` → `picked_up`
   - Record who picked it up and when

## Handoff Targets

### ClawRig Target

```json
{
  "type": "session",
  "identifier": "clawrig",
  "tool_preference": "openclaw"
}
```

Transfer: POST to `@clawrig/claudeman-api` endpoint.
ClawRig's `claudeman-skill` creates a new Claude Code session with handoff context injected.

### Agent Target

```json
{
  "type": "agent",
  "identifier": "task-agent",
  "tool_preference": "claude-code"
}
```

Transfer:
1. Create beads issue from handoff (if not exists)
2. Set issue status to `open` with handoff context in notes
3. Agent discovers via `bd ready` on next session

### Person Target

```json
{
  "type": "person",
  "identifier": "colleague@email.com",
  "tool_preference": "claude-code"
}
```

Transfer:
1. Save envelope to shared location (git repo, file share)
2. Optionally notify via configured channel (future: slack, email)
3. Recipient runs `/relay:pickup` to resume

### Self (Cross-Machine)

```json
{
  "type": "self",
  "identifier": "ivintik",
  "tool_preference": "claude-code"
}
```

Transfer:
1. Push branch with changes
2. Save envelope to git-synced handoffs repo
3. On other machine: pull, `/relay:pickup`

## Handoff Lifecycle

```
pending → picked_up → completed
                   → expired (after expires_at)
                   → cancelled (manual)
```

Expired handoffs are auto-archived on next `/relay:pickup --list`.

## Handoff Storage Sync Options

### Local Only (Default)

```yaml
# ~/.claude/relay/config.yaml
handoff_sync: local
```

Handoffs stored in `~/.claude/relay/handoffs/`. No sync. Good for single-machine use.

### Git Sync

```yaml
handoff_sync: git
handoff_repo: https://github.com/user/handoffs.git
handoff_branch: main
```

Handoffs committed and pushed to a shared repo. Recipients pull to discover.

### None (Inline)

```yaml
handoff_sync: none
```

Handoffs printed to stdout as JSON. User copies/pastes or pipes to another tool.
