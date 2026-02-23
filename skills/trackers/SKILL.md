---
name: trackers
description: Manage per-project issue tracker configuration — show, initialize, add, or remove trackers in .claude/relay.yaml. Use when setting up relay for a project, viewing tracker config, adding new trackers, or managing routing rules.
argument-hint: "[show|init|add|remove <name>] [--project <slug>]"
---

# Relay Tracker Management

Manage the per-project `.claude/relay.yaml` issue tracker configuration.

Refer to `knowledge/relay-config-schema.md` for the full config schema.

## Parse Arguments

Parse `$ARGUMENTS`:
- Subcommand (first positional argument): `show` (default), `init`, `add`, `remove`
- For `remove`: second positional argument is the tracker name to remove.
- `--project <slug>`: Target project. If omitted, use current project (cwd).

## Resolve Project

1. If `--project <slug>` provided:
   - Read `~/.claude/atlas/registry.yaml`, find project → get path
   - If not found: try slug as directory path
2. Otherwise: use cwd as project path
   - Optionally detect project slug from atlas registry

Set `project_path` = resolved path. Config file = `{project_path}/.claude/relay.yaml`.

## Subcommand: show (default)

1. Read `{project_path}/.claude/relay.yaml`
2. If missing: "No tracker config found. Run `/relay:trackers init` to create one."
3. Display in readable format:

```
{project_slug} — Issue Trackers:
  1. {name} ({type}{, default if default}) — {type-specific-id} — labels: {labels}
     Rules: {summary of each routing rule}
  2. {name} ({type})
     Rules: {summary}
```

Example:
```
digital-web-sdk — Issue Trackers:
  1. gitlab (default) — project: digital/web-sdk — labels: sdk, web
     Rules: bugs+critical/high → @team-lead +urgent | features → +enhancement
  2. beads (local)
     Rules: agent tasks → beads | quick tasks → beads
```

## Subcommand: init

Create `.claude/relay.yaml` if it doesn't exist.

1. Check if `{project_path}/.claude/relay.yaml` already exists
   - If yes: "Tracker config already exists. Use `show` to view, `add` to add trackers."
   - Stop.

2. Detect repo host from git config:
   ```bash
   git -C {project_path} config --get remote.origin.url
   ```
   - Contains `github.com` → suggest `github` adapter
   - Contains `gitlab` → suggest `gitlab` adapter
   - Otherwise → ask the user

3. Auto-detect tracker-specific config:
   - **github**: Extract `owner/repo` from remote URL
   - **gitlab**: Extract project path from remote URL

4. Ask using AskUserQuestion:
   - "Detected {type} repository ({detected_id}). Use as primary tracker?" → Yes (recommended) / Different tracker / Skip
   - "Also track local/agent work in beads?" → Yes / No

5. Build and write `.claude/relay.yaml`:

   For github:
   ```yaml
   issue_trackers:
     - name: github
       type: github
       repo: "{owner/repo}"
       default: true
   ```

   For gitlab:
   ```yaml
   issue_trackers:
     - name: gitlab
       type: gitlab
       project_id: "{project_path}"
       default: true
   ```

   If beads requested, append:
   ```yaml
     - name: beads
       type: beads
       scope: local
       routing_rules:
         - match: { source: agent }
           action: { default: true }
   ```

6. Ensure `.claude/` directory exists (`mkdir -p {project_path}/.claude`).
7. Write the config file.
8. Print: "Created {project_path}/.claude/relay.yaml with {N} tracker(s)."

## Subcommand: add

Add a new tracker to an existing config.

1. Read `{project_path}/.claude/relay.yaml`
   - If missing: "No config found. Run `init` first."
2. Ask tracker type using AskUserQuestion:
   - Options: "GitHub", "GitLab", "Jira", "Beads"
3. Based on type, ask for required config:
   - **github**: "Repository (owner/repo):" — try to auto-detect from git remote
   - **gitlab**: "Project ID (group/project):" — try to auto-detect from git remote
   - **jira**: "Project key (e.g., PROJ):"
   - **beads**: No extra config needed (scope: local)
4. Ask: "Set as default tracker?" → Yes / No
5. Ask: "Default labels (comma-separated, or none):"
6. Ask: "Add routing rules?" → Yes / No
   - If yes: guide through match/action pairs interactively
7. Append the new tracker entry to `issue_trackers` in the YAML
8. Write updated config
9. Print: "Added {name} ({type}) tracker to relay config."

## Subcommand: remove

Remove a tracker by name.

1. Read `{project_path}/.claude/relay.yaml`
   - If missing: "No config found."
2. Find tracker by name in `issue_trackers`
   - If not found: "Tracker '{name}' not found. Available: {list names}"
3. If it's the only tracker: warn "This is the only configured tracker. Removing it leaves no trackers."
4. If it has `default: true`: warn "This is the default tracker. After removal, set another tracker as default."
5. Confirm with user: "Remove tracker '{name}' ({type})?"
6. Remove the entry from `issue_trackers`
7. Write updated config
8. Print: "Removed {name} from relay config."
