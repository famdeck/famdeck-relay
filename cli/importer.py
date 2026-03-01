"""BMAD import — sync sprint-status.yaml stories into Beads issues."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .adapters import BeadsAdapter
from .bmad import BMADAdapter, BMAD_TO_BEADS_STATUS
from .models import Issue, IssueQuery

logger = logging.getLogger(__name__)


class ImportResult:
    """Result of a BMAD import operation."""

    def __init__(self):
        self.created: list[str] = []  # issue IDs created
        self.updated: list[str] = []  # issue IDs updated
        self.skipped: list[str] = []  # story keys skipped (already synced)
        self.errors: list[str] = []  # error messages

    @property
    def total(self) -> int:
        return len(self.created) + len(self.updated) + len(self.skipped)

    def to_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "summary": f"{len(self.created)} created, {len(self.updated)} updated, "
                       f"{len(self.skipped)} skipped, {len(self.errors)} errors",
        }


def import_bmad_stories(
    project_path: str | Path,
    dry_run: bool = False,
    epic_filter: Optional[int] = None,
) -> ImportResult:
    """Import BMAD stories from sprint-status.yaml into Beads.

    For each BMAD story:
    1. Check if a Beads issue with matching bmad_key label exists
    2. If not, create one with source_system=bmad, spec_id, labels
    3. If yes, sync status if it changed

    Args:
        project_path: Project root containing _bmad-output/
        dry_run: If True, don't actually create/update issues
        epic_filter: Only import stories from this epic number
    """
    project_path = Path(project_path).resolve()
    result = ImportResult()

    bmad = BMADAdapter(project_path)
    if not bmad.exists():
        result.errors.append(f"sprint-status.yaml not found in {project_path}")
        return result

    beads = BeadsAdapter(project_path=str(project_path))
    if not beads.available():
        result.errors.append("bd CLI not available")
        return result

    # Get all BMAD stories
    bmad_stories = bmad.list_stories()
    if epic_filter:
        bmad_stories = [s for s in bmad_stories if s.epic_num == epic_filter]

    # Get existing Beads issues with bmad label
    existing = beads.list(IssueQuery(labels=["bmad"]))
    existing_by_key: dict[str, Issue] = {}
    for issue in existing:
        bmad_key = issue.metadata.get("bmad_key", "")
        if bmad_key:
            existing_by_key[bmad_key] = issue
        else:
            # Try to match by label
            for label in issue.labels:
                if label.startswith("bmad:"):
                    existing_by_key[label.replace("bmad:", "")] = issue
                    break

    # Convert stories to issues
    bmad_issues = bmad.to_issues()
    bmad_issues_by_key = {i.metadata.get("bmad_key", ""): i for i in bmad_issues}

    for story in bmad_stories:
        try:
            if story.key in existing_by_key:
                _sync_existing(beads, story, existing_by_key[story.key],
                               bmad_issues_by_key.get(story.key), result, dry_run)
            else:
                _create_new(beads, story, bmad_issues_by_key.get(story.key),
                            result, dry_run)
        except Exception as e:
            result.errors.append(f"{story.key}: {e}")

    return result


def _create_new(
    beads: BeadsAdapter,
    story,
    issue_template: Optional[Issue],
    result: ImportResult,
    dry_run: bool,
) -> None:
    """Create a new Beads issue for a BMAD story."""
    if issue_template is None:
        result.errors.append(f"{story.key}: no issue template")
        return

    issue = Issue(
        title=issue_template.title,
        description=issue_template.description,
        issue_type="feature",
        priority=_epic_to_priority(story.epic_num),
        labels=issue_template.labels + [f"bmad:{story.key}"],
        source_system="bmad",
        spec_id=issue_template.spec_id,
        metadata=issue_template.metadata,
    )

    if dry_run:
        result.created.append(f"(dry-run) {story.key}")
        return

    created = beads.create(issue)
    result.created.append(created.id)
    logger.info("Created %s for BMAD story %s", created.id, story.key)


def _sync_existing(
    beads: BeadsAdapter,
    story,
    existing: Issue,
    issue_template: Optional[Issue],
    result: ImportResult,
    dry_run: bool,
) -> None:
    """Sync status between BMAD story and existing Beads issue."""
    beads_status = BMAD_TO_BEADS_STATUS.get(story.status, "open")

    if existing.status == beads_status:
        result.skipped.append(story.key)
        return

    if dry_run:
        result.updated.append(f"(dry-run) {existing.id}: {existing.status} → {beads_status}")
        return

    updates = {
        "status": beads_status,
        "metadata": {
            **(existing.metadata or {}),
            "bmad_status": story.status,
        },
    }
    beads.update(existing.id, **updates)
    result.updated.append(existing.id)
    logger.info("Updated %s: %s → %s", existing.id, existing.status, beads_status)


def _epic_to_priority(epic_num: int) -> int:
    """Map epic number to default priority. Lower epics = higher priority."""
    if epic_num <= 1:
        return 1
    elif epic_num <= 3:
        return 2
    else:
        return 3
