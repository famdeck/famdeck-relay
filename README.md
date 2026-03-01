# Famdeck Relay

Issue routing, bidirectional sync, and work handoffs for [Claude Code](https://claude.ai/claude-code). Routes issues to GitHub, GitLab, Jira, or Beads based on per-project rules. All interaction through slash commands in Claude Code sessions or the `relay` CLI.

Part of the [Famdeck](https://github.com/famdeck/famdeck) autonomous development toolkit.

## Installation

### Via Marketplace (recommended)

```bash
claude plugin marketplace add iVintik/private-claude-marketplace
claude plugin install famdeck-relay@ivintik
```

Or install the full toolkit which includes Relay:

```bash
claude plugin install famdeck-toolkit@ivintik
# then in Claude Code:
/toolkit:toolkit-setup
```

### Manual Install

```bash
git clone https://github.com/famdeck/famdeck-relay.git
ln -sf /path/to/famdeck-relay/bin/relay ~/.local/bin/relay
```

Requires: Python >= 3.8, PyYAML.
Optional: Beads CLI (`bd`), GitHub CLI (`gh`), GitLab MCP plugin, Jira MCP plugin.

## Setup

Initialize tracker config for a project (auto-detects from git remote):

```
> /relay:trackers init

Detected GitHub remote: org/my-app
Created .claude/relay.yaml with:
  - github (default) → org/my-app
  - beads (local) → agent-created issues
```

Or manage trackers manually:

```
> /relay:trackers add --type gitlab --name main --repo group/project --set-default
> /relay:trackers show
> /relay:trackers remove --name old-tracker
```

Config lives in `.claude/relay.yaml`:

```yaml
issue_trackers:
  - name: github
    type: github
    default: true
    repo: "org/repo"
  - name: beads
    type: beads
    scope: local
    routing_rules:
      - match: { source: agent }
        action: { default: true }
```

## Skills

### `/relay:issue` — Create and Route Issues

Create an issue and let Relay route it to the right tracker based on your rules:

```
> /relay:issue "Navbar breaks on mobile" --type bug --priority high

Routing: type=bug, priority=high → github (rule: high-priority bugs)
Created: org/my-app#142 [bug, urgent]
```

Cross-project issues:

```
> /relay:issue "Atlas registry stale" --type bug --project atlas
```

Force a specific tracker:

```
> /relay:issue "Internal cleanup" --tracker beads
```

Options: `--type` (bug|task|feature|chore), `--priority` (critical|high|medium|low), `--labels`, `--body`, `--tracker`, `--project`.

### `/relay:status` — Cross-Project Issue Dashboard

Unified view across all configured trackers:

```
> /relay:status --all

my-app (github):
  #142  [bug]     Navbar breaks on mobile        open
  #138  [feature] Add dark mode support           open

my-app (beads):
  beads-042  [task]  Retry logic for sync engine  in_progress
  beads-039  [bug]   Config path resolution       open

atlas (beads):
  beads-015  [bug]   Registry stale after rename  open
```

Options: `--all` (all projects), `--project`, `--tracker`, `--status` (open|all), `--limit`.

### `/relay:handoff` — Save Work Context

Capture your current work state for pickup in another session:

```
> /relay:handoff --summary "Halfway through auth refactor"

Captured context:
  Branch: feat/beads-042-auth-refactor
  Commit: a1b2c3d (dirty: 3 files)
  Created: beads-055 [relay:handoff]
```

If no summary given, Claude generates one from the conversation context.

### `/relay:pickup` — Resume from Handoff

```
> /relay:pickup --list

Pending handoffs:
  beads-055  "Halfway through auth refactor"  (2h ago)
  beads-048  "API tests passing, needs docs"  (1d ago)

> /relay:pickup beads-055

Restored context:
  Objective: Auth refactor — extract token validation
  Branch: feat/beads-042-auth-refactor
  Decisions: Using jose instead of pyjwt
  Next: Finish middleware integration, run tests
```

## CLI

All skills wrap the `relay` CLI. You can also use it directly:

```bash
relay issue "Fix timeout" --type bug --priority high
relay route "Fix timeout" --type bug --priority high    # dry-run routing
relay sync                                               # auto-detect direction
relay sync --direction bmad-to-beads --dry-run           # preview sync
relay sync --check                                       # detect desyncs
relay import --dry-run                                   # preview BMAD import
relay import --epic 1                                    # import specific epic
relay handoff --summary "Context here"
relay pickup --list
relay status --all
relay prime                                              # session context output
```

## Routing Rules

Rules in `.claude/relay.yaml` match issue properties and route to the right tracker:

```yaml
issue_trackers:
  - name: github
    type: github
    repo: "org/repo"
    default: true
    labels: [from-relay]
    routing_rules:
      - match: { type: bug, priority: [critical, high] }
        action: { labels: [urgent], assignee: "@oncall" }
  - name: beads
    type: beads
    scope: local
    routing_rules:
      - match: { source: agent }
        action: { default: true, labels: [agent-created] }
```

Match conditions: `type`, `priority` (string or list), `source` (`human`/`agent`), `tags`.
Actions: `default` (route here), `labels` (merge with tracker defaults), `assignee`.

Rules evaluate in config order. First match with `default: true` wins. No match falls back to the tracker with `default: true`.

## Bidirectional Sync

Syncs BMAD `sprint-status.yaml` with Beads issue statuses:

```
> relay sync

Auto-detecting direction...
BMAD status changed for 2 stories.
  1.3: "in_progress" → "done" (synced to beads)
  2.1: "ready" → "in_progress" (synced to beads)
```

Transactional safety: Beads-to-BMAD sync writes BMAD first, then updates Beads metadata. If the second step fails, the first is rolled back.

## Adapter Model

| Tracker | Method | Tool | Operations |
|---------|--------|------|------------|
| Beads | CLI | `bd` | Full CRUD — create, update, close, list, show, deps |
| GitHub | CLI | `gh` | Create, list |
| GitLab | MCP | `mcp__plugin_ds_gitlab__*` | Create, list |
| Jira | MCP | `mcp__plugin_ds_atlassian__jira_*` | Create, list |

CLI adapters execute directly. MCP adapters return instructions for Claude to execute the MCP tool call.

## Hooks

Relay installs two Claude Code hooks automatically:

- **SessionStart** — registers Atlas providers + runs `relay prime` for session context
- **PreCompact** — runs `relay prime` so context survives memory compaction

## Project Structure

```
famdeck-relay/
  cli/
    main.py             # Entry point, argparse, subcommands
    config.py           # relay.yaml read/write, atlas integration
    routing.py          # Routing rule evaluation
    adapters.py         # Adapter dispatch (Beads, gh, GitLab MCP, Jira MCP)
    sync.py             # Bidirectional BMAD <-> Beads sync engine
    bmad.py             # sprint-status.yaml reader/writer
    importer.py         # BMAD story import into Beads
    models.py           # Universal Issue model
  bin/relay             # CLI entry script
  skills/               # Claude Code skill definitions
  hooks/                # SessionStart + PreCompact hooks
  tests/                # 134 tests
```

## Development

```bash
python -m pytest tests/ -q    # 134 tests
```

## License

MIT
