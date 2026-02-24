# Relay — Development Guide

## Architecture

```
relay/
├── cli/                          # Python CLI (the "engine")
│   ├── main.py                   # Entry point, argparse, subcommands
│   ├── config.py                 # Config reading/writing, atlas integration
│   ├── routing.py                # Routing rule evaluation
│   └── adapters.py               # Adapter dispatch (gh/bd CLI, MCP instructions)
├── bin/relay                     # Global entry script (symlink to ~/.local/bin/relay)
├── skills/                       # Thin skill wrappers (the "coach")
│   ├── issue/SKILL.md
│   ├── trackers/SKILL.md
│   ├── status/SKILL.md
│   ├── handoff/SKILL.md
│   └── pickup/SKILL.md
├── openclaw-skills/              # OpenClaw format skills (same content)
├── agents/router.md              # Auto-routing agent
├── hooks/hooks.json              # SessionStart + PreCompact hooks
├── hooks/scripts/                # Hook scripts
├── knowledge/                    # Reference docs (kept for spec)
└── spec/                         # Design specifications
```

## Key Principle: CLI is Engine, Skill is Coach

Skills are thin (~30 lines) wrappers that call `relay <command>`.
The CLI handles all deterministic logic: config parsing, routing, adapter dispatch.
Skills only handle MCP tool calls (GitLab/Jira) and user interaction.

## CLI Commands

```bash
relay prime                       # Session context (run by hooks)
relay issue "title" [flags]       # Create and route an issue
relay route "title" [flags]       # Dry-run routing
relay trackers [show|init|add|remove]
relay status [--all]
relay handoff [--summary "..."]
relay pickup [issue_id|--list]
```

Output is JSON by default (`--format text` for human-readable).

## Hooks

- **SessionStart**: Registers atlas providers + runs `relay prime`
- **PreCompact**: Runs `relay prime` (context survives compaction)

## Adapter Model

| Tracker | Method | Tool |
|---------|--------|------|
| GitHub | CLI (direct) | `gh` |
| Beads | CLI (direct) | `bd` |
| GitLab | MCP (via Claude) | `mcp__plugin_ds_gitlab__*` |
| Jira | MCP (via Claude) | `mcp__plugin_ds_atlassian__jira_*` |

CLI-based adapters execute directly and return results.
MCP-based adapters return `{"status": "needs_mcp", "tool": "...", "params": {...}}` for Claude to execute.

## Dependencies

| Dependency | Required? | Check |
|---|---|---|
| Python 3.8+ | Yes | `python3 --version` |
| PyYAML | Yes | `python3 -c "import yaml"` |
| Atlas plugin | Recommended | `~/.claude/atlas/registry.yaml` |
| Beads CLI | For handoffs | `which bd` |
| GitHub CLI | For GitHub tracker | `which gh` |
| GitLab MCP | For GitLab tracker | ToolSearch |
| Jira MCP | For Jira tracker | ToolSearch |

## Config Schema

Per-project: `<project-root>/.claude/relay.yaml`

```yaml
issue_trackers:
  - name: <string>          # Unique name
    type: github|gitlab|jira|beads
    default: true            # Fallback tracker
    repo: "org/repo"         # GitHub
    project_id: "group/proj" # GitLab
    project_key: "PROJ"      # Jira
    scope: local             # Beads
    labels: [default-labels]
    routing_rules:
      - match: { type: bug, priority: [critical, high], source: agent }
        action: { default: true, labels: [urgent], assignee: "@user" }
```
