# Routing Rules

Issue routing determines which tracker receives an issue based on the project's `.claude/relay.yaml` configuration.

## Decision Tree

```
/relay:issue "title" [--project X] [--tracker Y] [--type T] [--priority P]
  │
  ├─ 1. Resolve project
  │     ├─ Explicit --project flag → atlas registry lookup → get path
  │     ├─ Atlas cwd detection → current project
  │     └─ No atlas / no match → use cwd, check .claude/relay.yaml directly
  │
  ├─ 2. Read .claude/relay.yaml from project path
  │     ├─ Found → load issue_trackers config
  │     └─ Missing → ask user which tracker to use (offer to create config)
  │
  ├─ 3. Explicit --tracker?
  │     ├─ Yes → use that tracker from config, skip routing rules
  │     └─ No → continue to routing rules
  │
  ├─ 4. Evaluate routing rules (in order, across all trackers)
  │     │
  │     │  For each tracker's routing_rules (evaluated in config order):
  │     │    match:
  │     │      type: bug|task|feature|chore     # Issue type filter
  │     │      priority: [critical, high]       # Priority filter (array = any)
  │     │      source: agent|human              # Who's creating
  │     │      tags: [frontend]                 # Tag filter
  │     │    action:
  │     │      default: true                    # This tracker wins
  │     │      labels: [urgent]                 # Extra labels to add
  │     │      assignee: "@user"                # Auto-assign
  │     │
  │     ├─ Rule matches → use that tracker + apply actions
  │     └─ No rules match → continue
  │
  ├─ 5. Fall back to default tracker (default: true on tracker entry)
  │
  ├─ 6. No default? → ask user which tracker to use
  │
  └─ 7. Create issue via adapter
        ├─ Also create beads cross-reference (if beads tracker configured)
        └─ Return issue URL/ID
```

## Match Semantics

A rule matches when ALL specified match fields are satisfied:

- **type**: Exact match. `type: bug` matches only bugs.
- **priority**: Array = any match. `priority: [critical, high]` matches either.
- **source**: `agent` if issue created during autonomous agent work, `human` otherwise.
- **tags**: Array = all must match. `tags: [frontend, urgent]` requires both.

Fields not specified in a match are wildcards (match anything).

## Action Semantics

When a rule matches, its action is applied:

- **default: true** — This tracker receives the issue (overrides the tracker-level default).
- **labels** — Merged with tracker-level default labels and user-specified labels.
- **assignee** — Sets assignee. User-specified `--assignee` takes precedence.

## Rule Evaluation Order

1. Rules are evaluated per-tracker, in the order trackers appear in config.
2. Within a tracker, rules are evaluated top-to-bottom.
3. **First match wins** — once a rule matches, evaluation stops.
4. If a matching rule has `action.default: true`, that tracker wins regardless of tracker-level `default`.
5. If a matching rule has no `action.default: true`, the matched tracker's actions (labels, assignee) are applied but routing falls through to the tracker-level default.

## Examples

### Bug routed to GitLab with extra labels

```yaml
# Config:
issue_trackers:
  - name: gitlab
    type: gitlab
    project_id: "digital/web-sdk"
    default: true
    routing_rules:
      - match: { type: bug, priority: [critical, high] }
        action: { labels: [urgent], assignee: "@team-lead" }
```

`/relay:issue "Crash on login" --type bug --priority critical` →
- Tracker: gitlab (match + default)
- Labels: urgent (from rule)
- Assignee: @team-lead (from rule)

### Agent task routed to beads

```yaml
issue_trackers:
  - name: gitlab
    type: gitlab
    project_id: "digital/web-sdk"
    default: true
  - name: beads
    type: beads
    routing_rules:
      - match: { source: agent }
        action: { default: true }
```

Issue created during agent work →
- Tracker: beads (match with `default: true` overrides gitlab's tracker-level default)
