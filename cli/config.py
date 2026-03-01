"""Relay config management — read/write/validate .claude/relay.yaml"""

import os
import subprocess
from pathlib import Path
from typing import Optional

import yaml


def _iter_atlas_projects() -> list:
    """Read atlas registry and yield (slug, info_dict) tuples."""
    registry = Path.home() / ".claude" / "atlas" / "registry.yaml"
    if not registry.exists():
        return []
    data = yaml.safe_load(registry.read_text()) or {}
    projects = data.get("projects", {})
    # Registry is slug→{path, repo, ...} dict
    if isinstance(projects, dict):
        return list(projects.items())
    # Handle list format as fallback
    if isinstance(projects, list):
        return [(p.get("slug", ""), p) for p in projects]
    return []


def find_project_path(project_slug: Optional[str] = None) -> Path:
    """Resolve project path from slug (via atlas) or cwd."""
    if project_slug:
        for slug, info in _iter_atlas_projects():
            if slug == project_slug:
                return Path(info["path"]).expanduser()
        # Try as direct path
        p = Path(project_slug).expanduser()
        if p.is_dir():
            return p
        raise SystemExit(f"Project '{project_slug}' not found in atlas or as path")

    # Detect from cwd — walk up to find .claude/relay.yaml or .git
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        if (d / ".claude" / "relay.yaml").exists() or (d / ".git").exists():
            return d
        if d == d.parent:
            break
    return cwd


def find_project_slug(project_path: Path) -> Optional[str]:
    """Look up slug from atlas registry for a given path."""
    resolved = str(project_path.resolve())
    for slug, info in _iter_atlas_projects():
        if str(Path(info["path"]).expanduser().resolve()) == resolved:
            return slug
    return project_path.name


def read_config(project_path: Path) -> Optional[dict]:
    """Read .claude/relay.yaml from project path. Returns None if missing."""
    config_file = project_path / ".claude" / "relay.yaml"
    if not config_file.exists():
        return None
    return yaml.safe_load(config_file.read_text()) or {}


def write_config(project_path: Path, config: dict):
    """Write .claude/relay.yaml."""
    config_dir = project_path / ".claude"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "relay.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))


def get_defaults(config: dict) -> dict:
    """Extract defaults section from config, with fallback values."""
    defaults = config.get("defaults", {})
    return {
        "cli_timeout": defaults.get("cli_timeout", 30),
        "git_timeout": defaults.get("git_timeout", 5),
        "handoff_timeout": defaults.get("handoff_timeout", 15),
        "codeman_api_url": defaults.get("codeman_api_url", "http://localhost:3000"),
        "codeman_timeout": defaults.get("codeman_timeout", 15),
        "status_list_limit": defaults.get("status_list_limit", 20),
        "sprint_status_paths": defaults.get("sprint_status_paths", [
            "_bmad-output/implementation-artifacts/sprint-status.yaml",
            "_bmad-output/sprint-status.yaml",
            "sprint-status.yaml",
        ]),
    }


def get_trackers(config: dict) -> list:
    """Extract issue_trackers list from config."""
    return config.get("issue_trackers", [])


def get_default_tracker(config: dict) -> Optional[dict]:
    """Find the tracker with default: true."""
    for t in get_trackers(config):
        if t.get("default"):
            return t
    return None


def get_tracker_by_name(config: dict, name: str) -> Optional[dict]:
    """Find tracker by name."""
    for t in get_trackers(config):
        if t.get("name") == name:
            return t
    return None


def detect_repo_type(project_path: Path) -> Optional[dict]:
    """Auto-detect tracker type from git remote."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=5
        )
        url = result.stdout.strip()
        if not url:
            return None

        if "github.com" in url:
            # Extract owner/repo
            repo = url.rstrip(".git")
            if ":" in repo:
                repo = repo.split(":")[-1]
            elif "github.com/" in repo:
                repo = repo.split("github.com/")[-1]
            return {"type": "github", "repo": repo}

        if "gitlab" in url:
            project_id = url.rstrip(".git")
            if ":" in project_id:
                project_id = project_id.split(":")[-1]
            elif "gitlab" in project_id:
                parts = project_id.split("//")[-1].split("/", 1)
                project_id = parts[1] if len(parts) > 1 else parts[0]
            return {"type": "gitlab", "project_id": project_id}

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def init_config(project_path: Path, tracker_type: str = None, add_beads: bool = True) -> dict:
    """Create initial relay.yaml config."""
    detected = detect_repo_type(project_path)

    trackers = []

    if tracker_type and tracker_type != "auto":
        # User specified type
        if tracker_type == "github":
            repo = detected["repo"] if detected and detected["type"] == "github" else "owner/repo"
            trackers.append({"name": "github", "type": "github", "repo": repo, "default": True})
        elif tracker_type == "gitlab":
            pid = detected["project_id"] if detected and detected["type"] == "gitlab" else "group/project"
            trackers.append({"name": "gitlab", "type": "gitlab", "project_id": pid, "default": True})
        elif tracker_type == "jira":
            trackers.append({"name": "jira", "type": "jira", "project_key": "PROJ", "default": True})
        elif tracker_type == "beads":
            trackers.append({"name": "beads", "type": "beads", "scope": "local", "default": True})
            add_beads = False
    elif detected:
        t = detected["type"]
        entry = {"name": t, "type": t, "default": True}
        if t == "github":
            entry["repo"] = detected["repo"]
        elif t == "gitlab":
            entry["project_id"] = detected["project_id"]
        trackers.append(entry)
    else:
        trackers.append({"name": "beads", "type": "beads", "scope": "local", "default": True})
        add_beads = False

    if add_beads and not any(t["type"] == "beads" for t in trackers):
        trackers.append({
            "name": "beads", "type": "beads", "scope": "local",
            "routing_rules": [{"match": {"source": "agent"}, "action": {"default": True}}]
        })

    config = {"issue_trackers": trackers}
    write_config(project_path, config)
    return config
