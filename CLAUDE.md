# Relay — Development Guide

## Structure

```
relay/
├── .claude-plugin/plugin.json    # Plugin manifest
├── skills/                       # 5 skills (issue, handoff, pickup, status, trackers)
├── knowledge/                    # 6 knowledge files referenced by skills
├── agents/router.md              # Auto-routing agent
├── hooks/                        # SessionStart hook for Atlas provider registration
├── spec/                         # Design specifications (source of truth)
└── CLAUDE.md                     # This file
```

## Conventions

- Skills are structured prompts, not executable code. They instruct Claude on what steps to perform.
- Knowledge files contain reference data (schemas, mappings, decision trees) that skills reference with `Refer to knowledge/<file>.md`.
- The `spec/` directory is the design source of truth. When skill behavior conflicts with spec, spec wins.
- Per-project config lives at `<project-root>/.claude/relay.yaml`.

## Two Communication Models

| Model | Storage | Scope | Tool |
|-------|---------|-------|------|
| Handoffs | Beads issues (`.beads/`) | Within-project, branch-scoped | `bd` CLI |
| Messages | mcp_agent_mail | Cross-project | MCP tools |

## Key Dependencies

| Dependency | Required? | How to check |
|---|---|---|
| Atlas plugin | Recommended | `~/.claude/atlas/registry.yaml` exists |
| Beads CLI (`bd`) | Required for handoffs | `which bd` |
| mcp_agent_mail | Required | `curl -s http://localhost:8765/health/liveness` |
| GitHub CLI (`gh`) | Optional | `which gh` |
| GitLab MCP | Optional | ToolSearch for `mcp__plugin_ds_gitlab__*` |
| Jira MCP | Optional | ToolSearch for `mcp__plugin_ds_atlassian__jira_*` |

## File Budgets

| Component | Target Size |
|---|---|
| Knowledge files | 2-5 KB each |
| Skill files | 3-4 KB each |
| Agent | < 2 KB |
| Hook script | < 1 KB |

## Testing

Manual verification:
1. `/relay:trackers init` — creates valid `.claude/relay.yaml`
2. `/relay:trackers show` — displays config correctly
3. `/relay:issue "test"` — routes based on config
4. `/relay:handoff` — creates beads issue with `relay:handoff` label
5. `/relay:pickup --list` — lists handoff issues on current branch
6. `/relay:pickup` — restores context from a handoff
7. `/relay:status` — queries configured trackers
