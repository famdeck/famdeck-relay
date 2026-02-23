# Tracker Adapters

Adapters translate relay's generic issue operations into tracker-specific tool calls or CLI commands.

## Adapter Interface

Every adapter implements these operations (not all required):

| Operation | Description |
|---|---|
| `create_issue` | Create a new issue |
| `list_issues` | List issues with filters |
| `get_issue` | Get issue details |
| `update_issue` | Update issue fields |
| `add_comment` | Add a comment to an issue |
| `search` | Search issues by text |

## GitHub Adapter

**Requires**: `gh` CLI (system dependency)

| Operation | Command |
|---|---|
| `create_issue` | `gh issue create --repo {repo} --title {title} --body {body} --label {labels}` |
| `list_issues` | `gh issue list --repo {repo} --state {state} --label {labels}` |
| `get_issue` | `gh issue view {number} --repo {repo} --json title,body,state,labels,assignees` |
| `update_issue` | `gh issue edit {number} --repo {repo} --title/--body/--add-label` |
| `add_comment` | `gh issue comment {number} --repo {repo} --body {body}` |
| `search` | `gh issue list --repo {repo} --search {query}` |

Config field: `repo` (e.g., `"org/repo-name"`). Maps to `gh --repo` parameter.

## GitLab Adapter

**Requires**: `plugin_ds_gitlab` MCP server

| Operation | MCP Tool | Key Parameters |
|---|---|---|
| `create_issue` | `mcp__plugin_ds_gitlab__create_issue` | `project_id`, `title`, `description`, `labels` |
| `list_issues` | `mcp__plugin_ds_gitlab__list_issues` | `project_id`, `state`, `labels` |
| `get_issue` | `mcp__plugin_ds_gitlab__get_issue` | `project_id`, `issue_iid` |
| `update_issue` | `mcp__plugin_ds_gitlab__update_issue` | `project_id`, `issue_iid`, fields... |
| `add_comment` | `mcp__plugin_ds_gitlab__create_issue_note` | `project_id`, `issue_iid`, `body` |
| `search` | `mcp__plugin_ds_gitlab__list_issues` | `project_id`, `search` |

Config field: `project_id` (e.g., `"digital/web-sdk"`). URL-encoded path used directly.

### Label Handling

- Default labels from tracker config applied automatically
- Routing rule labels merged with defaults
- User-specified `--labels` added on top

## Jira Adapter

**Requires**: `plugin_ds_atlassian` MCP server

| Operation | MCP Tool | Key Parameters |
|---|---|---|
| `create_issue` | `mcp__plugin_ds_atlassian__jira_create_issue` | `project_key`, `summary`, `description`, `issuetype`, `priority` |
| `list_issues` | `mcp__plugin_ds_atlassian__jira_search` | `jql` query |
| `get_issue` | `mcp__plugin_ds_atlassian__jira_get_issue` | `issue_key` |
| `update_issue` | `mcp__plugin_ds_atlassian__jira_update_issue` | `issue_key`, fields... |
| `add_comment` | `mcp__plugin_ds_atlassian__jira_add_comment` | `issue_key`, `body` |
| `search` | `mcp__plugin_ds_atlassian__jira_search` | `jql` with text search |

Config field: `project_key` (e.g., `"PROJ"`).

### Jira Type Mappings

| Relay Type | Jira issuetype |
|---|---|
| bug | Bug |
| feature | Story |
| task | Task |
| chore | Task |

### Jira Priority Mappings

| Relay Priority | Jira Priority |
|---|---|
| critical | Highest |
| high | High |
| medium | Medium |
| low | Low |

### JQL Generation

List issues: `project = {project_key} AND status != Done`
With labels: `project = {project_key} AND labels IN ({labels})`
Search: `project = {project_key} AND status != Done AND text ~ "{query}"`

## Beads Adapter

**Requires**: `bd` CLI (installed via toolkit)

| Operation | Command |
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

## Issue Field Mapping

| Relay Field | GitHub | GitLab | Jira | Beads |
|---|---|---|---|---|
| title | title | title | summary | title |
| description | body | description | description | description |
| type | label | label | issuetype | issue_type |
| priority | label (P0-P4) | label | priority | priority (0-4) |
| labels | labels[] | labels[] | labels[] | labels |
| assignee | assignees[] | assignee_ids[] | assignee | — |
| milestone | milestone | milestone_id | fixVersion | — |

## Adapter Discovery

At runtime, check which adapters are available:

1. **MCP tools** — Use ToolSearch to check:
   - `mcp__plugin_ds_gitlab__create_issue` → GitLab adapter available
   - `mcp__plugin_ds_atlassian__jira_create_issue` → Jira adapter available

2. **CLI tools** — Use Bash `which`:
   - `which gh` → GitHub adapter available
   - `which bd` → Beads adapter available

3. Match available adapters against project's configured trackers.

4. If a configured tracker's adapter is unavailable:
   - Print: `"{Tracker} not available. Install with: /toolkit:toolkit-setup"`
   - Fall back to next available tracker in config order.
