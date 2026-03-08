---
name: messaging
description: "Cross-project agent messaging via mcp_agent_mail. Send notifications, coordinate between agents, check inbox. Trigger phrases — 'send a message', 'check messages', 'notify another project', 'agent inbox', 'message the other agent'. For within-project context transfer use /handoff instead."
metadata: {"openclaw":{"emoji":"💬"}}
---

# Relay Messaging

Cross-project messaging using mcp_agent_mail MCP tools.

## Prerequisites

mcp_agent_mail must be running (default: `http://localhost:8765`). Check: `curl -sf http://localhost:8765/health/liveness`. Report errors clearly if unavailable.

## Subcommands

Parse `$ARGUMENTS` for:

| Subcommand | Action |
|---|---|
| (none) / `inbox` | `fetch_inbox()` — display as table with ID, From, Subject, Thread, Time |
| `send <to> <subject>` | `send_message(to, project_key, subject, body, thread_id?)` |
| `ack <message_id>` | `acknowledge_message(message_id)` |
| `thread <thread_id>` | `fetch_topic(thread_id)` |
| `contacts` | `list_contacts()` |
| `start` | `macro_start_session(agent_name, project_key)` — register + fetch inbox |

## MCP tools

All accessed via `mcp__agent-mail__` prefix. Load via ToolSearch (e.g., `+agent-mail send_message`).

Available: `send_message`, `fetch_inbox`, `acknowledge_message`, `ensure_project`, `register_agent`, `macro_start_session`, `fetch_topic`, `list_contacts`, `search_messages`.

## Rules

- Check health before operations
- Use `thread_id` to group related messages
- Within-project context transfer: use handoffs, not messages
- Never silently skip on errors
