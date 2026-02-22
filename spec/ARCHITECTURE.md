# Relay — Issue Routing & Handoff

## Overview

Relay is a Claude Code plugin that provides **cross-project issue routing** and **work handoff** between sessions, tools, and people. It uses Atlas for project resolution (slug → path) and maintains its own per-project issue tracker configuration in each project's repository.

## Core Responsibilities

1. **Issue Tracker Config** — Own and manage `.claude/relay.yaml` in each project repo
2. **Issue Routing** — Route issues to the right tracker based on per-project config
3. **Handoff Protocol** — Serialize work context and transfer between sessions/tools/people
4. **Pickup** — Resume handed-off work with full context restoration
5. **Cross-Project Dashboard** — Unified view of issues across all projects and trackers

## Key Architectural Decision

**Relay owns issue tracker configuration.** Each project repo has a `.claude/relay.yaml` that defines which trackers the project uses and how issues are routed. This config is version-controlled, team-shared, and travels with the repo.

Atlas tells relay "this is project X at path Y." Relay reads its own config from that path to know where issues go.

## Plugin Structure

```
relay/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── issue/SKILL.md                # /relay:issue — create & route issues
│   ├── handoff/SKILL.md              # /relay:handoff — serialize & transfer work
│   ├── pickup/SKILL.md               # /relay:pickup — resume handed-off work
│   ├── status/SKILL.md               # /relay:status — cross-project issue dashboard
│   └── trackers/SKILL.md             # /relay:trackers — manage tracker config
├── agents/
│   └── router.md                     # Auto-routes issues based on project config
├── knowledge/
│   ├── routing-rules.md              # Issue routing logic & decision tree
│   ├── handoff-protocol.md           # Handoff envelope specification
│   ├── tracker-adapters.md           # GitHub/GitLab/Jira adapter patterns
│   ├── relay-config-schema.md        # .claude/relay.yaml schema
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

## Per-Project Config (`.claude/relay.yaml`)

Lives in each project's repo — version-controlled, team-shared:

```yaml
# <project-root>/.claude/relay.yaml

issue_trackers:

  - name: gitlab
    type: gitlab
    project_id: "digital/web-sdk"
    default: true
    labels: [sdk, web]
    routing_rules:
      - match: { type: bug, priority: [critical, high] }
        action: { labels: [urgent], assignee: "@team-lead" }
      - match: { type: feature }
        action: { labels: [enhancement] }

  - name: beads
    type: beads
    scope: local
    routing_rules:
      - match: { source: agent }
        action: { default: true }
      - match: { type: task }
        action: { default: true }
```

## Design Principles

### 1. Route, Don't Replace

Relay routes issues to existing trackers — it doesn't become yet another tracker. Beads handles local/agent work. GitLab/GitHub/Jira handle team work. Relay is the switchboard.

### 2. Config Travels With the Repo

Issue tracker config is in `.claude/relay.yaml` inside the project repo. Clone a repo → relay knows where its issues go. No central config to keep in sync.

### 3. Adapter Pattern

Each tracker type (github, gitlab, jira, beads) has an adapter that maps relay's generic interface to tracker-specific MCP tools. Adding a new tracker = adding a new adapter definition in knowledge.

### 4. Graceful Degradation

- If atlas isn't installed → relay resolves project from cwd manually
- If `.claude/relay.yaml` is missing → relay asks where to create the issue
- If a tracker MCP isn't installed → relay tells you which one to install
- If beads isn't installed → relay skips local cross-referencing
- If clawrig isn't available → handoff stores locally

### 5. Envelope-Based Handoff

Handoffs are self-contained JSON envelopes with everything needed to resume work: project context, git state, active issues, decisions, next steps.

### 6. MCP Discovery, Not Installation

Relay discovers which MCP tools are available at runtime. It never installs MCP servers — it suggests installation via toolkit when a needed adapter is missing.

## Dependencies

| Dependency | Type | Required? | Purpose |
|---|---|---|---|
| Atlas | Plugin | Recommended | Project resolution (slug → path) |
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
└── config.yaml                       # Global relay preferences
    # handoff_sync: git | local | none
    # handoff_repo: https://github.com/user/handoffs.git
    # default_handoff_target: clawrig | local
```

Note: No issue tracker config here. That lives per-project in `.claude/relay.yaml`.
