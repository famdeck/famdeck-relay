---
name: messaging
description: "Send cross-project messages and check inbox via Agent Mail — coordinate between agents, send notifications, and read messages. Use when an agent needs to notify another project, check for incoming messages, or acknowledge messages. Do NOT use for within-project context transfer (use handoff) or issue tracking (use relay)."
metadata: {"openclaw":{"emoji":"💬"}}
allowed-tools: "Bash,ToolSearch,mcp__agent-mail__send_message,mcp__agent-mail__fetch_inbox,mcp__agent-mail__acknowledge_message,mcp__agent-mail__ensure_project,mcp__agent-mail__register_agent,mcp__agent-mail__macro_start_session,mcp__agent-mail__fetch_topic,mcp__agent-mail__list_contacts,mcp__agent-mail__search_messages"
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
