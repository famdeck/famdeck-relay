# Relay — Issue Routing & Handoff

## Overview

Relay is a Claude Code plugin that provides **cross-project issue routing** and **work handoff** between sessions, tools, and people. It builds on top of Atlas (project registry) and integrates with Beads (local issue tracking), external issue trackers (GitHub, GitLab, Jira), and ClawRig/OpenClaw for orchestration.

## Core Responsibilities

1. **Issue Routing** — Create issues in the right tracker based on project configuration
2. **Handoff Protocol** — Serialize work context and transfer between sessions/tools/people
3. **Pickup** — Resume handed-off work with full context restoration
4. **Cross-Project Dashboard** — Unified view of issues across all projects and trackers

## Plugin Structure

```
relay/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── issue/SKILL.md                # /relay:issue — create & route issues
│   ├── handoff/SKILL.md              # /relay:handoff — serialize & transfer work
│   ├── pickup/SKILL.md               # /relay:pickup — resume handed-off work
│   └── status/SKILL.md               # /relay:status — cross-project issue dashboard
├── agents/
│   └── router.md                     # Auto-routes issues based on project config
├── knowledge/
│   ├── routing-rules.md              # Issue routing logic & decision tree
│   ├── handoff-protocol.md           # Handoff envelope specification
│   ├── tracker-adapters.md           # GitHub/GitLab/Jira adapter patterns
│   └── beads-integration.md          # How relay extends beads
├── hooks/
│   ├── hooks.json
│   └── scripts/
│       └── check-handoffs.sh         # SessionStart: check for pending handoffs
├── spec/
│   ├── ARCHITECTURE.md
│   ├── ROUTING.md
│   ├── HANDOFF.md
│   ├── ADAPTERS.md
│   └── SKILLS.md
└── README.md
```

## Design Principles

### 1. Route, Don't Replace

Relay routes issues to existing trackers — it doesn't become yet another tracker. Beads handles local/agent work. GitLab/GitHub/Jira handle team work. Relay is the switchboard.

### 2. Adapter Pattern

Each tracker type (github, gitlab, jira, beads) has an adapter that maps relay's generic interface to tracker-specific MCP tools. Adding a new tracker = adding a new adapter definition in knowledge.

### 3. Graceful Degradation

- If atlas isn't installed → relay asks for project info manually
- If a tracker MCP isn't installed → relay tells you which one to install and how
- If beads isn't installed → relay skips local issue cross-referencing
- If clawrig isn't available → handoff stores locally (manual transfer)

### 4. Envelope-Based Handoff

Handoffs are self-contained JSON envelopes. They include everything needed to resume work: project context, git state, active issues, decisions made, next steps. The envelope is the unit of transfer — it can travel via git, file share, API, or even copy-paste.

### 5. MCP Discovery, Not Installation

Relay discovers which MCP tools are available at runtime. It never installs MCP servers itself — it suggests installation via toolkit when a needed adapter is missing.

## Dependencies

| Dependency | Type | Required? | Purpose |
|---|---|---|---|
| Atlas | Plugin | Recommended | Project metadata, tracker configs |
| Beads | Plugin + CLI | Optional | Local issue tracking, cross-references |
| GitLab MCP | MCP Server | Optional | GitLab issue operations |
| Jira MCP | MCP Server | Optional | Jira issue operations |
| `gh` CLI | System | Optional | GitHub issue operations |
| ClawRig | External | Optional | Session orchestration for handoffs |

## Global Storage

```
~/.claude/relay/
├── handoffs/
│   ├── hf-a1b2c3d4.json             # Pending handoff envelopes
│   ├── hf-e5f6g7h8.json
│   └── archive/                      # Completed handoffs
│       └── hf-x9y0z1a2.json
└── config.yaml                       # Relay configuration
    # handoff_sync: git | local | none
    # handoff_repo: https://github.com/user/handoffs.git
    # default_handoff_target: clawrig | local
```
