#!/usr/bin/env python3
"""Relay CLI — issue routing, handoffs, and tracker management."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .config import (
    find_project_path, find_project_slug, read_config, write_config,
    get_trackers, get_default_tracker, get_tracker_by_name, get_defaults,
    detect_repo_type, init_config, _iter_atlas_projects,
)
from .routing import evaluate_rules, priority_to_number
from .adapters import check_adapter, create_issue, list_issues
from .importer import import_bmad_stories
from .sync import sync_statuses, check_desync


def out(data: dict, fmt: str = "json"):
    """Output result in requested format."""
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_text(data)


def _print_text(data: dict):
    """Human-readable output."""
    status = data.get("status", "")
    if status == "error":
        print(f"Error: {data.get('message', 'unknown')}", file=sys.stderr)
        return
    if status == "needs_mcp":
        print(f"MCP call required: {data.get('tool')}")
        print(f"Params: {json.dumps(data.get('params', {}), indent=2)}")
        return
    # Generic: print all keys
    for k, v in data.items():
        if k == "status":
            continue
        if isinstance(v, (dict, list)):
            print(f"{k}: {json.dumps(v, indent=2, ensure_ascii=False)}")
        else:
            print(f"{k}: {v}")


# --- Subcommands ---

def cmd_prime(args):
    """Output context block for Claude session injection."""
    project_path = find_project_path(args.project)
    slug = find_project_slug(project_path) or project_path.name
    config = read_config(project_path)

    lines = [f"# Relay — {slug}", ""]

    if not config:
        lines.append("No tracker config for this project. Run `/relay:trackers init` to set up.")
        lines.append("To file issues in OTHER projects: /relay:issue \"title\" --project <slug>")
        print("\n".join(lines))
        return

    trackers = get_trackers(config)
    lines.append("## Trackers")
    for i, t in enumerate(trackers, 1):
        default = " (default)" if t.get("default") else ""
        tid = t.get("repo") or t.get("project_id") or t.get("project_key") or t.get("scope", "")
        lines.append(f"  {i}. {t['name']} ({t['type']}{default}) — {tid}")
        for rule in t.get("routing_rules", []):
            m = rule.get("match", {})
            a = rule.get("action", {})
            match_str = ", ".join(f"{k}={v}" for k, v in m.items())
            action_str = ", ".join(f"{k}={v}" for k, v in a.items())
            lines.append(f"     Rule: {match_str} → {action_str}")

    lines.append("")
    lines.append("## When to create issues")
    lines.append("  When you discover a bug or problem in ANY project (not just the current one),")
    lines.append("  use /relay:issue to file it. Use --project <slug> for cross-project issues.")
    lines.append("  Do NOT silently fix problems without tracking — file an issue first or alongside the fix.")
    lines.append("")
    lines.append("## Commands")
    lines.append("  relay issue \"title\" [--type bug|task|feature|chore] [--priority critical|high|medium|low] [--body \"...\"] [--project <slug>]")
    lines.append("  relay route \"title\" --type bug --priority high  (dry-run, shows which tracker)")
    lines.append("  relay trackers [show|init|add|remove]")
    lines.append("  relay status [--all]")
    lines.append("  relay handoff [--summary \"...\"]")
    lines.append("  relay pickup [issue_id]")

    print("\n".join(lines))


def cmd_issue(args):
    """Route and create an issue."""
    project_path = find_project_path(args.project)
    config = read_config(project_path)
    if not config:
        out({"status": "error", "message": f"No relay config at {project_path}/.claude/relay.yaml. Run: relay trackers init"}, args.format)
        sys.exit(1)

    # Explicit tracker override
    if args.tracker:
        tracker = get_tracker_by_name(config, args.tracker)
        if not tracker:
            names = [t["name"] for t in get_trackers(config)]
            out({"status": "error", "message": f"Tracker '{args.tracker}' not found. Available: {names}"}, args.format)
            sys.exit(1)
        labels = list(set((tracker.get("labels", []) or []) + (args.labels or [])))
        assignee = args.assignee
    else:
        # Route via rules
        issue_ctx = {
            "type": args.type,
            "priority": args.priority,
            "source": args.source or "human",
            "labels": args.labels or [],
            "assignee": args.assignee,
        }
        route = evaluate_rules(config, issue_ctx)
        tracker = route["tracker"]
        labels = route["labels"]
        assignee = route["assignee"]

    if not tracker:
        out({"status": "error", "message": "No tracker matched and no default configured"}, args.format)
        sys.exit(1)

    # Check adapter
    adapter_check = check_adapter(tracker["type"])
    if not adapter_check["available"]:
        out({"status": "error", "message": f"Adapter unavailable: {adapter_check['install_hint']}"}, args.format)
        sys.exit(1)

    # Create issue
    result = create_issue(
        tracker=tracker,
        title=args.title,
        body=args.body or "",
        issue_type=args.type,
        priority=args.priority,
        labels=labels,
        assignee=assignee,
    )

    # Add routing context to result
    result["tracker_name"] = tracker["name"]
    result["tracker_type"] = tracker["type"]

    # Beads cross-reference (if created in non-beads tracker)
    if result.get("status") == "ok" and tracker["type"] != "beads" and not args.no_beads:
        _maybe_beads_xref(config, args.title, result, tracker)

    out(result, args.format)

    if result.get("status") == "error":
        sys.exit(1)


def _maybe_beads_xref(config, title, result, source_tracker):
    """Create beads cross-reference issue if beads tracker is configured."""
    beads_tracker = None
    for t in get_trackers(config):
        if t["type"] == "beads":
            beads_tracker = t
            break
    if not beads_tracker:
        return

    import shutil
    if not shutil.which("bd"):
        return

    issue_ref = result.get("stdout", result.get("id", "unknown"))
    xref_body = f"Tracked in {source_tracker['name']}: {issue_ref}"
    try:
        subprocess.run(
            ["bd", "create", f"External: {title}", "--type", "task",
             "--description", xref_body, "--label", "external-ref"],
            capture_output=True, text=True, timeout=15
        )
        result["beads_xref"] = True
    except Exception:
        pass


def cmd_route(args):
    """Dry-run routing — show which tracker would be chosen."""
    project_path = find_project_path(args.project)
    config = read_config(project_path)
    if not config:
        out({"status": "error", "message": "No relay config found"}, args.format)
        sys.exit(1)

    issue_ctx = {
        "type": args.type,
        "priority": args.priority,
        "source": args.source or "human",
        "labels": args.labels or [],
    }
    route = evaluate_rules(config, issue_ctx)
    tracker = route["tracker"]

    result = {
        "status": "ok",
        "action": "route_dry_run",
        "tracker_name": tracker["name"] if tracker else None,
        "tracker_type": tracker["type"] if tracker else None,
        "labels": route["labels"],
        "assignee": route["assignee"],
        "matched_rule": route["matched_rule"],
    }

    # Check adapter availability
    if tracker:
        adapter_check = check_adapter(tracker["type"])
        result["adapter_available"] = adapter_check["available"]
        if not adapter_check["available"]:
            result["adapter_hint"] = adapter_check["install_hint"]

    out(result, args.format)


def cmd_trackers(args):
    """Manage tracker configuration."""
    project_path = find_project_path(args.project)

    if args.action == "init":
        config = read_config(project_path)
        if config:
            out({"status": "error", "message": "Config already exists. Use 'show' to view, 'add' to add trackers."}, args.format)
            sys.exit(1)
        config = init_config(project_path, args.tracker_type, add_beads=not args.no_beads)
        result = {
            "status": "ok",
            "action": "init",
            "path": str(project_path / ".claude" / "relay.yaml"),
            "trackers": [{"name": t["name"], "type": t["type"]} for t in get_trackers(config)],
        }
        out(result, args.format)

    elif args.action == "show" or args.action is None:
        config = read_config(project_path)
        if not config:
            out({"status": "error", "message": f"No relay config. Run: relay trackers init"}, args.format)
            sys.exit(1)
        slug = find_project_slug(project_path) or project_path.name
        trackers = []
        for t in get_trackers(config):
            entry = {
                "name": t["name"],
                "type": t["type"],
                "default": t.get("default", False),
            }
            for field in ("repo", "project_id", "project_key", "scope"):
                if field in t:
                    entry[field] = t[field]
            if t.get("labels"):
                entry["labels"] = t["labels"]
            if t.get("routing_rules"):
                entry["rules"] = len(t["routing_rules"])
            trackers.append(entry)

        result = {"status": "ok", "project": slug, "path": str(project_path), "trackers": trackers}
        out(result, args.format)

    elif args.action == "add":
        config = read_config(project_path)
        if not config:
            out({"status": "error", "message": "No config. Run 'init' first."}, args.format)
            sys.exit(1)

        if not args.tracker_type:
            out({"status": "error", "message": "Specify --type (github|gitlab|jira|beads)"}, args.format)
            sys.exit(1)

        name = args.name or args.tracker_type
        entry = {"name": name, "type": args.tracker_type}

        if args.tracker_type == "github":
            detected = detect_repo_type(project_path)
            entry["repo"] = args.repo or (detected["repo"] if detected and detected["type"] == "github" else "owner/repo")
        elif args.tracker_type == "gitlab":
            detected = detect_repo_type(project_path)
            entry["project_id"] = args.project_id or (detected["project_id"] if detected and detected["type"] == "gitlab" else "group/project")
        elif args.tracker_type == "jira":
            entry["project_key"] = args.project_key or "PROJ"
        elif args.tracker_type == "beads":
            entry["scope"] = "local"

        if args.set_default:
            # Remove default from others
            for t in config["issue_trackers"]:
                t.pop("default", None)
            entry["default"] = True

        config["issue_trackers"].append(entry)
        write_config(project_path, config)
        out({"status": "ok", "action": "add", "tracker": entry}, args.format)

    elif args.action == "remove":
        config = read_config(project_path)
        if not config:
            out({"status": "error", "message": "No config."}, args.format)
            sys.exit(1)
        if not args.name:
            out({"status": "error", "message": "Specify tracker name to remove"}, args.format)
            sys.exit(1)

        trackers = config.get("issue_trackers", [])
        found = [t for t in trackers if t["name"] == args.name]
        if not found:
            names = [t["name"] for t in trackers]
            out({"status": "error", "message": f"Tracker '{args.name}' not found. Available: {names}"}, args.format)
            sys.exit(1)

        config["issue_trackers"] = [t for t in trackers if t["name"] != args.name]
        write_config(project_path, config)
        out({"status": "ok", "action": "remove", "removed": args.name}, args.format)


def cmd_status(args):
    """Show issues across configured trackers."""
    if args.all:
        # Get all projects from atlas
        atlas_projects = _iter_atlas_projects()
        if not atlas_projects:
            out({"status": "error", "message": "Atlas not installed. Use --project or run from project dir."}, args.format)
            sys.exit(1)
        projects = [(slug, Path(info["path"]).expanduser()) for slug, info in atlas_projects]
    else:
        project_path = find_project_path(args.project)
        slug = find_project_slug(project_path) or project_path.name
        projects = [(slug, project_path)]

    results = []
    for slug, path in projects:
        config = read_config(path)
        if not config:
            results.append({"project": slug, "status": "no_config"})
            continue

        trackers_data = []
        for tracker in get_trackers(config):
            if args.tracker and tracker["name"] != args.tracker:
                continue
            adapter_check = check_adapter(tracker["type"])
            if not adapter_check["available"]:
                trackers_data.append({
                    "name": tracker["name"], "type": tracker["type"],
                    "status": "adapter_unavailable", "hint": adapter_check["install_hint"]
                })
                continue

            result = list_issues(tracker, status=args.status, limit=args.limit)
            trackers_data.append({
                "name": tracker["name"],
                "type": tracker["type"],
                "default": tracker.get("default", False),
                **result,
            })

        results.append({"project": slug, "trackers": trackers_data})

    out({"status": "ok", "projects": results}, args.format)


def cmd_handoff(args):
    """Create a handoff beads issue."""
    import shutil
    if not shutil.which("bd"):
        out({"status": "error", "message": "Beads CLI required. Install with /famdeck-toolkit:toolkit-setup"}, args.format)
        sys.exit(1)

    project_path = find_project_path(args.project)
    slug = find_project_slug(project_path) or project_path.name

    # Gather git state
    git_info = _gather_git_info(project_path)

    # Build description
    summary = args.summary or f"Work handoff from {slug}"
    instructions = args.instructions or ""

    description = f"""## Objective
{summary}

## Branch
{git_info['branch']} @ {git_info['commit']} (uncommitted: {'yes' if git_info['dirty'] else 'no'})

## Files Changed
{git_info['files_changed'] or 'None'}

## Notes
{instructions or 'None'}
"""

    # Create beads issue
    cmd = [
        "bd", "create", f"Handoff: {summary}",
        "--type", "task",
        "--description", description,
        "--label", "relay:handoff",
        "--label", f"handoff:branch:{git_info['branch']}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=str(project_path))

    if result.returncode == 0:
        out({
            "status": "ok",
            "action": "handoff_created",
            "project": slug,
            "branch": git_info["branch"],
            "commit": git_info["commit"],
            "stdout": result.stdout.strip(),
        }, args.format)
    else:
        out({"status": "error", "message": result.stderr.strip() or result.stdout.strip()}, args.format)
        sys.exit(1)


def cmd_pickup(args):
    """List or restore from handoff."""
    import shutil
    if not shutil.which("bd"):
        out({"status": "error", "message": "Beads CLI required."}, args.format)
        sys.exit(1)

    project_path = find_project_path(args.project)

    if args.list or not args.issue_id:
        # List handoffs
        result = subprocess.run(
            ["bd", "list", "--label", "relay:handoff", "--status", "open"],
            capture_output=True, text=True, timeout=15, cwd=str(project_path)
        )
        out({
            "status": "ok",
            "action": "list_handoffs",
            "stdout": result.stdout.strip(),
        }, args.format)
        return

    # Show specific handoff
    result = subprocess.run(
        ["bd", "show", args.issue_id],
        capture_output=True, text=True, timeout=15, cwd=str(project_path)
    )
    if result.returncode != 0:
        out({"status": "error", "message": result.stderr.strip() or f"Issue {args.issue_id} not found"}, args.format)
        sys.exit(1)

    # Mark as in_progress
    subprocess.run(
        ["bd", "update", args.issue_id, "--status", "in_progress"],
        capture_output=True, text=True, timeout=15, cwd=str(project_path)
    )

    out({
        "status": "ok",
        "action": "pickup",
        "issue_id": args.issue_id,
        "content": result.stdout.strip(),
    }, args.format)


def _gather_git_info(project_path: Path) -> dict:
    """Collect git branch, commit, dirty state, changed files."""
    def git(*cmd_args):
        try:
            r = subprocess.run(
                ["git", "-C", str(project_path)] + list(cmd_args),
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip()
        except Exception:
            return ""

    branch = git("branch", "--show-current") or "unknown"
    commit = git("rev-parse", "--short", "HEAD") or "unknown"
    porcelain = git("status", "--porcelain")
    files = git("diff", "--name-status", "HEAD")

    return {
        "branch": branch,
        "commit": commit,
        "dirty": bool(porcelain),
        "files_changed": files or None,
    }


def cmd_sync(args):
    """Sync BMAD ↔ Beads statuses."""
    project_path = find_project_path(args.project)
    config = read_config(project_path) or {}
    defaults = get_defaults(config)

    if args.check:
        result = check_desync(project_path, config_defaults=defaults)
        data = {"status": "ok", "action": "check", **result.to_dict()}
        if result.desynced:
            data["status"] = "desynced"
        if result.errors:
            data["status"] = "error"
        out(data, args.format)
        if result.desynced or result.errors:
            sys.exit(1)
        return

    result = sync_statuses(
        project_path=project_path,
        direction=args.direction,
        dry_run=args.dry_run,
        alert_conflicts=args.alert_conflicts,
        config_defaults=defaults,
    )
    data = {"status": "ok", "action": "sync", **result.to_dict()}
    if result.errors:
        data["status"] = "partial" if result.bmad_to_beads or result.beads_to_bmad else "error"
    if result.conflicts:
        data["status"] = "conflicts"
    out(data, args.format)


def cmd_import(args):
    """Import BMAD stories into Beads."""
    project_path = find_project_path(args.project)
    config = read_config(project_path) or {}
    defaults = get_defaults(config)
    result = import_bmad_stories(
        project_path=project_path,
        dry_run=args.dry_run,
        epic_filter=args.epic,
        config_defaults=defaults,
    )
    data = {"status": "ok", "action": "import", **result.to_dict()}
    if result.errors:
        data["status"] = "partial" if result.created or result.updated else "error"
    out(data, args.format)
    if data["status"] == "error":
        sys.exit(1)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(prog="relay", description="Relay CLI — issue routing and handoffs")
    parser.add_argument("--format", "-f", choices=["json", "text"], default="json", help="Output format")
    parser.add_argument("--project", "-p", help="Project slug or path")
    sub = parser.add_subparsers(dest="command")

    # prime
    sub.add_parser("prime", help="Output session context")

    # issue
    p_issue = sub.add_parser("issue", help="Create and route an issue")
    p_issue.add_argument("title", help="Issue title")
    p_issue.add_argument("--type", "-t", default="task", choices=["bug", "task", "feature", "chore"])
    p_issue.add_argument("--priority", default="medium", choices=["critical", "high", "medium", "low"])
    p_issue.add_argument("--body", "-b", default="", help="Issue description")
    p_issue.add_argument("--labels", "-l", nargs="*", default=[], help="Extra labels")
    p_issue.add_argument("--assignee", "-a", help="Assignee")
    p_issue.add_argument("--tracker", help="Force specific tracker by name")
    p_issue.add_argument("--source", default="human", choices=["human", "agent"])
    p_issue.add_argument("--no-beads", action="store_true", help="Skip beads cross-reference")

    # route (dry-run)
    p_route = sub.add_parser("route", help="Dry-run routing")
    p_route.add_argument("title", nargs="?", default="test", help="Issue title (for context)")
    p_route.add_argument("--type", "-t", default="task", choices=["bug", "task", "feature", "chore"])
    p_route.add_argument("--priority", default="medium", choices=["critical", "high", "medium", "low"])
    p_route.add_argument("--labels", "-l", nargs="*", default=[])
    p_route.add_argument("--source", default="human", choices=["human", "agent"])

    # trackers
    p_trackers = sub.add_parser("trackers", help="Manage tracker config")
    p_trackers.add_argument("action", nargs="?", choices=["show", "init", "add", "remove"])
    p_trackers.add_argument("--type", dest="tracker_type", choices=["github", "gitlab", "jira", "beads", "auto"])
    p_trackers.add_argument("--name", help="Tracker name")
    p_trackers.add_argument("--repo", help="GitHub repo (owner/name)")
    p_trackers.add_argument("--project-id", help="GitLab project ID")
    p_trackers.add_argument("--project-key", help="Jira project key")
    p_trackers.add_argument("--set-default", action="store_true")
    p_trackers.add_argument("--no-beads", action="store_true")

    # status
    p_status = sub.add_parser("status", help="Show issues across trackers")
    p_status.add_argument("--all", action="store_true", help="All registered projects")
    p_status.add_argument("--tracker", help="Filter to specific tracker")
    p_status.add_argument("--status", default="open", choices=["open", "closed", "all"])
    p_status.add_argument("--limit", type=int, default=20)

    # handoff
    p_handoff = sub.add_parser("handoff", help="Create work handoff")
    p_handoff.add_argument("--summary", "-s", help="Work summary")
    p_handoff.add_argument("--instructions", "-i", help="Instructions for recipient")

    # pickup
    p_pickup = sub.add_parser("pickup", help="Resume from handoff")
    p_pickup.add_argument("issue_id", nargs="?", help="Beads issue ID")
    p_pickup.add_argument("--list", action="store_true", help="List pending handoffs")

    # import (BMAD → Beads)
    p_import = sub.add_parser("import", help="Import BMAD stories into Beads")
    p_import.add_argument("--dry-run", action="store_true", help="Preview without creating issues")
    p_import.add_argument("--epic", type=int, help="Only import stories from this epic")

    # sync (BMAD ↔ Beads)
    p_sync = sub.add_parser("sync", help="Sync BMAD ↔ Beads statuses")
    p_sync.add_argument("--direction", choices=["auto", "bmad-to-beads", "beads-to-bmad"],
                        default="auto", help="Sync direction")
    p_sync.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_sync.add_argument("--check", action="store_true", help="Check for desyncs without changing anything")
    p_sync.add_argument("--alert-conflicts", action="store_true",
                        help="Create Beads issues for detected sync conflicts")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "prime": cmd_prime,
        "issue": cmd_issue,
        "route": cmd_route,
        "trackers": cmd_trackers,
        "status": cmd_status,
        "handoff": cmd_handoff,
        "pickup": cmd_pickup,
        "import": cmd_import,
        "sync": cmd_sync,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
