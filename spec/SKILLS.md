# Relay — Skills Specification

## Skill: /relay:issue

**Purpose**: Create an issue in the right tracker based on project configuration and routing rules.

### Usage

```
/relay:issue "Fix JWT refresh token bug"
/relay:issue "Add dark mode support" --type feature
/relay:issue "Upgrade deps" --project digital-web-sdk --tracker gitlab
/relay:issue "Refactor auth module" --type task --priority high
```

### Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| title | Yes | — | Issue title (first positional argument) |
| `--project` | No | Current (from atlas) | Target project slug |
| `--tracker` | No | Auto-routed | Force specific tracker |
| `--type` | No | task | bug, task, feature, chore |
| `--priority` | No | medium | critical, high, medium, low |
| `--labels` | No | From routing rules | Comma-separated labels |
| `--assignee` | No | From routing rules | Assignee |
| `--body` | No | Interactive | Issue description/body |
| `--no-beads` | No | false | Skip beads cross-reference |

### Flow

1. Resolve project (atlas registry lookup, cwd detection, or `--project`)
2. Read `.claude/relay.yaml` from project path for tracker config
3. If `--tracker` specified → skip routing, use that tracker
4. Else → evaluate routing rules from `.claude/relay.yaml`
5. Determine adapter (gitlab/github/jira/beads)
6. Check adapter availability (MCP installed? CLI available?)
7. If `--body` not provided → ask user for description, or generate from context
8. Create issue via adapter
9. If beads tracker configured and not `--no-beads` → create beads cross-reference
10. Print: issue URL/ID, tracker used, labels applied

### Cross-Project Issues

When `--project` differs from cwd project:
- Issue body automatically includes "Created from: {current_project}" reference
- If both projects use beads → create linked beads issues in both

---

## Skill: /relay:handoff

**Purpose**: Capture current work context as a beads issue for later pickup.

### Usage

```
/relay:handoff                                  # Create handoff with auto-generated context
/relay:handoff --summary "JWT refresh done"     # Override summary
/relay:handoff --instructions "Focus on tests"  # Add instructions for recipient
```

### Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--summary` | No | Auto-generated | Work summary override |
| `--instructions` | No | None | Instructions for recipient |

### Flow

1. **Check prerequisites**: Verify `bd` CLI available
2. **Gather project context** from atlas + git state (branch, commit, uncommitted)
3. **Summarize work**: objective, decisions, next steps, files touched
4. **Gather active issues**: `bd list --status in_progress --status open`
5. **Create beads issue**: `bd create --type task --title "Handoff: {objective}" --label relay:handoff --label "handoff:from:{user}" --label "handoff:branch:{branch}"` with structured markdown description
6. **Confirm**: Print issue ID, branch, objective

### Description Format

See `knowledge/handoff-protocol.md` for the structured markdown format (Objective, Branch, Summary, Decisions, Next Steps, Active Issues, Files Touched, Blockers, Notes).

---

## Skill: /relay:pickup

**Purpose**: Resume work from a handoff beads issue.

### Usage

```
/relay:pickup                                   # List and select pending handoffs
/relay:pickup bd-abc123                         # Resume specific handoff
/relay:pickup --list                            # Just list, don't pick up
```

### Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| issue_id | No | Interactive | Specific beads issue to resume |
| `--list` | No | false | List only, don't pick up |

### Flow

1. **Check prerequisites**: Verify `bd` CLI available
2. **List handoffs**: `bd list --label relay:handoff --status open`
3. **Display table**: ID, title, from (label), branch (label)
4. **Select**: User picks handoff (or specified via argument)
5. **Restore context**: `bd show {id}` — parse and display structured sections
6. **Check branch**: Compare current branch with handoff's branch label
7. **Mark picked up**: `bd update {id} --status in_progress`
8. **Ready**: Print next steps and remind to `bd close {id}` when done

---

## Skill: /relay:status

**Purpose**: Cross-project issue dashboard showing issues across all trackers.

### Usage

```
/relay:status                                   # Current project's issues
/relay:status --all                             # All projects
/relay:status --project digital-web-sdk         # Specific project
/relay:status --tracker gitlab                  # Filter by tracker type
```

### Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--all` | No | false | Show all registered projects |
| `--project` | No | Current | Specific project |
| `--tracker` | No | All | Filter by tracker type |
| `--status` | No | open | open, closed, all |
| `--limit` | No | 20 | Max issues per tracker |

### Flow

1. Resolve project(s) from atlas registry
2. For each project, read `.claude/relay.yaml` for tracker list
3. For each tracker:
   - Query issues via adapter
   - Collect results
3. Merge and display as unified table:

```
digital-web-sdk
  GitLab (default):
    #42  [bug]     JWT refresh broken after 24h          @dev-team   open
    #38  [feature] Add retry logic to API calls          @ivintik    open

  Beads (local):
    bd-x1y2  [task]  Implement token rotation            in_progress
    bd-y3z4  [task]  Update auth docs                    open (blocked by bd-x1y2)

clawrig
  GitHub:
    #12  [feature] Add project-ref MCP health check      open
    #10  [bug]     Session cleanup on timeout             open
```

### Performance

- Queries run in parallel across trackers
- Cache results for 5 minutes (avoid hammering APIs)
- Show stale indicator if cached data is old

---

## Skill: /relay:trackers

**Purpose**: Manage the per-project issue tracker configuration (`.claude/relay.yaml`).

### Usage

```
/relay:trackers                                 # Show current project's tracker config
/relay:trackers init                            # Create .claude/relay.yaml for current project
/relay:trackers add                             # Add a tracker to current project
/relay:trackers remove gitlab                   # Remove a tracker
/relay:trackers --project digital-web-sdk       # Show another project's config
```

### Subcommands

#### `show` (default)

Display the current project's `.claude/relay.yaml` in a readable format:

```
digital-web-sdk — Issue Trackers:
  1. gitlab (default) — project: digital/web-sdk — labels: sdk, web
     Rules: bugs+critical → @team-lead +urgent
  2. beads (local)
     Rules: agent tasks → beads, quick tasks → beads
```

#### `init`

Create `.claude/relay.yaml` if it doesn't exist:

1. Detect repo host from `.git/config` (or atlas)
2. Suggest primary tracker:
   - `github.com` → github adapter, repo auto-detected
   - `gitlab.*` → gitlab adapter, project_id auto-detected
   - Otherwise → ask
3. Ask: "Also track local/agent work in beads?" → add beads tracker
4. Write `.claude/relay.yaml` to project repo

#### `add`

Add a new tracker interactively:

1. Ask tracker type (github, gitlab, jira, beads)
2. Ask tracker-specific config (project_id, repo, project_key)
3. Ask for default labels
4. Ask about routing rules
5. Append to `.claude/relay.yaml`

#### `remove`

Remove a tracker by name from `.claude/relay.yaml`.
