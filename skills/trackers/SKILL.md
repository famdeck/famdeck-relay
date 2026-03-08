---
name: trackers
description: Manage per-project issue tracker configuration in .claude/relay.yaml — show, initialize, add, or remove trackers. Use when the user wants to set up relay for a project, connect GitHub, GitLab, Jira, or beads, view current tracker config, or remove a tracker. Do NOT trigger for creating issues (use relay:issue) or viewing issue status (use relay:status).
argument-hint: "[show|init|add|remove <name>] [--project <slug>]"
allowed-tools: "ToolSearch,Bash(relay:*)"
---

# Relay Trackers

Manage tracker configuration.

## Primary: MCP tool

Load via ToolSearch (`search for "trackers"`) if not available, then call:

```
trackers(
  action="show",           # show|init|add|remove
  tracker_type="github",   # github|gitlab|jira|beads|auto (for init/add)
  name="NAME",             # for add/remove
  repo="owner/repo",       # GitHub
  project_id="grp/proj",   # GitLab
  project_key="PROJ",      # Jira
  set_default=false,
  no_beads=false,           # for init
  project="SLUG"
)
```

## Fallback: CLI

```bash
relay trackers [--project SLUG]                                    # show
relay trackers init [--type TYPE] [--no-beads] [--project SLUG]    # init
relay trackers add --type TYPE [--name N] [--repo O/R] [--project-id G/P] [--project-key K] [--set-default] [--project SLUG]
relay trackers remove --name NAME [--project SLUG]
```

Parse `$ARGUMENTS` and run the appropriate subcommand. Report results to user.
