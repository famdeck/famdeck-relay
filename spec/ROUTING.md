# Relay — Issue Routing

## Routing Overview

When a user creates an issue via relay, the routing engine determines which tracker receives it. This decision is based on the project's `issue_trackers` configuration from atlas.

## Routing Decision Tree

```
/relay:issue "Fix JWT refresh bug" [--project X] [--tracker Y] [--type bug]
  │
  ├─ 1. Resolve project
  │     ├─ Explicit --project flag → use that
  │     ├─ Atlas cwd detection → use current project
  │     └─ No project found → ask user
  │
  ├─ 2. Explicit tracker?
  │     ├─ --tracker gitlab → use gitlab tracker, skip routing
  │     └─ No → continue to routing rules
  │
  ├─ 3. Load project's issue_trackers[] from atlas
  │
  ├─ 4. Evaluate routing rules (in order)
  │     │
  │     │  For each tracker's routing_rules:
  │     │    match:
  │     │      type: bug|task|feature|...    # Issue type filter
  │     │      priority: [critical, high]    # Priority filter
  │     │      source: agent|human           # Who's creating
  │     │      tags: [frontend]              # Tag filter
  │     │    action:
  │     │      default: true                 # This tracker wins
  │     │      labels: [urgent]              # Extra labels
  │     │      assignee: "@user"             # Auto-assign
  │     │
  │     ├─ Rule matches → use that tracker + apply actions
  │     └─ No rules match → continue
  │
  ├─ 5. Fall back to default tracker (default: true)
  │
  ├─ 6. No default? → ask user which tracker to use
  │
  └─ 7. Create issue via adapter
        ├─ Also create beads cross-reference (if beads configured)
        └─ Return issue URL/ID
```

## Routing Rules Examples

### Example 1: Bugs to GitLab, Agent Tasks to Beads

```yaml
issue_trackers:
  - name: gitlab
    type: gitlab
    project_id: "digital/web-sdk"
    default: true
    routing_rules:
      - match: { type: bug }
        action: { labels: [bug] }
      - match: { type: feature }
        action: { labels: [enhancement] }

  - name: beads
    type: beads
    scope: local
    routing_rules:
      - match: { source: agent }
        action: { default: true }     # Agent work stays local
      - match: { type: task }
        action: { default: true }     # Quick tasks stay local
```

### Example 2: Critical to Jira, Rest to GitHub

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

### Example 3: Cross-Project Issue

```
/relay:issue "API contract changed, update SDK" --project digital-web-sdk
```

When creating an issue for a different project than cwd:
1. Resolve target project from atlas
2. Route using target project's trackers (not current project's)
3. Include cross-reference to source project in issue body

## Beads Cross-References

When relay creates an issue in an external tracker, it optionally creates a beads reference:

```bash
bd create --type task \
  --title "External: Fix JWT refresh bug" \
  --description "Tracked in GitLab: https://git.example.com/project/-/issues/42" \
  --label external-ref
```

This allows `bd ready` and `bd list` to show external issues alongside local ones.

## Issue Fields Mapping

Relay uses a generic issue model that adapters map to tracker-specific fields:

| Relay Field | GitHub | GitLab | Jira | Beads |
|---|---|---|---|---|
| title | title | title | summary | title |
| description | body | description | description | description |
| type | label | label | issuetype | issue_type |
| priority | label (P0-P4) | label | priority | priority (0-4) |
| labels | labels[] | labels[] | labels[] | labels |
| assignee | assignees[] | assignee_ids[] | assignee | — |
| milestone | milestone | milestone_id | fixVersion | — |
| parent | — | — | parent (epic link) | dependency |
