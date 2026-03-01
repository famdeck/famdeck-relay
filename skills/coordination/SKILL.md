---
name: coordination
description: "Multi-agent coordination protocol using Agent Mail — session bootstrap, file reservations, threaded messaging, and Beads integration. Use when multiple agents work on the same project, when handing off file ownership, or when you need to communicate with other agents."
---

# Agent Coordination Protocol

Coordinate with other agents working on the same project using Agent Mail's MCP tools.

## When To Use This

- Multiple agents are working on the same codebase (via Codeman, tmux, worktrees)
- You need to edit files that another agent might also be editing
- You want to announce what you're working on so others don't conflict
- You received a message from another agent and need to respond
- You're starting work on a Beads issue and want to signal intent

## Session Start

At the beginning of work, bootstrap your session:

```
macro_start_session(
  human_key="<absolute path to project>",
  program="claude-code",
  model="<your model>",
  task_description="<what you plan to do>"
)
```

This single call: ensures the project exists in Agent Mail, registers your identity (you get a memorable name like "GreenCastle"), and fetches your inbox.

**Check your inbox first.** Other agents may have left messages about files they're editing or work they need you to avoid.

## Before Editing Files

Reserve files to signal your intent:

```
file_reservation_paths(
  project_key="<absolute path>",
  agent_name="<your name>",
  paths=["src/auth/**/*.ts", "src/middleware/auth.ts"],
  ttl_seconds=3600,
  exclusive=true,
  reason="bd-123"
)
```

- Use glob patterns for directories (`src/auth/**`)
- Use `exclusive=true` to signal "I'm actively editing these"
- Set `reason` to the Beads issue ID if applicable
- Check the `conflicts` field in the response — if another agent has reservations, coordinate first

## Announce Your Work

Send a message so other agents know what you're doing:

```
send_message(
  project_key="<absolute path>",
  sender_name="<your name>",
  to=["*"],
  subject="[bd-123] Starting auth refactor",
  body_md="Reserving src/auth/**. Will update session handling and add JWT validation.",
  thread_id="bd-123"
)
```

- Use `to=["*"]` to broadcast to all agents in the project
- Use `thread_id` matching the Beads issue ID (`bd-123`) to keep messages organized
- Prefix subject with `[bd-123]` for easy scanning

## Check Inbox Periodically

Fetch messages from other agents:

```
fetch_inbox(
  project_key="<absolute path>",
  agent_name="<your name>",
  limit=10,
  include_bodies=true
)
```

**Act on urgent messages immediately.** If another agent reports a conflict or asks you to hold off on certain files, respect that.

## Release When Done

When you finish editing files, release your reservations:

```
release_file_reservations(
  project_key="<absolute path>",
  agent_name="<your name>"
)
```

Then announce completion:

```
send_message(
  project_key="<absolute path>",
  sender_name="<your name>",
  to=["*"],
  subject="[bd-123] Completed auth refactor",
  body_md="Done. Released all file reservations. Changes in commit abc123.",
  thread_id="bd-123"
)
```

## Beads + Agent Mail Workflow

When working on a Beads issue, align identifiers across all tools:

1. **Pick work:** `bd ready` to find unblocked tasks
2. **Start session:** `macro_start_session(...)` to register and check inbox
3. **Reserve files:** `file_reservation_paths(..., reason="bd-123")`
4. **Announce:** `send_message(..., thread_id="bd-123", subject="[bd-123] Starting...")`
5. **Work** on the issue, replying in the thread with progress updates
6. **Complete:** `bd close bd-123`, then `release_file_reservations(...)`, then final message

Use the Beads issue ID (`bd-123`) as:
- Agent Mail `thread_id`
- Message subject prefix `[bd-123]`
- File reservation `reason`
- Git commit message reference

## Handling Conflicts

If `file_reservation_paths` returns conflicts:

1. **Read the conflict details** — who has the reservation and why
2. **Check their messages** — search for their thread: `search_messages(..., query="bd-###")`
3. **Coordinate** — send them a message asking to share or wait
4. **Work on something else** if they need more time — pick another Beads issue

## Pre-Commit Guard

If the project has the Agent Mail pre-commit guard installed, your commits will be blocked if they touch files exclusively reserved by another agent. This is a safety net — but always check reservations proactively rather than relying on the guard.

Bypass in emergencies: `AGENT_MAIL_BYPASS=1 git commit ...`

## BMAD Persona Distribution

In multi-agent setups with BMAD-METHOD projects, different agents can take different BMAD roles:

| Agent Role | BMAD Persona | Typical Commands |
|------------|-------------|------------------|
| PM agent | Product Manager | `/bmad-bmm-create-prd`, `/bmad-bmm-create-next-story` |
| Architect agent | Architect | `/bmad-bmm-create-architecture`, `/bmad-bmm-create-epics-and-stories` |
| Dev agent(s) | Developer | `/bmad-bmm-dev-story`, `/bmad-bmm-code-review` |

**Coordination rule:** Only one agent should write to `_bmad-output/` at a time. Use file reservations to enforce this:

```
file_reservation_paths(
  project_key="<absolute path>",
  agent_name="<your name>",
  paths=["_bmad-output/**"],
  ttl_seconds=3600,
  exclusive=true,
  reason="BMAD planning: creating PRD"
)
```

Release the reservation when you finish your planning step so the next persona can proceed. Announce in the Agent Mail thread which BMAD artifact you produced, so downstream agents (e.g., Dev agents waiting for stories) know when to start.
