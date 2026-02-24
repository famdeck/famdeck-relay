"""Adapter dispatch — execute issue operations via gh/bd CLI or return MCP instructions."""

import json
import shutil
import subprocess
from typing import Optional

from .routing import priority_to_number, priority_to_jira, type_to_jira


def check_adapter(tracker_type: str) -> dict:
    """Check if an adapter's required tool is available.

    Returns: {"available": bool, "tool": str, "install_hint": str}
    """
    checks = {
        "github": ("gh", "GitHub CLI — https://cli.github.com/"),
        "beads": ("bd", "Beads CLI — /clawrig-toolkit:toolkit-setup"),
        "gitlab": (None, "GitLab MCP — /clawrig-toolkit:toolkit-setup"),
        "jira": (None, "Jira MCP — /clawrig-toolkit:toolkit-setup"),
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


# --- Beads adapter (bd CLI) ---

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

def _run_cli(cmd: list, adapter_name: str) -> dict:
    """Run a CLI command and return structured result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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
