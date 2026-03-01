"""BMAD adapter — read/write sprint-status.yaml, map to universal issue model."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from .models import Issue


# BMAD status ↔ Beads status mapping
BMAD_TO_BEADS_STATUS = {
    "backlog": "open",
    "ready-for-dev": "open",
    "in-progress": "in_progress",
    "review": "in_progress",
    "done": "closed",
}

BEADS_TO_BMAD_STATUS = {
    "open": "backlog",  # default; "ready-for-dev" if spec exists
    "in_progress": "in-progress",
    "closed": "done",
}

# Valid BMAD statuses
EPIC_STATUSES = {"backlog", "in-progress", "done"}
STORY_STATUSES = {"backlog", "ready-for-dev", "in-progress", "review", "done"}


DEFAULT_SPRINT_STATUS_PATHS = [
    "_bmad-output/implementation-artifacts/sprint-status.yaml",
    "_bmad-output/sprint-status.yaml",
    "sprint-status.yaml",
]


class BMADAdapter:
    """Adapter for BMAD sprint-status.yaml — reads/writes story/epic status.

    sprint-status.yaml is a flat YAML file under development_status:
        epic-N: <epic_status>
        N-M-story-title: <story_status>
        epic-N-retrospective: optional | done
    """

    def __init__(self, project_path: str | Path,
                 sprint_status_paths: Optional[list[str]] = None):
        self.project_path = Path(project_path).resolve()
        self._status_path: Optional[Path] = None
        self._search_paths = sprint_status_paths or DEFAULT_SPRINT_STATUS_PATHS

    @property
    def status_path(self) -> Path:
        """Find sprint-status.yaml location."""
        if self._status_path and self._status_path.exists():
            return self._status_path

        # Check configured locations
        candidates = [self.project_path / p for p in self._search_paths]
        for p in candidates:
            if p.exists():
                self._status_path = p
                return p

        # Default to first candidate
        self._status_path = candidates[0]
        return self._status_path

    def exists(self) -> bool:
        """Check if sprint-status.yaml exists."""
        return self.status_path.exists()

    def read_raw(self) -> dict:
        """Read sprint-status.yaml and return the raw development_status dict."""
        if not self.exists():
            return {}
        with open(self.status_path) as f:
            data = yaml.safe_load(f)
        return (data or {}).get("development_status", {})

    def read_metadata(self) -> dict:
        """Read YAML comment metadata (project, story_location, etc.)."""
        if not self.exists():
            return {}
        meta = {}
        with open(self.status_path) as f:
            for line in f:
                line = line.strip()
                if not line.startswith("#"):
                    break
                m = re.match(r"#\s*(\w+):\s*(.+)", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip().strip('"')
        return meta

    def list_stories(self) -> list[BMADStory]:
        """List all stories from sprint-status.yaml."""
        raw = self.read_raw()
        stories = []
        for key, status in raw.items():
            if key.startswith("epic-") or key.endswith("-retrospective"):
                continue
            story = BMADStory.from_key(key, status)
            if story:
                stories.append(story)
        return stories

    def list_epics(self) -> list[BMADEpic]:
        """List all epics from sprint-status.yaml."""
        raw = self.read_raw()
        epics = []
        for key, status in raw.items():
            if key.startswith("epic-") and not key.endswith("-retrospective"):
                num = key.replace("epic-", "")
                epics.append(BMADEpic(number=int(num), status=status))
        return epics

    def get_story_status(self, story_key: str) -> Optional[str]:
        """Get BMAD status for a story key."""
        raw = self.read_raw()
        return raw.get(story_key)

    def set_story_status(self, story_key: str, status: str) -> None:
        """Update a story's status in sprint-status.yaml."""
        if status not in STORY_STATUSES:
            raise ValueError(f"Invalid story status: {status}. Valid: {STORY_STATUSES}")
        self._update_key(story_key, status)

    def set_epic_status(self, epic_key: str, status: str) -> None:
        """Update an epic's status in sprint-status.yaml."""
        if status not in EPIC_STATUSES:
            raise ValueError(f"Invalid epic status: {status}. Valid: {EPIC_STATUSES}")
        self._update_key(epic_key, status)

    def _update_key(self, key: str, value: str) -> None:
        """Update a single key in sprint-status.yaml preserving comments."""
        path = self.status_path
        if not path.exists():
            raise FileNotFoundError(f"sprint-status.yaml not found: {path}")

        lines = path.read_text().splitlines()
        updated = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            # Match "  key: value" pattern
            m = re.match(r"(\s*)" + re.escape(key) + r":\s*(.*)", line)
            if m:
                indent = m.group(1)
                lines[i] = f"{indent}{key}: {value}"
                updated = True
                break

        if not updated:
            raise KeyError(f"Key not found in sprint-status.yaml: {key}")

        path.write_text("\n".join(lines) + "\n")

    def to_issues(self) -> list[Issue]:
        """Convert all BMAD stories to universal Issue model."""
        stories = self.list_stories()
        meta = self.read_metadata()
        story_location = meta.get("story_location", "_bmad-output/implementation-artifacts")

        issues = []
        for story in stories:
            spec_path = f"{story_location}/{story.key}.md"
            beads_status = BMAD_TO_BEADS_STATUS.get(story.status, "open")
            issue = Issue(
                title=f"Story {story.epic_num}.{story.story_num}: {story.title_text}",
                description=f"BMAD story from sprint-status.yaml",
                issue_type="feature",
                status=beads_status,
                source_system="bmad",
                spec_id=spec_path,
                metadata={
                    "bmad_key": story.key,
                    "bmad_status": story.status,
                    "epic_num": story.epic_num,
                    "story_num": story.story_num,
                },
                labels=[f"epic-{story.epic_num}", "bmad"],
            )
            issues.append(issue)
        return issues

    def next_story(self) -> Optional[BMADStory]:
        """Find the next story to work on (first ready-for-dev, then first backlog)."""
        stories = self.list_stories()
        # Priority: ready-for-dev > backlog
        for status in ("ready-for-dev", "backlog"):
            for story in stories:
                if story.status == status:
                    return story
        return None

    def sprint_counts(self) -> dict[str, int]:
        """Return status counts for stories."""
        stories = self.list_stories()
        counts: dict[str, int] = {}
        for story in stories:
            counts[story.status] = counts.get(story.status, 0) + 1
        return counts


class BMADStory:
    """Parsed BMAD story from sprint-status.yaml key."""

    def __init__(self, key: str, status: str, epic_num: int, story_num: int, title_text: str):
        self.key = key
        self.status = status
        self.epic_num = epic_num
        self.story_num = story_num
        self.title_text = title_text

    @classmethod
    def from_key(cls, key: str, status: str) -> Optional[BMADStory]:
        """Parse a sprint-status key like '1-1-autonomy-readiness-assessment'."""
        m = re.match(r"(\d+)-(\d+)-(.+)", key)
        if not m:
            return None
        epic_num = int(m.group(1))
        story_num = int(m.group(2))
        title_text = m.group(3).replace("-", " ").title()
        return cls(key=key, status=status, epic_num=epic_num,
                   story_num=story_num, title_text=title_text)

    @property
    def story_id(self) -> str:
        """Dotted story identifier (e.g., '1.1')."""
        return f"{self.epic_num}.{self.story_num}"

    def __repr__(self) -> str:
        return f"BMADStory({self.key!r}, {self.status!r})"


class BMADEpic:
    """Parsed BMAD epic from sprint-status.yaml."""

    def __init__(self, number: int, status: str):
        self.number = number
        self.status = status
        self.key = f"epic-{number}"

    def __repr__(self) -> str:
        return f"BMADEpic({self.number}, {self.status!r})"
