# Beads Integration

Relay optionally creates beads cross-references when issues are created in external trackers (GitHub, GitLab, Jira). This keeps external issues visible in `bd list` and `bd ready`.

## When to Create Cross-References

Create a beads cross-reference **only when**:
1. The project's `.claude/relay.yaml` includes a `type: beads` tracker entry
2. The issue is being created in a non-beads tracker
3. The user hasn't passed `--no-beads`

## Cross-Reference Command

```bash
bd create --type task \
  --title "External: {original_title}" \
  --description "Tracked in {tracker_name}: {issue_url_or_id}\n\nOriginal description: {description}" \
  --label external-ref
```

The `external-ref` label distinguishes cross-references from native beads issues.

## Cross-Reference in Handoffs

When exporting beads state for a handoff:
```bash
bd export --format jsonl > /tmp/beads-export.jsonl
```

When importing on pickup:
```bash
bd import /tmp/beads-export.jsonl
```

Dependencies between beads issues are preserved in the export/import cycle.

## When Beads Is Not Available

If beads (`bd` CLI) is not installed:
- Skip cross-reference creation silently
- Note in output: "Beads not available — skipping cross-reference. Install with: /toolkit:toolkit-setup"
- The issue is still created in the target tracker normally

If beads is installed but the project has no `type: beads` tracker entry:
- Skip cross-reference creation (no beads tracker configured for this project)
- No warning needed — this is an intentional configuration choice
