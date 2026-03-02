"""Relay MCP server — exposes issue routing and tracker management as MCP tools."""

import json
import sys
from pathlib import Path
from typing import Optional

# Add plugin root to sys.path so we can import cli/ modules
_plugin_root = str(Path(__file__).resolve().parents[3])
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

from mcp.server.fastmcp import FastMCP

from cli.config import (
    find_project_path,
    find_project_slug,
    read_config,
    write_config,
    get_trackers,
    get_default_tracker,
    get_tracker_by_name,
    get_defaults,
    detect_repo_type,
    init_config,
    _iter_atlas_projects,
)
from cli.routing import evaluate_rules
from cli.adapters import check_adapter, create_issue, list_issues
from cli.importer import import_bmad_stories
from cli.sync import sync_statuses, check_desync

mcp = FastMCP(
    "relay",
    instructions=(
        "Cross-project issue routing and work handoff between sessions, tools, and people. "
        "Use issue() to create issues, status() to check dashboards, "
        "trackers() to manage tracker config."
    ),
)


def _result(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _error(message: str) -> str:
    return _result({"status": "error", "message": message})


# ── issue ────────────────────────────────────────────────────────────────────


@mcp.tool()
def issue(
    title: str,
    type: str = "task",
    priority: str = "medium",
    body: str = "",
    labels: Optional[list[str]] = None,
    assignee: Optional[str] = None,
    tracker: Optional[str] = None,
    source: str = "agent",
    no_beads: bool = False,
    project: Optional[str] = None,
) -> str:
    """Create and route an issue to the correct tracker.

    Routes issues based on .claude/relay.yaml rules to GitHub, GitLab, Jira,
    or beads. Use for filing bugs, tasks, features, or chores.

    Args:
        title: Issue title (required)
        type: Issue type — bug, task, feature, or chore
        priority: Priority — critical, high, medium, or low
        body: Issue description/body text
        labels: Extra labels to apply
        assignee: Assign to this user
        tracker: Force a specific tracker by name (bypasses routing rules)
        source: Who created it — human or agent
        no_beads: Skip beads cross-reference for non-beads trackers
        project: Atlas project slug or path (auto-detected if omitted)
    """
    labels = labels or []

    try:
        project_path = find_project_path(project)
    except Exception as e:
        return _error(str(e))

    config = read_config(project_path)
    if not config:
        return _error(f"No relay config at {project_path}/.claude/relay.yaml. Run: relay trackers init")

    # Explicit tracker override
    if tracker:
        target = get_tracker_by_name(config, tracker)
        if not target:
            names = [t["name"] for t in get_trackers(config)]
            return _error(f"Tracker '{tracker}' not found. Available: {names}")
        merged_labels = list(set((target.get("labels", []) or []) + labels))
        merged_assignee = assignee
    else:
        issue_ctx = {
            "type": type,
            "priority": priority,
            "source": source,
            "labels": labels,
            "assignee": assignee,
        }
        route = evaluate_rules(config, issue_ctx)
        target = route["tracker"]
        merged_labels = route["labels"]
        merged_assignee = route["assignee"]

    if not target:
        return _error("No tracker matched and no default configured")

    adapter_check = check_adapter(target["type"])
    if not adapter_check["available"]:
        return _error(f"Adapter unavailable: {adapter_check['install_hint']}")

    result = create_issue(
        tracker=target,
        title=title,
        body=body,
        issue_type=type,
        priority=priority,
        labels=merged_labels,
        assignee=merged_assignee,
        project_path=project_path,
    )
    result["tracker_name"] = target["name"]
    result["tracker_type"] = target["type"]

    # Beads cross-reference (if created in non-beads tracker)
    if result.get("status") == "ok" and target["type"] != "beads" and not no_beads:
        _maybe_beads_xref(config, title, result, target, project_path=project_path)

    return _result(result)


def _maybe_beads_xref(config, title, result, source_tracker, project_path=None):
    """Create beads cross-reference issue if beads tracker is configured."""
    import shutil
    import subprocess

    beads_tracker = None
    for t in get_trackers(config):
        if t["type"] == "beads":
            beads_tracker = t
            break
    if not beads_tracker:
        return

    if not shutil.which("bd"):
        return

    issue_ref = result.get("stdout", result.get("id", "unknown"))
    xref_body = f"Tracked in {source_tracker['name']}: {issue_ref}"
    try:
        kwargs = {"capture_output": True, "text": True, "timeout": 15}
        if project_path:
            kwargs["cwd"] = str(project_path)
        subprocess.run(
            ["bd", "create", f"External: {title}", "--type", "task",
             "--description", xref_body, "--label", "external-ref"],
            **kwargs,
        )
        result["beads_xref"] = True
    except Exception:
        pass


# ── route ────────────────────────────────────────────────────────────────────


@mcp.tool()
def route(
    title: str = "test",
    type: str = "task",
    priority: str = "medium",
    labels: Optional[list[str]] = None,
    source: str = "agent",
    project: Optional[str] = None,
) -> str:
    """Dry-run routing — shows which tracker would be chosen without creating anything.

    Args:
        title: Issue title (for context only)
        type: Issue type — bug, task, feature, or chore
        priority: Priority — critical, high, medium, or low
        labels: Labels to consider for routing
        source: Who is creating — human or agent
        project: Atlas project slug or path (auto-detected if omitted)
    """
    try:
        project_path = find_project_path(project)
    except Exception as e:
        return _error(str(e))

    config = read_config(project_path)
    if not config:
        return _error("No relay config found")

    issue_ctx = {
        "type": type,
        "priority": priority,
        "source": source,
        "labels": labels or [],
    }
    route = evaluate_rules(config, issue_ctx)
    target = route["tracker"]

    result = {
        "status": "ok",
        "action": "route_dry_run",
        "tracker_name": target["name"] if target else None,
        "tracker_type": target["type"] if target else None,
        "labels": route["labels"],
        "assignee": route["assignee"],
        "matched_rule": route["matched_rule"],
    }

    if target:
        adapter_check = check_adapter(target["type"])
        result["adapter_available"] = adapter_check["available"]
        if not adapter_check["available"]:
            result["adapter_hint"] = adapter_check["install_hint"]

    return _result(result)


# ── status ───────────────────────────────────────────────────────────────────


@mcp.tool()
def status(
    all: bool = False,
    project: Optional[str] = None,
    tracker: Optional[str] = None,
    status: str = "open",
    limit: int = 20,
) -> str:
    """Show issues across configured trackers — unified dashboard.

    Args:
        all: If true, show issues from all Atlas-registered projects
        project: Atlas project slug or path (auto-detected if omitted)
        tracker: Filter to a specific tracker by name
        status: Filter by status — open, closed, or all
        limit: Max issues per tracker (default 20)
    """
    if all:
        atlas_projects = _iter_atlas_projects()
        if not atlas_projects:
            return _error("Atlas not installed. Use project parameter or run from project dir.")
        projects = [(slug, Path(info["path"]).expanduser()) for slug, info in atlas_projects]
    else:
        try:
            project_path = find_project_path(project)
        except Exception as e:
            return _error(str(e))
        slug = find_project_slug(project_path) or project_path.name
        projects = [(slug, project_path)]

    results = []
    for slug, path in projects:
        config = read_config(path)
        if not config:
            results.append({"project": slug, "status": "no_config"})
            continue

        trackers_data = []
        for t in get_trackers(config):
            if tracker and t["name"] != tracker:
                continue
            adapter_check = check_adapter(t["type"])
            if not adapter_check["available"]:
                trackers_data.append({
                    "name": t["name"], "type": t["type"],
                    "status": "adapter_unavailable", "hint": adapter_check["install_hint"],
                })
                continue

            result = list_issues(t, status=status, limit=limit, project_path=path)
            trackers_data.append({
                "name": t["name"],
                "type": t["type"],
                "default": t.get("default", False),
                **result,
            })

        results.append({"project": slug, "trackers": trackers_data})

    return _result({"status": "ok", "projects": results})


# ── trackers ─────────────────────────────────────────────────────────────────


@mcp.tool()
def trackers(
    action: str = "show",
    tracker_type: Optional[str] = None,
    name: Optional[str] = None,
    repo: Optional[str] = None,
    project_id: Optional[str] = None,
    project_key: Optional[str] = None,
    set_default: bool = False,
    no_beads: bool = False,
    project: Optional[str] = None,
) -> str:
    """Manage per-project tracker configuration in .claude/relay.yaml.

    Args:
        action: What to do — show, init, add, or remove
        tracker_type: Tracker type for init/add — github, gitlab, jira, beads, or auto
        name: Tracker name (for add/remove)
        repo: GitHub repo as owner/name (for add --type github)
        project_id: GitLab project ID as group/project (for add --type gitlab)
        project_key: Jira project key (for add --type jira)
        set_default: Make this tracker the default (for add)
        no_beads: Skip adding beads tracker (for init)
        project: Atlas project slug or path (auto-detected if omitted)
    """
    try:
        project_path = find_project_path(project)
    except Exception as e:
        return _error(str(e))

    if action == "init":
        config = read_config(project_path)
        if config:
            return _error("Config already exists. Use 'show' to view, 'add' to add trackers.")
        config = init_config(project_path, tracker_type, add_beads=not no_beads)
        return _result({
            "status": "ok",
            "action": "init",
            "path": str(project_path / ".claude" / "relay.yaml"),
            "trackers": [{"name": t["name"], "type": t["type"]} for t in get_trackers(config)],
        })

    elif action == "show":
        config = read_config(project_path)
        if not config:
            return _error("No relay config. Run relay_trackers with action='init'")
        slug = find_project_slug(project_path) or project_path.name
        trackers = []
        for t in get_trackers(config):
            entry = {"name": t["name"], "type": t["type"], "default": t.get("default", False)}
            for field in ("repo", "project_id", "project_key", "scope"):
                if field in t:
                    entry[field] = t[field]
            if t.get("labels"):
                entry["labels"] = t["labels"]
            if t.get("routing_rules"):
                entry["rules"] = len(t["routing_rules"])
            trackers.append(entry)
        return _result({"status": "ok", "project": slug, "path": str(project_path), "trackers": trackers})

    elif action == "add":
        config = read_config(project_path)
        if not config:
            return _error("No config. Run init first.")
        if not tracker_type:
            return _error("Specify tracker_type (github|gitlab|jira|beads)")

        entry_name = name or tracker_type
        entry = {"name": entry_name, "type": tracker_type}

        if tracker_type == "github":
            detected = detect_repo_type(project_path)
            entry["repo"] = repo or (detected["repo"] if detected and detected["type"] == "github" else "owner/repo")
        elif tracker_type == "gitlab":
            detected = detect_repo_type(project_path)
            entry["project_id"] = project_id or (detected["project_id"] if detected and detected["type"] == "gitlab" else "group/project")
        elif tracker_type == "jira":
            entry["project_key"] = project_key or "PROJ"
        elif tracker_type == "beads":
            entry["scope"] = "local"

        if set_default:
            for t in config["issue_trackers"]:
                t.pop("default", None)
            entry["default"] = True

        config["issue_trackers"].append(entry)
        write_config(project_path, config)
        return _result({"status": "ok", "action": "add", "tracker": entry})

    elif action == "remove":
        config = read_config(project_path)
        if not config:
            return _error("No config.")
        if not name:
            return _error("Specify tracker name to remove")

        trackers = config.get("issue_trackers", [])
        found = [t for t in trackers if t["name"] == name]
        if not found:
            names = [t["name"] for t in trackers]
            return _error(f"Tracker '{name}' not found. Available: {names}")

        config["issue_trackers"] = [t for t in trackers if t["name"] != name]
        write_config(project_path, config)
        return _result({"status": "ok", "action": "remove", "removed": name})

    else:
        return _error(f"Unknown action '{action}'. Use: show, init, add, remove")


# ── handoff ──────────────────────────────────────────────────────────────────


@mcp.tool()
def handoff(
    summary: Optional[str] = None,
    instructions: Optional[str] = None,
    project: Optional[str] = None,
) -> str:
    """Create a work handoff — captures git state and context as a beads issue.

    Use when switching context, delegating work, or saving progress for later pickup.

    Args:
        summary: What was being worked on (auto-generated if omitted)
        instructions: Special instructions for the next person/session
        project: Atlas project slug or path (auto-detected if omitted)
    """
    import shutil
    import subprocess

    if not shutil.which("bd"):
        return _error("Beads CLI required. Install with /famdeck-toolkit:toolkit-setup")

    try:
        project_path = find_project_path(project)
    except Exception as e:
        return _error(str(e))
    slug = find_project_slug(project_path) or project_path.name

    git_info = _gather_git_info(project_path)

    summary = summary or f"Work handoff from {slug}"
    instructions = instructions or ""

    description = f"""## Objective
{summary}

## Branch
{git_info['branch']} @ {git_info['commit']} (uncommitted: {'yes' if git_info['dirty'] else 'no'})

## Files Changed
{git_info['files_changed'] or 'None'}

## Notes
{instructions or 'None'}
"""

    cmd = [
        "bd", "create", f"Handoff: {summary}",
        "--type", "task",
        "--description", description,
        "--label", "relay:handoff",
        "--label", f"handoff:branch:{git_info['branch']}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=str(project_path))
    except Exception as e:
        return _error(f"Failed to create handoff: {e}")

    if result.returncode == 0:
        return _result({
            "status": "ok",
            "action": "handoff_created",
            "project": slug,
            "branch": git_info["branch"],
            "commit": git_info["commit"],
            "stdout": result.stdout.strip(),
        })
    else:
        return _error(result.stderr.strip() or result.stdout.strip())


# ── pickup ───────────────────────────────────────────────────────────────────


@mcp.tool()
def pickup(
    issue_id: Optional[str] = None,
    list: bool = False,
    project: Optional[str] = None,
) -> str:
    """Resume from a handoff or list pending handoffs.

    Args:
        issue_id: Beads issue ID to pick up (omit to list pending)
        list: If true, list pending handoffs instead of picking up
        project: Atlas project slug or path (auto-detected if omitted)
    """
    import shutil
    import subprocess

    if not shutil.which("bd"):
        return _error("Beads CLI required.")

    try:
        project_path = find_project_path(project)
    except Exception as e:
        return _error(str(e))

    if list or not issue_id:
        result = subprocess.run(
            ["bd", "list", "--label", "relay:handoff", "--status", "open"],
            capture_output=True, text=True, timeout=15, cwd=str(project_path),
        )
        return _result({
            "status": "ok",
            "action": "list_handoffs",
            "stdout": result.stdout.strip(),
        })

    result = subprocess.run(
        ["bd", "show", issue_id],
        capture_output=True, text=True, timeout=15, cwd=str(project_path),
    )
    if result.returncode != 0:
        return _error(result.stderr.strip() or f"Issue {issue_id} not found")

    subprocess.run(
        ["bd", "update", issue_id, "--status", "in_progress"],
        capture_output=True, text=True, timeout=15, cwd=str(project_path),
    )

    return _result({
        "status": "ok",
        "action": "pickup",
        "issue_id": issue_id,
        "content": result.stdout.strip(),
    })


# ── sync ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def sync(
    direction: str = "auto",
    dry_run: bool = False,
    check: bool = False,
    alert_conflicts: bool = False,
    project: Optional[str] = None,
) -> str:
    """Sync BMAD sprint-status ↔ Beads statuses bidirectionally.

    Args:
        direction: Sync direction — auto, bmad-to-beads, or beads-to-bmad
        dry_run: Preview changes without applying them
        check: Just check for desyncs, don't change anything
        alert_conflicts: Create beads issues for detected sync conflicts
        project: Atlas project slug or path (auto-detected if omitted)
    """
    try:
        project_path = find_project_path(project)
    except Exception as e:
        return _error(str(e))

    config = read_config(project_path) or {}
    defaults = get_defaults(config)

    if check:
        result = check_desync(project_path, config_defaults=defaults)
        data = {"status": "ok", "action": "check", **result.to_dict()}
        if result.desynced:
            data["status"] = "desynced"
        if result.errors:
            data["status"] = "error"
        return _result(data)

    result = sync_statuses(
        project_path=project_path,
        direction=direction,
        dry_run=dry_run,
        alert_conflicts=alert_conflicts,
        config_defaults=defaults,
    )
    data = {"status": "ok", "action": "sync", **result.to_dict()}
    if result.errors:
        data["status"] = "partial" if result.bmad_to_beads or result.beads_to_bmad else "error"
    if result.conflicts:
        data["status"] = "conflicts"
    return _result(data)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _gather_git_info(project_path: Path) -> dict:
    """Collect git branch, commit, dirty state, changed files."""
    import subprocess

    def git(*cmd_args):
        try:
            r = subprocess.run(
                ["git", "-C", str(project_path)] + list(cmd_args),
                capture_output=True, text=True, timeout=5,
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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
