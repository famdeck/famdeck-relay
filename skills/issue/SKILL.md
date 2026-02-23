---
name: issue
description: Create and route an issue to the right tracker based on project config — supports GitHub, GitLab, Jira, and beads. Use when creating issues, filing bugs, requesting features, or logging tasks across projects.
argument-hint: '"title" [--project <slug>] [--tracker <name>] [--type bug|task|feature|chore] [--priority critical|high|medium|low] [--labels <l1,l2>] [--assignee <user>] [--body <text>] [--no-beads]'
---

# Relay Issue Creation

Create an issue in the right tracker based on the project's `.claude/relay.yaml` routing configuration.

## Parse Arguments

Parse `$ARGUMENTS`:
- First positional argument (quoted string): **title** (required)
- `--project <slug>`: Target project slug. If omitted, detect from cwd.
- `--tracker <name>`: Force a specific tracker by name (skips routing rules).
- `--type <type>`: Issue type — `bug`, `task`, `feature`, `chore`. Default: `task`.
- `--priority <priority>`: `critical`, `high`, `medium`, `low`. Default: `medium`.
- `--labels <labels>`: Comma-separated extra labels.
- `--assignee <user>`: Assignee (format depends on tracker).
- `--body <text>`: Issue description. If omitted, ask interactively or generate from context.
- `--no-beads`: Skip beads cross-reference creation.

If no title is provided, ask the user for one.

## Step 1: Resolve Project

1. If `--project <slug>` provided:
   - Read `~/.claude/atlas/registry.yaml`
   - Find the project entry → get its `path`
   - If atlas not installed or slug not found: inform the user and ask for the project path
2. Otherwise, detect from current working directory:
   - Try atlas registry lookup (match cwd against project paths)
   - If no atlas: use cwd directly

## Step 2: Read Tracker Config

1. Read `<project-path>/.claude/relay.yaml`
2. If the file doesn't exist:
   - Inform the user: "No tracker config found for this project."
   - Ask: "Create one with `/relay:trackers init`, or specify a tracker manually?"
   - Stop here — don't guess.

## Step 3: Route the Issue

Refer to `knowledge/routing-rules.md` for the full decision tree.

1. If `--tracker <name>` specified:
   - Find tracker by `name` in config → use it directly, skip routing rules
   - If name not found in config: error and list available tracker names
2. Else, evaluate routing rules:
   - Build match context: `{ type, priority, source: "human", tags: [from --labels] }`
   - Evaluate rules across all trackers (config order, first match wins)
   - If a rule matches with `action.default: true` → that tracker wins
   - If a rule matches without `action.default` → apply labels/assignee, continue to default tracker
3. If no rule matches → use the tracker with `default: true`
4. If no default → ask the user which tracker to use (list configured trackers)

Collect: chosen tracker config, merged labels (tracker defaults + rule labels + user labels), assignee.

## Step 4: Check Adapter Availability

Refer to `knowledge/tracker-adapters.md` for adapter details.

Based on the chosen tracker's `type`:
- **github**: Check `which gh` via Bash. If missing: "GitHub CLI not installed. Install: https://cli.github.com/"
- **gitlab**: Use ToolSearch to check for `mcp__plugin_ds_gitlab__create_issue`. If missing: "GitLab MCP not available. Install with: /toolkit:toolkit-setup"
- **jira**: Use ToolSearch to check for `mcp__plugin_ds_atlassian__jira_create_issue`. If missing: "Jira MCP not available. Install with: /toolkit:toolkit-setup"
- **beads**: Check `which bd` via Bash. If missing: "Beads CLI not installed. Install with: /toolkit:toolkit-setup"

If the adapter is unavailable, try the next tracker in config. If all unavailable, stop with error.

## Step 5: Prepare Issue Body

If `--body` was provided, use it.

Otherwise:
- If there's clear context from the current conversation (e.g., a bug just discussed, a feature being planned), generate a concise description.
- If no context: ask the user for a description using AskUserQuestion.

For cross-project issues (when `--project` differs from cwd project), prepend to the body:
```
> Created from project: {current_project_slug}
```

## Step 6: Create the Issue

Use the appropriate adapter command/tool:

**GitHub** (`gh` CLI via Bash):
```bash
gh issue create --repo {repo} --title "{title}" --body "{body}" --label {comma-labels} [--assignee {assignee}]
```

**GitLab** (MCP tool):
Call `mcp__plugin_ds_gitlab__create_issue` with:
- `project_id`: from tracker config
- `title`: issue title
- `description`: issue body
- `labels`: comma-separated labels

**Jira** (MCP tool):
Call `mcp__plugin_ds_atlassian__jira_create_issue` with:
- `project_key`: from tracker config
- `summary`: issue title
- `description`: issue body
- `issuetype`: mapped from relay type (see `knowledge/tracker-adapters.md` for mappings)
- `priority`: mapped from relay priority

**Beads** (`bd` CLI via Bash):
```bash
bd create --title "{title}" --description "{body}" --type {type} --priority {priority_number} --label {labels}
```

## Step 7: Beads Cross-Reference

Refer to `knowledge/beads-integration.md` for cross-referencing details.

If ALL of these are true:
- The issue was created in a non-beads tracker
- The project's config includes a `type: beads` tracker entry
- `--no-beads` was NOT passed
- `bd` CLI is available

Then create a beads cross-reference:
```bash
bd create --type task \
  --title "External: {title}" \
  --description "Tracked in {tracker_name}: {issue_url_or_id}" \
  --label external-ref
```

## Output

Print a summary:
```
Issue created in {tracker_name} ({tracker_type}):
  {issue_url_or_id}
  Type: {type}  Priority: {priority}
  Labels: {merged_labels}
  Assignee: {assignee or "none"}
  {beads_cross_ref_line if created}
```
