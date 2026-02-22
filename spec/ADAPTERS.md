# Relay — Tracker Adapters

## Overview

Adapters translate relay's generic issue operations into tracker-specific MCP tool calls. Each adapter is a knowledge definition that relay's skills reference at runtime.

## Adapter Interface

Every adapter implements these operations:

| Operation | Description |
|---|---|
| `create_issue` | Create a new issue |
| `list_issues` | List issues with filters |
| `get_issue` | Get issue details |
| `update_issue` | Update issue fields |
| `add_comment` | Add a comment to an issue |
| `search` | Search issues by text |

Not all operations are required. Relay gracefully handles missing operations.

## GitLab Adapter

**Required MCP**: `plugin_ds_gitlab` (already installed)

### Tool Mapping

| Relay Operation | MCP Tool | Key Parameters |
|---|---|---|
| `create_issue` | `mcp__plugin_ds_gitlab__create_issue` | `project_id`, `title`, `description`, `labels` |
| `list_issues` | `mcp__plugin_ds_gitlab__list_issues` | `project_id`, `state`, `labels` |
| `get_issue` | `mcp__plugin_ds_gitlab__get_issue` | `project_id`, `issue_iid` |
| `update_issue` | `mcp__plugin_ds_gitlab__update_issue` | `project_id`, `issue_iid`, fields... |
| `add_comment` | `mcp__plugin_ds_gitlab__create_issue_note` | `project_id`, `issue_iid`, `body` |
| `search` | `mcp__plugin_ds_gitlab__list_issues` | `project_id`, `search` |

### Project ID Resolution

Atlas stores `project_id` in tracker config (e.g., `"digital/web-sdk"`). This maps directly to GitLab's `project_id` parameter (URL-encoded path).

### Label Handling

- Default labels from atlas tracker config applied automatically
- Routing rule labels merged with defaults
- User-specified labels added on top

## GitHub Adapter

**Required**: `gh` CLI (system dependency, usually pre-installed)

### Tool Mapping

GitHub operations use `gh` CLI via bash, not MCP:

| Relay Operation | Command |
|---|---|
| `create_issue` | `gh issue create --repo {repo} --title {title} --body {body} --label {labels}` |
| `list_issues` | `gh issue list --repo {repo} --state {state} --label {labels}` |
| `get_issue` | `gh issue view {number} --repo {repo} --json title,body,state,labels,assignees` |
| `update_issue` | `gh issue edit {number} --repo {repo} --title/--body/--add-label` |
| `add_comment` | `gh issue comment {number} --repo {repo} --body {body}` |
| `search` | `gh issue list --repo {repo} --search {query}` |

### Repo Resolution

Atlas stores `repo` in tracker config (e.g., `"iVintik/clawrig"`). This maps directly to `gh --repo` parameter.

## Jira Adapter

**Required MCP**: `plugin_ds_atlassian` (already installed)

### Tool Mapping

| Relay Operation | MCP Tool | Key Parameters |
|---|---|---|
| `create_issue` | `mcp__plugin_ds_atlassian__jira_create_issue` | `project_key`, `summary`, `description`, `issuetype`, `priority` |
| `list_issues` | `mcp__plugin_ds_atlassian__jira_search` | `jql` query |
| `get_issue` | `mcp__plugin_ds_atlassian__jira_get_issue` | `issue_key` |
| `update_issue` | `mcp__plugin_ds_atlassian__jira_update_issue` | `issue_key`, fields... |
| `add_comment` | `mcp__plugin_ds_atlassian__jira_add_comment` | `issue_key`, `body` |
| `search` | `mcp__plugin_ds_atlassian__jira_search` | `jql` with text search |

### Jira-Specific Mappings

| Relay Field | Jira Field | Notes |
|---|---|---|
| type: bug | issuetype: Bug | Standard Jira type |
| type: feature | issuetype: Story | Mapped to Story |
| type: task | issuetype: Task | Direct mapping |
| priority: critical | priority: Highest | Jira priority names |
| priority: high | priority: High | |
| priority: medium | priority: Medium | |
| priority: low | priority: Low | |

### JQL Generation

For `list_issues` and `search`, relay generates JQL:

```
project = {project_key} AND status != Done AND text ~ "{search_text}"
```

Labels filter:
```
project = {project_key} AND labels IN ({labels})
```

## Beads Adapter

**Required**: `bd` CLI (installed via toolkit)

### Tool Mapping

| Relay Operation | Command |
|---|---|
| `create_issue` | `bd create --title {title} --description {body} --type {type} --priority {priority}` |
| `list_issues` | `bd list --status {status}` |
| `get_issue` | `bd show {id}` |
| `update_issue` | `bd update {id} --status/--priority/--title` |
| `add_comment` | `bd comment {id} {body}` |
| `search` | `bd search {query}` |

### Beads-Specific Features

- Cross-references: when relay creates an external issue, it can also create a beads issue linked to it
- Dependencies: beads' dependency graph preserved during handoff export/import
- Agent discovery: issues created with `source: agent` are discoverable via `bd ready`

## Adapter Discovery

At runtime, relay checks which adapters are available:

```
1. Check for MCP tools:
   - mcp__plugin_ds_gitlab__create_issue → GitLab adapter available
   - mcp__plugin_ds_atlassian__jira_create_issue → Jira adapter available

2. Check for CLI tools:
   - which gh → GitHub adapter available
   - which bd → Beads adapter available

3. Match available adapters against project's configured trackers

4. If configured tracker's adapter is unavailable:
   - Print: "GitLab MCP not installed. Install with: /toolkit-setup"
   - Fall back to next available tracker
```

## Adding New Adapters

To add a new tracker type (e.g., Linear, Asana):

1. Add adapter definition in `knowledge/tracker-adapters.md`
2. Define tool mapping (MCP tools or CLI commands)
3. Define field mapping (relay generic → tracker specific)
4. Add type to atlas schema validation
5. Test with a project configured for the new tracker

The adapter pattern means relay's core skills never change — only knowledge files are updated.
