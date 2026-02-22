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

1. Resolve project (atlas lookup or `--project`)
2. If `--tracker` specified → skip routing, use that tracker
3. Else → evaluate routing rules from project config
4. Determine adapter (gitlab/github/jira/beads)
5. Check adapter availability (MCP installed? CLI available?)
6. If `--body` not provided → ask user for description, or generate from context
7. Create issue via adapter
8. If beads configured and not `--no-beads` → create beads cross-reference
9. Print: issue URL/ID, tracker used, labels applied

### Cross-Project Issues

When `--project` differs from cwd project:
- Issue body automatically includes "Created from: {current_project}" reference
- If both projects use beads → create linked beads issues in both

---

## Skill: /relay:handoff

**Purpose**: Serialize current work context and transfer to another session, tool, or person.

### Usage

```
/relay:handoff                                  # Interactive: choose target
/relay:handoff --to clawrig                     # Transfer to ClawRig session
/relay:handoff --to person:colleague@email.com  # Hand off to a person
/relay:handoff --to agent:task-agent            # Delegate to autonomous agent
/relay:handoff --to self                        # Save for self (cross-machine)
/relay:handoff --save-only                      # Just save envelope, don't transfer
```

### Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--to` | No | Interactive | Target: clawrig, person:{id}, agent:{name}, self |
| `--summary` | No | Auto-generated | Work summary override |
| `--include-diff` | No | true | Include git diff in envelope |
| `--include-beads` | No | true | Include beads export |
| `--save-only` | No | false | Save but don't transfer |
| `--instructions` | No | None | Instructions for recipient |

### Flow

1. **Gather project context** from atlas
2. **Gather git state**: branch, commit, `git diff` (staged + unstaged)
3. **Gather beads state**: `bd list --status in_progress`, export related issues
4. **Summarize work**: Ask Claude to produce summary, decisions, next steps
5. **Build envelope**: Assemble all context into handoff JSON
6. **Transfer**: Based on `--to` target type
7. **Confirm**: Print handoff ID, summary, transfer status

### Interactive Mode (no `--to`)

Present options:
1. Continue in ClawRig/OpenClaw
2. Transfer to another machine (self)
3. Hand off to a colleague
4. Delegate to an agent
5. Just save for later

---

## Skill: /relay:pickup

**Purpose**: Resume work from a handoff envelope.

### Usage

```
/relay:pickup                                   # List and select pending handoffs
/relay:pickup hf-a1b2c3d4                       # Resume specific handoff
/relay:pickup --list                            # Just list, don't pick up
```

### Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| handoff_id | No | Interactive | Specific handoff to resume |
| `--list` | No | false | List only, don't pick up |
| `--apply-diff` | No | ask | Apply git diff from envelope |
| `--import-beads` | No | ask | Import beads issues |

### Flow

1. **Discover handoffs**: Scan `~/.claude/relay/handoffs/` for pending envelopes
2. **If git sync**: Pull latest from handoffs repo
3. **List pending**: Show summary table (ID, project, summary, from, age)
4. **Select**: User picks handoff (or specified via argument)
5. **Check project**: Is cwd the right project? If not, suggest `cd`
6. **Check branch**: Is the right branch checked out? Offer to switch
7. **Restore context**: Print full context (summary, decisions, next steps, blockers)
8. **Apply artifacts**:
   - Git diff → offer to apply (`git apply`)
   - Beads JSONL → offer to import (`bd import`)
9. **Mark picked up**: Update envelope status
10. **Ready**: Session now has full context to continue work

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

1. Resolve project(s) from atlas
2. For each project's configured trackers:
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
