# Famdeck Relay

Issue routing, bidirectional sync, and work handoffs across trackers. Routes issues to GitHub, GitLab, Jira, or Beads based on per-project rules. Syncs BMAD sprint-status.yaml with Beads bidirectionally.

Part of the [Famdeck](https://github.com/famdeck/famdeck) autonomous development toolkit.

## Installation

```bash
git clone https://github.com/famdeck/famdeck-relay.git
ln -sf /path/to/famdeck-relay/bin/relay ~/.local/bin/relay
```

Requires: Python >= 3.8, PyYAML.
Optional: Beads CLI (`bd`), GitHub CLI (`gh`), GitLab MCP, Jira MCP.

Verify: `relay prime`

## Setup

Initialize tracker config for a project:

```bash
cd /path/to/your-project
relay trackers init          # auto-detects GitHub/GitLab from git remote
relay trackers show          # view current config
relay trackers add --type gitlab --project-id group/project
relay trackers remove --name gitlab
```

Creates `.claude/relay.yaml`:

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

# Optional — all values have sensible defaults
defaults:
  cli_timeout: 30              # bd/gh command timeout (seconds)
  git_timeout: 5               # git command timeout
  handoff_timeout: 15          # handoff operation timeout
  codeman_api_url: "http://localhost:3000"
  codeman_timeout: 15
  status_list_limit: 20
  sprint_status_paths:         # where to find sprint-status.yaml
    - "_bmad-output/implementation-artifacts/sprint-status.yaml"
    - "_bmad-output/sprint-status.yaml"
    - "sprint-status.yaml"
```

## Commands

### Issue Routing

```bash
# Create and route an issue
relay issue "Fix the sync timeout" --type bug --priority high
relay issue "Add dark mode" --type feature --priority medium --body "Details here"

# Cross-project
relay issue "Atlas registry stale" --type bug -p atlas

# Dry-run — see where it would go
relay route "Fix sync" --type bug --priority high

# Force a specific tracker
relay issue "Internal task" --tracker beads
```

Issue types: `bug`, `task`, `feature`, `chore`.
Priorities: `critical`, `high`, `medium`, `low`.

### Bidirectional Sync

Sync BMAD sprint-status.yaml with Beads issue statuses.

```bash
relay sync                              # auto-detect which side changed
relay sync --direction bmad-to-beads    # force BMAD as source of truth
relay sync --direction beads-to-bmad    # force Beads as source of truth
relay sync --dry-run                    # preview without changes

relay sync --check                      # detect desyncs (read-only, non-zero exit)
relay sync --alert-conflicts            # create Beads issues for sync conflicts
```

Auto-detect uses `metadata.bmad_status` as a checkpoint: if the stored value differs from current BMAD status, BMAD changed; if Beads status differs from what BMAD implies, Beads changed; if both changed, it's a conflict.

Transactional safety: Beads-to-BMAD sync writes BMAD first, then updates Beads metadata. If the second step fails, the first is rolled back.

### BMAD Import

Import stories from sprint-status.yaml into Beads.

```bash
relay import --dry-run       # preview
relay import                 # execute
relay import --epic 1        # only epic 1 stories
```

### Handoffs

Save work context for later pickup.

```bash
relay handoff --summary "Halfway through auth refactor"
relay handoff --summary "Done with API" --instructions "Run integration tests next"

relay pickup --list          # list pending handoffs
relay pickup beads-XXX       # restore context, mark in_progress
```

Captures: git branch, commit hash, dirty state, changed files.

### Status Dashboard

```bash
relay status                 # current project
relay status --all           # all atlas-registered projects
relay status --tracker beads # filter to one tracker
relay status --status all    # include closed issues
```

### Session Context

```bash
relay prime                  # output context block (run by hooks automatically)
```

## Adapter Model

| Tracker | Method | Tool | Operations |
|---------|--------|------|------------|
| Beads | CLI | `bd` | Full CRUD — create, update, close, list, show, deps |
| GitHub | CLI | `gh` | Create, list |
| GitLab | MCP | `mcp__plugin_ds_gitlab__*` | Create, list (returns MCP instructions) |
| Jira | MCP | `mcp__plugin_ds_atlassian__jira_*` | Create, list (returns MCP instructions) |

CLI adapters execute directly and return results. MCP adapters return `{"status": "needs_mcp", "tool": "...", "params": {...}}` for Claude to execute.

## Routing Rules

Rules in `relay.yaml` match issue properties and route to trackers:

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

Match conditions: `type`, `priority` (string or list), `source` (`human` or `agent`), `tags`.
Actions: `default` (route here), `labels` (merge), `assignee` (set if not user-specified).

Rules are evaluated in config order. First match with `default: true` wins. If no rule matches, the tracker with `default: true` is used.

## Hooks

Relay installs two Claude Code hooks:

- **SessionStart**: Registers atlas providers + runs `relay prime` for session context
- **PreCompact**: Runs `relay prime` so context survives compaction

## Project Structure

```
famdeck-relay/
  cli/
    main.py             # Entry point, argparse, subcommands
    config.py           # relay.yaml read/write, atlas integration, defaults
    routing.py          # Routing rule evaluation
    adapters.py         # Adapter dispatch (BeadsAdapter, gh, GitLab MCP, Jira MCP)
    sync.py             # Bidirectional BMAD <-> Beads sync engine
    bmad.py             # sprint-status.yaml reader/writer
    importer.py         # BMAD story import into Beads
    codeman.py          # Ralph Loop session status adapter
    models.py           # Universal Issue model
  bin/relay             # CLI entry script
  skills/               # Claude Code skill wrappers
  hooks/                # SessionStart + PreCompact hooks
  tests/                # 134 tests
```

## Running Tests

```bash
python -m pytest tests/ -q    # 134 tests
```

## License

MIT
