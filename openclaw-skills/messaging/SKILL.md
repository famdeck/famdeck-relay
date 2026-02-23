---
name: messaging
description: "Send and receive cross-project messages via mcp_agent_mail. Use for notifying other projects, coordinating between agents, or checking incoming messages."
metadata: {"openclaw":{"emoji":"💬"}}
---

# Relay Messaging

Cross-project messaging using mcp_agent_mail MCP tools.

## When to Use

| Scenario | Use This Skill |
|----------|---------------|
| Notify another project about something | Yes |
| Coordinate between agents in different repos | Yes |
| Check incoming messages from other agents | Yes |
| Save work context on current branch | No — use `/handoff` instead |
| Delegate work within the same repo | No — use `/handoff` instead |

## Prerequisites

mcp_agent_mail must be running (default: `http://localhost:8765`). Check health:

```bash
curl -sf http://localhost:8765/health/liveness
```

If unavailable, report the error clearly. Do not silently degrade.

## Parse Arguments

Parse `$ARGUMENTS` for subcommand:

- **No args or `inbox`**: Fetch and display inbox
- **`send <to> <subject>`**: Send a message
- **`ack <message_id>`**: Acknowledge a message
- **`thread <thread_id>`**: View a thread
- **`contacts`**: List known contacts
- **`start`**: Initialize session (register + fetch)

## Subcommand: inbox (default)

Fetch incoming messages using the `fetch_inbox` MCP tool.

Display as:
```
Inbox (N messages):
  ID          From            Subject                     Thread          Time
  msg-abc     atlas-agent     Status: JWT done            feature-jwt     2m ago
  msg-def     relay-agent     Handoff: cleanup needed     handoff-123     1h ago
```

## Subcommand: send

Send a message using the `send_message` MCP tool:

```
send_message(
  to="<agent-name>",
  project_key="<path/to/project>",
  subject="<subject>",
  body="<body>",
  thread_id="<optional-thread-id>"
)
```

Messages use GitHub-Flavored Markdown for body content. Threading via `thread_id` groups related messages.

If `--thread <id>` provided, use it. Otherwise generate from context (e.g., `feature-jwt-refresh`).

## Subcommand: ack

Mark a message as read/handled:

```
acknowledge_message(message_id="<id>")
```

## Subcommand: thread

View all messages in a thread:

```
fetch_topic(thread_id="<id>")
```

## Subcommand: contacts

List known agent contacts:

```
list_contacts()
```

## Subcommand: start

Initialize a messaging session — registers the current agent and fetches inbox in one call:

```
macro_start_session(
  agent_name="<agent-name>",
  project_key="<project-path>"
)
```

Atlas auto-registers projects with the mail server at session start (idempotent).

## MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `send_message` | Send a message to an agent/project |
| `fetch_inbox` | Read incoming messages |
| `acknowledge_message` | Mark message as read/handled |
| `ensure_project` | Register a project with the mail server |
| `register_agent` | Register an agent identity |
| `macro_start_session` | Bundled startup (register + fetch inbox) |
| `fetch_topic` | Fetch all messages in a thread |
| `list_contacts` | List known agent contacts |
| `search_messages` | Search messages by query |

All tools are accessed via the `mcp__agent-mail__` prefix. Use ToolSearch to load them before calling (e.g., `ToolSearch("+agent-mail send_message")`).

## Server Configuration

Default: `http://localhost:8765`. Override with `AGENT_MAIL_URL` env var.

## Rules

- Always check mail server health before operations
- Use thread_id for related messages to maintain conversation context
- For within-project context transfer, use handoffs (beads) instead of messages
- Report mail server errors clearly — never silently skip messaging
