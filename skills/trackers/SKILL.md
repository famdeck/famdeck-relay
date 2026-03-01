---
name: trackers
description: Manage per-project issue tracker configuration — show, initialize, add, or remove trackers in .claude/relay.yaml. Use when setting up relay for a project, viewing tracker config, adding new trackers, or managing routing rules.
argument-hint: "[show|init|add|remove <name>] [--project <slug>]"
allowed-tools: "ToolSearch,Bash(relay:*)"
---

# Relay Trackers

Manage tracker configuration.

## Primary: MCP tool

Call the `trackers` MCP tool directly:

```
trackers(
  action="show",         # show|init|add|remove
  tracker_type="github", # github|gitlab|jira|beads|auto (for init/add)
  name="NAME",           # tracker name (for add/remove)
  repo="owner/repo",     # GitHub repo (for add --type github)
  project_id="grp/proj", # GitLab project (for add --type gitlab)
  project_key="PROJ",    # Jira key (for add --type jira)
  set_default=false,     # make default (for add)
  no_beads=false,        # skip beads (for init)
  project="SLUG"         # optional: atlas project slug
)
```

Load it via ToolSearch if not already available: search for `trackers`.

## Fallback: CLI

**Show** (default):
```bash
relay trackers [--project SLUG]
```

**Initialize** new config:
```bash
relay trackers init [--type github|gitlab|jira|beads|auto] [--no-beads] [--project SLUG]
```

**Add** a tracker:
```bash
relay trackers add --type TYPE [--name NAME] [--repo OWNER/REPO] [--project-id GROUP/PROJECT] [--project-key PROJ] [--set-default] [--project SLUG]
```

**Remove** a tracker:
```bash
relay trackers remove --name NAME [--project SLUG]
```

Parse `$ARGUMENTS` and run the appropriate command. Report results to user.
