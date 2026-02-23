---
name: relay
description: "Cross-project issue routing. Create issues in the right tracker (GitHub, GitLab, Jira, Beads) based on per-project .claude/relay.yaml config. Read the config, evaluate routing rules, and create via the matching adapter."
metadata: {"openclaw":{"emoji":"🔀","requires":{"anyBins":["gh","bd"]}}}
---

# Relay — Issue Router

Route issues to the correct tracker based on per-project `.claude/relay.yaml` configuration. Supports GitHub (`gh` CLI), GitLab (MCP), Jira (MCP), and Beads (`bd` CLI).

## When to Use

- User asks to "create an issue", "file a bug", "open a ticket" for a project
- User asks to route or triage an issue to the right place
- User wants to initialize tracker config for a project

## Creating an Issue

Follow this decision tree step by step.

### Step 1 — Resolve Project

Determine which project the issue targets:

1. If user specifies a project path or name → use that path
2. Otherwise → use current working directory
3. Verify `.claude/relay.yaml` exists at `<project-root>/.claude/relay.yaml`
4. If missing → offer to create one (see "Initializing Config" below)

### Step 2 — Read Config

Read `.claude/relay.yaml` from the project root. Parse the `issue_trackers` list.

### Step 3 — Check Explicit Tracker Override

If user explicitly names a tracker (e.g., "create in GitLab", "file on GitHub"):
- Find that tracker by `name` or `type` in the config
- Skip routing rules, go directly to Step 6

### Step 4 — Evaluate Routing Rules

For each tracker in `issue_trackers`, evaluate its `routing_rules` in order:

```
For each tracker:
  For each rule in tracker.routing_rules:
    Check match conditions (ALL must be true):
      - type: matches issue type (bug/task/feature/chore)
      - priority: matches issue priority (critical/high/medium/low)
      - source: "agent" if you're creating it autonomously, "human" if user asked
      - tags: all listed tags present
    If match:
      Apply action:
        - default: true → this tracker wins
        - labels: add these labels
        - assignee: set this assignee
      Use this tracker → go to Step 6
```

First matching rule wins. If a rule has `action.default: true`, that tracker is selected.

### Step 5 — Fall Back to Default

If no routing rule matched:
- Use the tracker with `default: true` at the top level
- If no tracker has `default: true` → ask the user which tracker to use

### Step 6 — Check Adapter Availability

Before creating, verify the adapter is available:

| Tracker Type | Check |
|---|---|
| `github` | `which gh` succeeds |
| `gitlab` | `mcp__plugin_ds_gitlab__create_issue` tool exists (use ToolSearch) |
| `jira` | `mcp__plugin_ds_atlassian__jira_create_issue` tool exists (use ToolSearch) |
| `beads` | `which bd` succeeds |

If unavailable → tell user what's missing, try next tracker.

### Step 7 — Create Issue via Adapter

Use the appropriate adapter (see "Tracker Adapters" below). Merge labels from:
1. Tracker's `labels` (defaults)
2. Matched routing rule's `action.labels`
3. User-specified labels

### Step 8 — Beads Cross-Reference (Optional)

If the config includes a `type: beads` tracker AND the issue was created in a different tracker:

```bash
bd create --type task \
  --title "External: <issue title>" \
  --description "Tracked in <tracker>: <issue URL>" \
  --label external-ref
```

Report the created issue URL/ID and which tracker was used.

## Tracker Adapters

### GitHub (`gh` CLI)

```bash
# Create issue
gh issue create --repo <repo> --title "<title>" --body "<body>" --label "<label1>,<label2>"

# With assignee
gh issue create --repo <repo> --title "<title>" --body "<body>" --label "<labels>" --assignee "<user>"

# List issues
gh issue list --repo <repo> --state open --label "<labels>"

# View issue
gh issue view <number> --repo <repo> --json title,body,state,labels,assignees

# Add comment
gh issue comment <number> --repo <repo> --body "<body>"

# Search
gh issue list --repo <repo> --search "<query>"
```

Config field: `repo` (e.g., `"org/repo-name"`)

### GitLab (MCP Tools)

Load tools first with ToolSearch (`+gitlab create_issue`), then call:

| Operation | MCP Tool | Key Parameters |
|---|---|---|
| Create | `mcp__plugin_ds_gitlab__create_issue` | `project_id`, `title`, `description`, `labels` |
| List | `mcp__plugin_ds_gitlab__list_issues` | `project_id`, `state`, `labels` |
| View | `mcp__plugin_ds_gitlab__get_issue` | `project_id`, `issue_iid` |
| Comment | `mcp__plugin_ds_gitlab__create_issue_note` | `project_id`, `issue_iid`, `body` |
| Update | `mcp__plugin_ds_gitlab__update_issue` | `project_id`, `issue_iid`, fields... |

Config field: `project_id` (e.g., `"group/project"` — URL-encoded path)

### Jira (MCP Tools)

Load tools first with ToolSearch (`+atlassian jira_create_issue`), then call:

| Operation | MCP Tool | Key Parameters |
|---|---|---|
| Create | `mcp__plugin_ds_atlassian__jira_create_issue` | `project_key`, `summary`, `description`, `issuetype`, `priority` |
| Search | `mcp__plugin_ds_atlassian__jira_search` | `jql` |
| View | `mcp__plugin_ds_atlassian__jira_get_issue` | `issue_key` |
| Comment | `mcp__plugin_ds_atlassian__jira_add_comment` | `issue_key`, `body` |
| Update | `mcp__plugin_ds_atlassian__jira_update_issue` | `issue_key`, fields... |

**Type mapping**: bug → `Bug`, feature → `Story`, task → `Task`
**Priority mapping**: critical → `Highest`, high → `High`, medium → `Medium`, low → `Low`

Config field: `project_key` (e.g., `"PROJ"`)

### Beads (`bd` CLI)

```bash
# Create issue
bd create --type <task|bug|feature> --title "<title>" --description "<body>" --priority <0-4>

# List
bd list --status <open|in_progress|done>

# View
bd show <id>

# Comment
bd comment <id> "<body>"

# Search
bd search "<query>"
```

**Priority mapping**: critical → `0`, high → `1`, medium → `2`, low → `3`

Config field: `scope` (typically `local`)

## Issue Fields Mapping

| Generic Field | GitHub | GitLab | Jira | Beads |
|---|---|---|---|---|
| title | `--title` | `title` | `summary` | `--title` |
| description | `--body` | `description` | `description` | `--description` |
| type | label | label | `issuetype` | `--type` |
| priority | label (P0-P4) | label | `priority` | `--priority` (0-4) |
| labels | `--label` | `labels` | `labels` | `--label` |
| assignee | `--assignee` | `assignee_ids` | `assignee` | — |

## Config Format (`.claude/relay.yaml`)

```yaml
issue_trackers:
  - name: <display_name>          # e.g., "gitlab", "github-main"
    type: gitlab|github|jira|beads
    # Tracker-specific identifier (exactly one):
    project_id: "group/project"   # GitLab
    repo: "org/repo"              # GitHub
    project_key: "PROJ"           # Jira
    scope: local                  # Beads
    default: true                 # Primary tracker (at most one)
    labels: [tag1, tag2]          # Default labels on all issues
    routing_rules:                # Optional fine-grained routing
      - match:
          type: bug               # bug|task|feature|chore
          priority: [critical, high]
          source: agent           # agent|human
          tags: [frontend]
        action:
          default: true           # This tracker wins for this match
          labels: [urgent]        # Extra labels
          assignee: "@user"       # Auto-assign
```

### Example Configs

**Single tracker (simple):**
```yaml
issue_trackers:
  - name: github
    type: github
    repo: "user/my-project"
    default: true
```

**Multi-tracker with routing:**
```yaml
issue_trackers:
  - name: gitlab
    type: gitlab
    project_id: "team/backend"
    default: true
    labels: [backend]
    routing_rules:
      - match: { type: bug, priority: [critical, high] }
        action: { labels: [urgent], assignee: "@lead" }

  - name: beads
    type: beads
    scope: local
    routing_rules:
      - match: { source: agent }
        action: { default: true }
      - match: { type: task }
        action: { default: true }
```

**Critical to Jira, rest to GitHub:**
```yaml
issue_trackers:
  - name: jira
    type: jira
    project_key: "PROJ"
    routing_rules:
      - match: { priority: [critical, high] }
        action: { default: true, labels: [escalated] }

  - name: github
    type: github
    repo: "org/repo"
    default: true
```

## Initializing Config

When `.claude/relay.yaml` is missing and the user wants to create an issue:

1. Check `.git/config` for the remote URL
2. Detect host:
   - `github.com` → suggest `type: github`, extract `org/repo` from remote
   - `gitlab.*` → suggest `type: gitlab`, extract project path from remote
   - Otherwise → ask user
3. Ask if they also want a `type: beads` tracker for local/agent work
4. Write `.claude/relay.yaml` to `<project-root>/.claude/`

## Rules

- **Always** read `.claude/relay.yaml` before creating an issue — never guess the tracker
- Evaluate routing rules **in order** — first match wins
- Merge labels (tracker defaults + routing action + user-specified) — don't replace
- Source is `agent` when you create autonomously, `human` when user explicitly asks
- Only create beads cross-references if a `type: beads` tracker is configured
- If adapter is unavailable, explain what's missing and try the next configured tracker
- For cross-project issues, include "Created from: <source project>" in the issue body
