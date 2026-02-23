---
name: status
description: Cross-project issue dashboard — shows issues across all configured trackers (GitHub, GitLab, Jira, beads) in a unified view. Use when checking issue status, reviewing open work, or getting an overview of project issues.
argument-hint: "[--all] [--project <slug>] [--tracker <name>] [--status open|closed|all] [--limit <n>]"
---

# Relay Status Dashboard

Show a unified view of issues across all configured trackers for one or more projects.

## Parse Arguments

Parse `$ARGUMENTS`:
- `--all`: Show issues from all registered projects (via atlas registry).
- `--project <slug>`: Specific project slug. If omitted and no `--all`, use current project.
- `--tracker <name>`: Filter to a specific tracker name from the config.
- `--status <status>`: Filter by issue status — `open` (default), `closed`, `all`.
- `--limit <n>`: Maximum issues per tracker. Default: 20.

## Step 1: Resolve Projects

1. If `--all`:
   - Read `~/.claude/atlas/registry.yaml`
   - Collect all registered project slugs and paths
   - If atlas not available: "Atlas not installed. Use --project or run from a project directory."
2. If `--project <slug>`:
   - Look up in atlas registry → get path
   - If not found: try using slug as a directory path
3. Default (no flags):
   - Detect current project from cwd (atlas lookup or direct cwd)
   - If not in a project: "Not in a project directory. Use --project or --all."

## Step 2: Read Tracker Configs

For each resolved project:
1. Read `<project-path>/.claude/relay.yaml`
2. If missing: note "No relay config" and skip this project
3. Extract `issue_trackers` list
4. If `--tracker` specified: filter to only that tracker name

## Step 3: Query Each Tracker

For each tracker in each project, query issues via the appropriate adapter.

Refer to `knowledge/tracker-adapters.md` for adapter commands and tools.

### GitHub

```bash
gh issue list --repo {repo} --state {state} --limit {limit} --json number,title,labels,assignees,state,createdAt
```

### GitLab

Use ToolSearch to find `mcp__plugin_ds_gitlab__list_issues`, then call with:
- `project_id`, `state` (opened/closed), `per_page: {limit}`

### Jira

Use ToolSearch to find `mcp__plugin_ds_atlassian__jira_search`, then call with:
- JQL: `project = {project_key} AND status {= Done | != Done | is not EMPTY}` based on status filter
- `max_results: {limit}`

### Beads

```bash
bd list [--status {status}]
```

If an adapter is unavailable for a configured tracker, note it and continue with others.

## Step 4: Display Unified Table

Group results by project, then by tracker:

```
{project_slug}
  {tracker_name} ({tracker_type}{, default if default}):
    #{id}  [{type}]  {title}                              {assignee}  {status}
    #{id}  [{type}]  {title}                              {assignee}  {status}

  {tracker_name} ({tracker_type}):
    {id}   [{type}]  {title}                              {status}
```

Example:
```
digital-web-sdk
  gitlab (default):
    #42  [bug]     JWT refresh broken after 24h          @dev-team   open
    #38  [feature] Add retry logic to API calls          @ivintik    open

  beads (local):
    bd-x1y2  [task]  Implement token rotation            in_progress
    bd-y3z4  [task]  Update auth docs                    open

clawrig
  github (default):
    #12  [feature] Add project-ref MCP health check      open
    #10  [bug]     Session cleanup on timeout             open
```

If no issues found for a tracker, show: `{tracker_name}: No {status} issues`

## Summary Line

At the end, print:
```
Total: {N} issues across {M} trackers in {P} projects
```
