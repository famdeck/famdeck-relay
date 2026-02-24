---
name: trackers
description: Manage per-project issue tracker configuration — show, initialize, add, or remove trackers in .claude/relay.yaml. Use when setting up relay for a project, viewing tracker config, adding new trackers, or managing routing rules.
argument-hint: "[show|init|add|remove <name>] [--project <slug>]"
allowed-tools: "Bash(relay:*)"
---

# Relay Trackers

Manage tracker configuration via the `relay` CLI.

## Commands

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
