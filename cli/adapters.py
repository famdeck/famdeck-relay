"""Adapter dispatch — execute issue operations via gh/bd CLI or return MCP instructions."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .models import Issue, IssueQuery
from .routing import priority_to_number, priority_to_jira, type_to_jira


# --- Beads adapter (bd CLI) — full CRUD ---

class BeadsAdapter:
    """Full-featured adapter for Beads issue tracker via bd CLI.

    Supports create, update, close, show, list with rich metadata fields
    (spec_id, external_ref, parent, metadata JSON, labels, deps).
    """

    def __init__(self, project_path: Optional[str | Path] = None):
        self.project_path = str(project_path) if project_path else None

    def _bd(self, *args: str, silent: bool = False) -> dict:
        """Run bd CLI command."""
        cmd = ["bd"] + list(args)
        kwargs: dict = {"capture_output": True, "text": True, "timeout": 30}
        if self.project_path:
            kwargs["cwd"] = self.project_path
        return _run_cli(cmd, "beads", **kwargs)

    def _bd_json(self, *args: str) -> list[dict]:
        """Run bd command with --json and parse output."""
        result = self._bd(*args, "--json")
        if result["status"] != "ok":
            return []
        try:
            data = json.loads(result.get("stdout", "[]"))
            return data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            return []

    def available(self) -> bool:
        """Check if bd CLI is available."""
        return shutil.which("bd") is not None

    def create(self, issue: Issue) -> Issue:
        """Create a new issue in Beads. Returns the created Issue with ID populated."""
        cmd_args = ["create", issue.title, "--type", issue.issue_type,
                     "--priority", str(issue.priority), "--silent"]

        if issue.description:
            cmd_args.extend(["--description", issue.description])
        for label in issue.labels:
            cmd_args.extend(["--label", label])
        if issue.assignee:
            cmd_args.extend(["--assignee", issue.assignee])
        if issue.spec_id:
            cmd_args.extend(["--spec-id", issue.spec_id])
        if issue.external_ref:
            cmd_args.extend(["--external-ref", issue.external_ref])
        if issue.parent_id:
            cmd_args.extend(["--parent", issue.parent_id])
        if issue.acceptance:
            cmd_args.extend(["--acceptance", issue.acceptance])
        if issue.design:
            cmd_args.extend(["--design", issue.design])
        if issue.notes:
            cmd_args.extend(["--notes", issue.notes])

        result = self._bd(*cmd_args)
        if result["status"] != "ok":
            raise AdapterError(f"bd create failed: {result.get('message', 'unknown')}")

        issue_id = result["stdout"].strip()
        created = issue
        created.id = issue_id

        # Set metadata and source_system via update (not available on create)
        update_args = []
        if issue.metadata:
            update_args.extend(["--metadata", json.dumps(issue.metadata)])
        if update_args:
            self._bd("update", issue_id, *update_args)

        return created

    def update(self, issue_id: str, **fields) -> None:
        """Update issue fields. Accepts any field name from Issue model."""
        cmd_args = ["update", issue_id]

        field_map = {
            "title": "--title",
            "description": "--description",
            "status": "--status",
            "priority": "--priority",
            "assignee": "--assignee",
            "spec_id": "--spec-id",
            "external_ref": "--external-ref",
            "parent_id": "--parent",
            "acceptance": "--acceptance",
            "design": "--design",
            "notes": "--notes",
        }

        for field_name, flag in field_map.items():
            if field_name in fields:
                value = fields[field_name]
                cmd_args.extend([flag, str(value)])

        if "metadata" in fields:
            cmd_args.extend(["--metadata", json.dumps(fields["metadata"])])

        if "add_labels" in fields:
            for label in fields["add_labels"]:
                cmd_args.extend(["--add-label", label])

        if "remove_labels" in fields:
            for label in fields["remove_labels"]:
                cmd_args.extend(["--remove-label", label])

        if len(cmd_args) <= 2:
            return  # nothing to update

        result = self._bd(*cmd_args)
        if result["status"] != "ok":
            raise AdapterError(f"bd update failed: {result.get('message', 'unknown')}")

    def close(self, issue_id: str, reason: str = "") -> None:
        """Close an issue."""
        cmd_args = ["close", issue_id]
        if reason:
            cmd_args.extend(["--reason", reason])
        result = self._bd(*cmd_args)
        if result["status"] != "ok":
            raise AdapterError(f"bd close failed: {result.get('message', 'unknown')}")

    def show(self, issue_id: str) -> Optional[Issue]:
        """Get a single issue by ID."""
        items = self._bd_json("show", issue_id)
        if not items:
            return None
        return Issue.from_beads_json(items[0])

    def list(self, query: Optional[IssueQuery] = None) -> list[Issue]:
        """List issues matching query."""
        cmd_args = ["list"]
        if query:
            cmd_args.extend(query.to_bd_args())
        items = self._bd_json(*cmd_args)
        return [Issue.from_beads_json(item) for item in items]

    def add_dependency(self, issue_id: str, depends_on: str, dep_type: str = "blocks") -> None:
        """Add a dependency between issues."""
        result = self._bd("dep", "add", issue_id, depends_on)
        if result["status"] != "ok":
            raise AdapterError(f"bd dep add failed: {result.get('message', 'unknown')}")

    def ready(self) -> list[Issue]:
        """Get ready-to-work issues (no blockers)."""
        items = self._bd_json("ready")
        return [Issue.from_beads_json(item) for item in items]


class AdapterError(Exception):
    """Raised when an adapter operation fails."""
    pass


# --- Backward-compatible dispatch functions ---

def check_adapter(tracker_type: str) -> dict:
    """Check if an adapter's required tool is available.

    Returns: {"available": bool, "tool": str, "install_hint": str}
    """
    checks = {
        "github": ("gh", "GitHub CLI — https://cli.github.com/"),
        "beads": ("bd", "Beads CLI — /famdeck-toolkit:toolkit-setup"),
        "gitlab": (None, "GitLab MCP — /famdeck-toolkit:toolkit-setup"),
        "jira": (None, "Jira MCP — /famdeck-toolkit:toolkit-setup"),
    }
    tool, hint = checks.get(tracker_type, (None, "Unknown tracker type"))

    if tool:
        available = shutil.which(tool) is not None
        return {"available": available, "tool": tool, "install_hint": hint}
    else:
        # MCP tools — CLI can't check, mark as needing Claude to verify
        return {"available": True, "tool": "mcp", "install_hint": hint, "needs_mcp": True}


def create_issue(tracker: dict, title: str, body: str, issue_type: str,
                 priority: str, labels: list, assignee: Optional[str] = None) -> dict:
    """Create an issue via the appropriate adapter.

    Returns:
        {"status": "ok", "id": ..., "url": ..., ...}  — for CLI adapters
        {"status": "needs_mcp", "tool": ..., "params": ...}  — for MCP adapters
        {"status": "error", "message": ...}  — on failure
    """
    adapter_type = tracker["type"]

    if adapter_type == "github":
        return _github_create(tracker, title, body, issue_type, priority, labels, assignee)
    elif adapter_type == "beads":
        return _beads_create(tracker, title, body, issue_type, priority, labels, assignee)
    elif adapter_type == "gitlab":
        return _gitlab_create(tracker, title, body, issue_type, priority, labels, assignee)
    elif adapter_type == "jira":
        return _jira_create(tracker, title, body, issue_type, priority, labels, assignee)
    else:
        return {"status": "error", "message": f"Unknown adapter type: {adapter_type}"}


def list_issues(tracker: dict, status: str = "open", limit: int = 20) -> dict:
    """List issues from a tracker."""
    adapter_type = tracker["type"]

    if adapter_type == "github":
        return _github_list(tracker, status, limit)
    elif adapter_type == "beads":
        return _beads_list(tracker, status, limit)
    elif adapter_type == "gitlab":
        return _gitlab_list(tracker, status, limit)
    elif adapter_type == "jira":
        return _jira_list(tracker, status, limit)
    else:
        return {"status": "error", "message": f"Unknown adapter type: {adapter_type}"}


# --- GitHub adapter (gh CLI) ---

def _github_create(tracker, title, body, issue_type, priority, labels, assignee):
    repo = tracker.get("repo")
    if not repo:
        return {"status": "error", "message": "GitHub tracker missing 'repo' field"}

    all_labels = list(set(labels + [issue_type, f"P-{priority}"]))
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    if all_labels:
        cmd.extend(["--label", ",".join(all_labels)])
    if assignee:
        cmd.extend(["--assignee", assignee.lstrip("@")])

    return _run_cli(cmd, "github")


def _github_list(tracker, status, limit):
    repo = tracker.get("repo")
    state = "all" if status == "all" else ("closed" if status == "closed" else "open")
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", state,
           "--limit", str(limit), "--json", "number,title,labels,assignees,state,createdAt"]
    result = _run_cli(cmd, "github")
    if result["status"] == "ok":
        try:
            result["issues"] = json.loads(result.get("stdout", "[]"))
        except json.JSONDecodeError:
            result["issues"] = []
    return result


# --- Beads adapter (bd CLI) — legacy functions ---

def _beads_create(tracker, title, body, issue_type, priority, labels, assignee):
    pri_num = priority_to_number(priority)
    cmd = ["bd", "create", title, "--type", issue_type, "--priority", str(pri_num)]
    if body:
        cmd.extend(["--description", body])
    for label in labels:
        cmd.extend(["--label", label])
    return _run_cli(cmd, "beads")


def _beads_list(tracker, status, limit):
    cmd = ["bd", "list"]
    if status and status != "all":
        cmd.extend(["--status", status])
    result = _run_cli(cmd, "beads")
    if result["status"] == "ok":
        result["issues"] = result.get("stdout", "")
    return result


# --- GitLab adapter (MCP) ---

def _gitlab_create(tracker, title, body, issue_type, priority, labels, assignee):
    project_id = tracker.get("project_id")
    if not project_id:
        return {"status": "error", "message": "GitLab tracker missing 'project_id' field"}

    all_labels = ",".join(set(labels + [issue_type, priority]))
    params = {
        "project_id": project_id,
        "title": title,
        "description": body or "",
        "labels": all_labels,
    }
    if assignee:
        params["assignee"] = assignee

    return {
        "status": "needs_mcp",
        "adapter": "gitlab",
        "tool": "mcp__plugin_ds_gitlab__create_issue",
        "params": params,
    }


def _gitlab_list(tracker, status, limit):
    project_id = tracker.get("project_id")
    state = "all" if status == "all" else ("closed" if status == "closed" else "opened")
    return {
        "status": "needs_mcp",
        "adapter": "gitlab",
        "tool": "mcp__plugin_ds_gitlab__list_issues",
        "params": {"project_id": project_id, "state": state, "per_page": limit},
    }


# --- Jira adapter (MCP) ---

def _jira_create(tracker, title, body, issue_type, priority, labels, assignee):
    project_key = tracker.get("project_key")
    if not project_key:
        return {"status": "error", "message": "Jira tracker missing 'project_key' field"}

    params = {
        "project_key": project_key,
        "summary": title,
        "description": body or "",
        "issuetype": type_to_jira(issue_type),
        "priority": priority_to_jira(priority),
    }
    if labels:
        params["labels"] = labels
    if assignee:
        params["assignee"] = assignee

    return {
        "status": "needs_mcp",
        "adapter": "jira",
        "tool": "mcp__plugin_ds_atlassian__jira_create_issue",
        "params": params,
    }


def _jira_list(tracker, status, limit):
    project_key = tracker.get("project_key")
    if status == "closed":
        jql = f'project = {project_key} AND status = Done'
    elif status == "all":
        jql = f'project = {project_key}'
    else:
        jql = f'project = {project_key} AND status != Done'
    return {
        "status": "needs_mcp",
        "adapter": "jira",
        "tool": "mcp__plugin_ds_atlassian__jira_search",
        "params": {"jql": jql, "max_results": limit},
    }


# --- CLI runner ---

def _run_cli(cmd: list, adapter_name: str, **subprocess_kwargs) -> dict:
    """Run a CLI command and return structured result."""
    kwargs = {"capture_output": True, "text": True, "timeout": 30}
    kwargs.update(subprocess_kwargs)
    try:
        result = subprocess.run(cmd, **kwargs)
        if result.returncode == 0:
            return {
                "status": "ok",
                "adapter": adapter_name,
                "stdout": result.stdout.strip(),
                "command": " ".join(cmd),
            }
        else:
            return {
                "status": "error",
                "adapter": adapter_name,
                "message": result.stderr.strip() or result.stdout.strip(),
                "command": " ".join(cmd),
                "returncode": result.returncode,
            }
    except FileNotFoundError:
        return {"status": "error", "adapter": adapter_name, "message": f"Command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "adapter": adapter_name, "message": f"Command timed out: {' '.join(cmd)}"}
