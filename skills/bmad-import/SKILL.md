---
name: bmad-import
description: "Import BMAD story and epic artifacts into Beads as trackable issues with dependencies. Use when the user says 'import stories', 'sync BMAD into Beads', 'import epics', or when Beads has no issues but sprint-status.yaml has backlog stories. Shows a dry-run plan before applying. Can filter by specific epic."
---

# BMAD Story Import

BMAD produces planning artifacts (epics, stories in sprint-status.yaml) but those aren't tracked as issues. This skill bridges the gap — it reads the BMAD plan and creates corresponding Beads issues with proper dependencies, so work can be picked up, assigned, and tracked.

## Step 1: Preview (always dry-run first)

```bash
python -c "
from famdeck.bmad_import.importer import import_stories
result = import_stories('$PWD', dry_run=True)
print(result.summary())
"
```

Show the plan to the user — which stories will be created, under which epics, with what dependencies. Wait for confirmation before applying.

## Step 2: Apply

```bash
python -c "
from famdeck.bmad_import.importer import import_stories
result = import_stories('$PWD')
print(result.summary())
"
```

## Importing a specific epic

To import only stories from one epic (e.g., epic 1):

```bash
python -c "
from famdeck.bmad_import.importer import import_stories
result = import_stories('$PWD', epic_filter=1)
print(result.summary())
"
```

## When to use

- After creating new epics or stories in BMAD planning
- When `bd list` shows no issues but `sprint-status.yaml` has backlog stories
- When the `/autopilot` pre-flight detects missing Beads issues
