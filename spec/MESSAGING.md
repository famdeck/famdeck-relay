# Relay — Cross-Project Messaging

## Overview

Cross-project messaging uses **mcp_agent_mail**, an HTTP server that provides agent identities, inboxes, threaded messages, and advisory file reservations via MCP tools.

Relay does not own or modify mcp_agent_mail. It uses the server as-is and integrates it into the atlas/relay ecosystem.

## Architecture

```
mcp_agent_mail (HTTP :8765)
├── Projects (keyed by absolute path)
├── Agents (named identities per project)
├── Messages (GFM markdown, threaded)
├── File Reservations (advisory leases)
└── Storage: Git repo + SQLite FTS5
```

## Integration Points

### Atlas Session-Start Hook

Atlas auto-registers projects with mcp_agent_mail at session start:

1. Health check: `GET /health`
2. Ensure project: `POST /projects/ensure` with `project_key` (absolute path)
3. Register agent: `POST /agents/register` with username as agent name
4. Fetch inbox count for context line

This is idempotent — safe to run every session. If the server isn't running, all steps are skipped silently.

### Atlas Provider Enrichment

The `relay-mail` provider (type: `mcp_query`) queries the mail server for inbox count:

```yaml
# ~/.claude/atlas/providers/relay-mail.yaml
name: relay-mail
type: mcp_query
endpoint: http://localhost:8765
resource: inbox/{agent}?project_key={project_path}&limit=0
field_name: pending_mail
```

When atlas enriches a project, it adds `pending_mail: N` to the project data. Returns `null` if the server is unavailable.

## Messaging vs Handoffs

| Aspect | Handoffs (beads) | Messages (mcp_agent_mail) |
|--------|-------------------|---------------------------|
| Scope | Within-project | Cross-project |
| Storage | `.beads/` (git) | `.agent_mail/` (git + SQLite) |
| Identity | beads issue with labels | Agent name + project |
| Threading | N/A (single issue) | `thread_id` for conversations |
| Lifecycle | open → in_progress → closed | send → fetch → acknowledge |
| Branch-scoped | Yes | No (project-scoped) |

## Use Cases

### Agent Coordination

Multiple agents working on related repos can message each other:

```
# Agent A in web-sdk finishes API change
send_message(to="agent-b", project_key="/path/to/mobile-sdk",
  subject="API change: new auth endpoint",
  body="Changed /auth/refresh to use rotation. Mobile SDK needs update.",
  thread_id="auth-refresh-v2")

# Agent B in mobile-sdk picks it up
fetch_inbox(project_key="/path/to/mobile-sdk", agent_name="agent-b")
```

### Status Broadcasts

Notify all agents in a project about important changes:

```
send_message(to="all", project_key="/path/to/project",
  subject="Breaking: DB schema migration",
  body="Running migration #42. Services will restart.")
```

### File Coordination

Reserve files to avoid conflicts between concurrent agents:

```
file_reservation_paths(
  project_key="/path/to/project",
  agent_name="agent-a",
  paths=["src/auth/**"],
  ttl_seconds=3600,
  exclusive=true
)
```

## Server Lifecycle

mcp_agent_mail is a standalone HTTP server. Relay does not manage its lifecycle.

- **Start**: User runs `am` (alias installed by mcp_agent_mail installer)
- **Stop**: User stops the server process
- **Health**: `GET http://localhost:8765/health`

All relay/atlas features degrade gracefully when the server is unavailable.
