"""Universal issue model — tracker-agnostic representation of issues."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


@dataclass
class Issue:
    """Tracker-agnostic issue representation.

    Maps to/from Beads, BMAD sprint-status, GitHub, GitLab, Jira.
    Beads is the canonical store; other trackers map to this model.
    """

    # Core identity
    id: str = ""
    title: str = ""
    description: str = ""

    # Classification
    issue_type: str = "task"  # bug, feature, task, chore, epic
    priority: int = 2  # 0=critical, 1=high, 2=medium, 3=low, 4=backlog
    status: str = "open"  # open, in_progress, closed
    labels: list[str] = field(default_factory=list)

    # Ownership
    assignee: str = ""
    created_by: str = ""

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    # Rich fields (Beads-specific, others ignore)
    source_system: str = ""  # "bmad", "relay", "manual", "retrospective"
    spec_id: str = ""  # path to spec file (e.g., story .md)
    external_ref: str = ""  # cross-ref to GitHub/GitLab/Jira
    parent_id: str = ""  # hierarchical parent
    metadata: dict[str, Any] = field(default_factory=dict)

    # Content fields
    acceptance: str = ""
    design: str = ""
    notes: str = ""

    # Dependency counts (read-only, from queries)
    dependency_count: int = 0
    dependent_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, omitting empty/default values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v or v == 0}

    @classmethod
    def from_beads_json(cls, data: dict) -> Issue:
        """Create Issue from bd CLI JSON output."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            issue_type=data.get("issue_type", "task"),
            priority=data.get("priority", 2),
            status=data.get("status", "open"),
            labels=data.get("labels", []),
            assignee=data.get("owner", ""),
            created_by=data.get("created_by", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            source_system=data.get("source_system", ""),
            spec_id=data.get("spec_id", ""),
            external_ref=data.get("external_ref", ""),
            parent_id=data.get("parent_id", ""),
            metadata=data.get("metadata") or {},
            acceptance=data.get("acceptance", ""),
            design=data.get("design", ""),
            notes=data.get("notes", ""),
            dependency_count=data.get("dependency_count", 0),
            dependent_count=data.get("dependent_count", 0),
        )

    @classmethod
    def from_github_json(cls, data: dict) -> Issue:
        """Create Issue from GitHub JSON (gh issue list --json)."""
        labels = [l.get("name", "") for l in data.get("labels", [])]
        assignees = [a.get("login", "") for a in data.get("assignees", [])]
        state = data.get("state", "OPEN").lower()
        status = "closed" if state == "closed" else "open"

        return cls(
            id=str(data.get("number", "")),
            title=data.get("title", ""),
            description=data.get("body", ""),
            status=status,
            labels=labels,
            assignee=assignees[0] if assignees else "",
            created_at=data.get("createdAt", ""),
            updated_at=data.get("updatedAt", ""),
            external_ref=data.get("url", ""),
        )

    def priority_label(self) -> str:
        """Human-readable priority."""
        return {0: "critical", 1: "high", 2: "medium", 3: "low", 4: "backlog"}.get(
            self.priority, "medium"
        )


@dataclass
class IssueQuery:
    """Query parameters for listing/filtering issues."""

    status: str = ""  # open, in_progress, closed, all
    issue_type: str = ""
    labels: list[str] = field(default_factory=list)
    assignee: str = ""
    parent_id: str = ""
    source_system: str = ""
    limit: int = 50

    def to_bd_args(self) -> list[str]:
        """Convert to bd list CLI arguments."""
        args: list[str] = []
        if self.status and self.status != "all":
            args.extend(["--status", self.status])
        if self.issue_type:
            args.extend(["--type", self.issue_type])
        for label in self.labels:
            args.extend(["--label", label])
        if self.assignee:
            args.extend(["--assignee", self.assignee])
        if self.parent_id:
            args.extend(["--parent", self.parent_id])
        return args
