# Messaging Protocol

Cross-project messaging uses **mcp_agent_mail** — an HTTP server with MCP tools for agent communication.

## When to Use

| Scenario | Use |
|----------|-----|
| Save work context on current branch | Handoff (beads) |
| Notify another project about something | Message (mail) |
| Coordinate between agents in different repos | Message (mail) |
| Delegate work within the same repo | Handoff (beads) |

## Key MCP Tools

| Tool | Purpose |
|------|---------|
| `send_message` | Send a message to an agent in a project |
| `fetch_inbox` | Read incoming messages |
| `acknowledge_message` | Mark message as read/handled |
| `ensure_project` | Register a project with the mail server |
| `register_agent` | Register an agent identity |
| `macro_start_session` | Bundled startup (register + fetch inbox) |

## Message Format

Messages use GitHub-Flavored Markdown. Threading via `thread_id`:

```
send_message(
  to="agent-name",
  project_key="/path/to/project",
  subject="Status update: JWT implementation",
  body="Completed token rotation. Tests passing. Ready for integration.",
  thread_id="feature-jwt-refresh"
)
```

## Server Configuration

Default: `http://localhost:8765`. Override with `AGENT_MAIL_URL` env var.

Atlas auto-registers projects with the mail server at session start (idempotent). No manual setup needed if atlas is installed.

## Requirements

mcp_agent_mail must be running for messaging features. Installed by toolkit (`/toolkit:toolkit-setup`).

If the server is not running, skills should attempt to start it via the toolkit's `start_mail_server()` or report the problem clearly rather than silently degrading.

## Extension Point

The current implementation uses mcp_agent_mail as the messaging backend. The messaging interface (send, fetch, acknowledge) is designed to be backend-agnostic. Future alternative backends (e.g., hosted service, different MCP server) can be swapped by:

1. Replacing the MCP server registration in toolkit
2. Updating the `AGENT_MAIL_URL` env var
3. Ensuring the new backend exposes the same MCP tool names (`send_message`, `fetch_inbox`, `acknowledge_message`)
