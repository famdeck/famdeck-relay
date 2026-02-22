# Relay — Issue Routing

## Routing Overview

When a user creates an issue via relay, the routing engine determines which tracker receives it. The decision is based on the project's `.claude/relay.yaml` — a config file that lives in the project repo and defines which trackers the project uses.

## Per-Project Config

```yaml
# <project-root>/.claude/relay.yaml

issue_trackers:
  - name: gitlab
    type: gitlab                          # gitlab | github | jira | beads
    project_id: "digital/web-sdk"         # Tracker-specific project reference
    default: true                         # Primary tracker for this project
    labels: [sdk, web]                    # Default labels on new issues
    routing_rules:                        # Fine-grained routing (optional)
      - match:
          type: bug
          priority: [critical, high]
        action:
          labels: [urgent]
          assignee: "@team-lead"

  - name: beads
    type: beads
    scope: local
    routing_rules:
      - match: { source: agent }
        action: { default: true }
```

## Routing Decision Tree

```
/relay:issue "Fix JWT refresh bug" [--project X] [--tracker Y] [--type bug]
  │
  ├─ 1. Resolve project
  │     ├─ Explicit --project flag → look up in atlas registry → get path
  │     ├─ Atlas cwd detection → current project
  │     └─ No atlas / no match → use cwd, check for .claude/relay.yaml directly
  │
  ├─ 2. Read .claude/relay.yaml from project path
  │     ├─ Found → load issue_trackers config
  │     └─ Missing → ask user which tracker to use (offer to create config)
  │
  ├─ 3. Explicit --tracker?
  │     ├─ --tracker gitlab → use that tracker from config, skip routing rules
  │     └─ No → continue to routing rules
  │
  ├─ 4. Evaluate routing rules (in order, across all trackers)
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
        ├─ Also create beads cross-reference (if beads tracker configured)
        └─ Return issue URL/ID
```

## Config Examples

### Example 1: Bugs to GitLab, Agent Tasks to Beads

```yaml
# .claude/relay.yaml
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
        action: { default: true }
      - match: { type: task }
        action: { default: true }
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

### Example 3: Single Tracker (Simple)

```yaml
issue_trackers:
  - name: github
    type: github
    repo: "iVintik/clawrig"
    default: true
```

## Cross-Project Issues

```
/relay:issue "API contract changed, update SDK" --project digital-web-sdk
```

When creating an issue for a different project than cwd:
1. Resolve target project path via atlas registry
2. Read target project's `.claude/relay.yaml`
3. Route using target project's trackers (not current project's)
4. Include cross-reference to source project in issue body

## Beads Cross-References

When relay creates an issue in an external tracker, it optionally creates a beads reference:

```bash
bd create --type task \
  --title "External: Fix JWT refresh bug" \
  --description "Tracked in GitLab: https://git.example.com/project/-/issues/42" \
  --label external-ref
```

This allows `bd ready` and `bd list` to show external issues alongside local ones.

Condition: beads cross-referencing only happens if the project's `.claude/relay.yaml` includes a `type: beads` tracker entry.

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

## Relay Config Initialization

```
/relay:trackers init
```

If `.claude/relay.yaml` doesn't exist, relay offers to create one:
1. Check repo type from `.git/config` (or atlas)
2. Suggest default tracker based on repo host:
   - `github.com` → github adapter
   - `gitlab.*` → gitlab adapter
   - Otherwise → ask
3. Ask about additional trackers (beads for local work?)
4. Write `.claude/relay.yaml`
