# Relay — Issue Routing, Handoff & Messaging

## Overview

Relay is a Claude Code plugin that provides **cross-project issue routing**, **work handoffs** (via beads), and **cross-project messaging** (via mcp_agent_mail). It uses Atlas for project resolution and maintains per-project issue tracker configuration.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    mcp_agent_mail (HTTP server)               │
│  Cross-project messaging, agent identity, file reservations   │
│  Storage: Git (.agent_mail/) + SQLite                         │
└────────────────────┬─────────────────────────────────────────┘
                     │ MCP tools (send_message, fetch_inbox, ...)
                     │
┌────────────────────┼─────────────────────────────────────────┐
│  Atlas             │              Relay                       │
│  • Project registry│              • Issue routing (3 skills)  │
│  • Auto-registers  │              • Handoffs via beads        │
│    projects w/mail │              • /relay:handoff → bd create│
│  • Enriches with   │              • /relay:pickup → bd list   │
│    mail inbox count│              • Cross-project messaging   │
└────────────────────┴─────────────────────────────────────────┘
                     │
┌────────────────────┼─────────────────────────────────────────┐
│                  Beads (per-project)                          │
│  • Issues (.beads/)                                           │
│  • Handoffs stored as beads with relay:handoff label          │
│  • Committed to git, branch-scoped                            │
│  • Git hooks handle branch switching (post-checkout import)   │
└──────────────────────────────────────────────────────────────┘
```

## Core Responsibilities

1. **Issue Tracker Config** — Own and manage `.claude/relay.yaml` in each project repo
2. **Issue Routing** — Route issues to the right tracker based on per-project config
3. **Handoffs** — Capture work context as beads issues (`relay:handoff` label)
4. **Pickup** — Resume handed-off work with full context restoration
5. **Cross-Project Messaging** — Send/receive messages via mcp_agent_mail
6. **Cross-Project Dashboard** — Unified view of issues across all projects and trackers

## Plugin Structure

```
relay/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── issue/SKILL.md                # /relay:issue — create & route issues
│   ├── handoff/SKILL.md              # /relay:handoff — create beads handoff
│   ├── pickup/SKILL.md               # /relay:pickup — resume from handoff
│   ├── status/SKILL.md               # /relay:status — cross-project dashboard
│   └── trackers/SKILL.md             # /relay:trackers — manage tracker config
├── agents/
│   └── router.md                     # Auto-routes issues based on project config
├── knowledge/
│   ├── routing-rules.md              # Issue routing logic & decision tree
│   ├── handoff-protocol.md           # Handoff as beads issue — schema & lifecycle
│   ├── messaging-protocol.md         # Cross-project messaging via mcp_agent_mail
│   ├── tracker-adapters.md           # GitHub/GitLab/Jira adapter patterns
│   ├── relay-config-schema.md        # .claude/relay.yaml schema
│   └── beads-integration.md          # How relay extends beads
├── hooks/
│   ├── hooks.json
│   └── scripts/
│       └── register-provider.py      # SessionStart: register with Atlas
├── spec/
│   ├── ARCHITECTURE.md               # This file
│   ├── ROUTING.md
│   ├── HANDOFF.md                    # Handoff as beads issues
│   ├── MESSAGING.md                  # Cross-project messaging
│   ├── ADAPTERS.md
│   └── SKILLS.md
└── README.md
```

## Two Communication Models

### Handoffs (Within-Project)

Handoffs are **beads issues** with the `relay:handoff` label. They capture work context (objective, decisions, next steps, files touched) as structured markdown in the issue description.

- **Storage**: `.beads/` directory, committed to git
- **Scope**: Branch-scoped — visible on the branch where created
- **Discovery**: `bd list --label relay:handoff --status open`
- **Lifecycle**: open → in_progress → closed (standard beads)

Use for: switching context, saving progress, delegating within the same repo.

### Messages (Cross-Project)

Cross-project communication uses **mcp_agent_mail** — an HTTP server with MCP tools for sending/receiving messages between agents and projects.

- **Storage**: Git (.agent_mail/) + SQLite per project
- **Scope**: Cross-project, agent-to-agent
- **Discovery**: `fetch_inbox` MCP tool
- **Threading**: Messages organized by `thread_id`

Use for: coordinating between repos, agent-to-agent communication, cross-project status updates.

## Per-Project Config (`.claude/relay.yaml`)

Lives in each project's repo — version-controlled, team-shared:

```yaml
issue_trackers:
  - name: gitlab
    type: gitlab
    project_id: "digital/web-sdk"
    default: true
    labels: [sdk, web]
    routing_rules:
      - match: { type: bug, priority: [critical, high] }
        action: { labels: [urgent], assignee: "@team-lead" }

  - name: beads
    type: beads
    scope: local
    routing_rules:
      - match: { source: agent }
        action: { default: true }
```

## Design Principles

### 1. Route, Don't Replace
Relay routes issues to existing trackers — it doesn't become yet another tracker.

### 2. Config Travels With the Repo
Issue tracker config is in `.claude/relay.yaml` inside the project repo.

### 3. Adapter Pattern
Each tracker type has an adapter that maps relay's generic interface to tracker-specific tools.

### 4. Graceful Degradation
- No atlas → relay resolves project from cwd
- No `.claude/relay.yaml` → relay asks where to create
- No mcp_agent_mail → cross-project messaging unavailable, handoffs still work
- No beads → handoffs unavailable, issue routing still works

### 5. Beads-Native Handoffs
Handoffs are beads issues, not separate JSON envelopes. They're committed, branch-scoped, and managed with standard beads lifecycle.

### 6. MCP Discovery, Not Installation
Relay discovers available MCP tools at runtime. It never installs servers.

## Dependencies

| Dependency | Type | Required? | Purpose |
|---|---|---|---|
| Atlas | Plugin | Recommended | Project resolution (slug → path) |
| Beads | Plugin + CLI | Required for handoffs | Handoff storage, local issues |
| mcp_agent_mail | HTTP Server | Optional | Cross-project messaging |
| GitLab MCP | MCP Server | Optional | GitLab issue operations |
| Jira MCP | MCP Server | Optional | Jira issue operations |
| `gh` CLI | System | Optional | GitHub issue operations |

## Integration with Atlas

Atlas auto-registers projects with mcp_agent_mail at session start (if server running). The relay plugin registers two Atlas providers:

1. **relay** — file-based, reads `.claude/relay.yaml` for `issue_trackers`
2. **relay-mail** — mcp_query, fetches inbox count as `pending_mail`
