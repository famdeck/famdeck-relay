# Relay Config Schema

The per-project config file `.claude/relay.yaml` lives in the project repository and defines which issue trackers the project uses.

## Schema

```yaml
# <project-root>/.claude/relay.yaml

issue_trackers:
  - name: <string>              # Unique name for this tracker entry (required)
    type: <string>              # github | gitlab | jira | beads (required)
    default: <boolean>          # Primary tracker for this project (optional, default: false)

    # Type-specific fields (one required based on type):
    repo: <string>              # GitHub: "org/repo-name"
    project_id: <string>        # GitLab: "group/project" (URL-encoded path)
    project_key: <string>       # Jira: "PROJ"
    scope: <string>             # Beads: "local" (always local)

    labels: [<string>, ...]     # Default labels applied to all issues (optional)

    routing_rules:              # Fine-grained routing (optional)
      - match:                  # ALL specified fields must match
          type: <string>        # bug | task | feature | chore
          priority: [<string>]  # [critical, high, medium, low] — array = any match
          source: <string>      # agent | human
          tags: [<string>]      # array = all must match
        action:
          default: true         # This tracker wins for this match (overrides tracker default)
          labels: [<string>]    # Additional labels to apply
          assignee: <string>    # Auto-assign to this user
```

## Field Definitions

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Unique identifier within the config. Used in `--tracker` flag. |
| `type` | Yes | Adapter type. Determines which tools/commands are used. |
| `default` | No | If `true`, this is the fallback tracker when no routing rule matches. Only one tracker should be default. |
| `repo` | GitHub only | Repository in `owner/name` format. |
| `project_id` | GitLab only | Project path (URL-encoded, e.g., `"digital/web-sdk"`). |
| `project_key` | Jira only | Jira project key (e.g., `"PROJ"`). |
| `scope` | Beads only | Always `"local"`. |
| `labels` | No | Default labels applied to every issue created in this tracker. |
| `routing_rules` | No | Ordered list of match/action rules. First match wins. |

## Examples

### Single tracker (simple)

```yaml
issue_trackers:
  - name: github
    type: github
    repo: "iVintik/clawrig"
    default: true
```

### GitLab + Beads (common pattern)

```yaml
issue_trackers:
  - name: gitlab
    type: gitlab
    project_id: "digital/web-sdk"
    default: true
    labels: [sdk, web]
    routing_rules:
      - match: { type: bug, priority: [critical, high] }
        action: { labels: [urgent], assignee: "@team-lead" }
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

### Jira + GitHub (escalation pattern)

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
