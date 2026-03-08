---
name: messaging
description: Send cross-project messages and check inbox via Agent Mail — coordinate between agents, send notifications, and read messages. Use when an agent needs to notify another project, check for incoming messages, acknowledge messages, or start a coordination session. Do NOT use for within-project context transfer (use relay:context-gatherer), issue tracking (use relay:issue), or file conflict resolution (use relay:coordinator).
allowed-tools: "ToolSearch"
---

# Relay Messaging

Cross-project agent messaging via Agent Mail MCP tools.

## Quick Reference

| Subcommand | MCP Tool | Action |
|---|---|---|
| (none) / `inbox` | `mcp__agent-mail__fetch_inbox` | List messages as table: ID, From, Subject, Thread, Time |
| `send <to> <subject>` | `mcp__agent-mail__send_message` | Send or broadcast a message |
| `ack <message_id>` | `mcp__agent-mail__acknowledge_message` | Acknowledge a message |
| `thread <thread_id>` | `mcp__agent-mail__fetch_topic` | Fetch full thread |
| `contacts` | `mcp__agent-mail__list_contacts` | List known agents |
| `search <query>` | `mcp__agent-mail__search_messages` | Search messages |
| `start` | `mcp__agent-mail__macro_start_session` | Register identity + fetch inbox in one call |

Load tools via ToolSearch: `+agent-mail <tool_name>`

## Finding the Right Project

Agent Mail organizes everything by project key. Getting this wrong means checking the wrong inbox or sending to the wrong place.

Use `fetch_summary` with the project directory path to discover the correct project key and any active agents:

```
fetch_summary(human_key="/path/to/project")
```

If the project path isn't obvious from context, check the Atlas registry (`~/.claude/atlas/registry.yaml`) to find registered project paths.

## Starting a Session

For most tasks, start with `macro_start_session` — it handles project setup, agent registration, and inbox fetch in one call. Use this instead of manually chaining ensure_project + register_agent + fetch_inbox.

## Checking Inbox

For coordination tasks (announcing work, checking for conflicts), always fetch the inbox before sending. Existing messages may already address what you're about to send — reading first avoids duplicate notifications and lets you reply to threads rather than starting new ones.

## Sending Messages

Use `broadcast=true` to reach all registered agents in a project without specifying names. If `count: 0` is returned, nobody is currently registered — note this in your response and suggest the recipient registers via `macro_start_session`.

Don't create placeholder agents in a target project just to have a recipient. If nobody is registered and you can't broadcast, report that clearly and offer to create a relay issue instead.
