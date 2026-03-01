"""Sync engine — bidirectional status sync between BMAD and Beads."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .adapters import BeadsAdapter
from .bmad import BMADAdapter, BMAD_TO_BEADS_STATUS, BEADS_TO_BMAD_STATUS
from .models import Issue, IssueQuery

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of a sync operation."""

    def __init__(self):
        self.bmad_to_beads: list[str] = []  # story keys synced BMAD → Beads
        self.beads_to_bmad: list[str] = []  # story keys synced Beads → BMAD
        self.conflicts: list[str] = []  # both changed — needs resolution
        self.unchanged: list[str] = []
        self.errors: list[str] = []

    def to_dict(self) -> dict:
        return {
            "bmad_to_beads": self.bmad_to_beads,
            "beads_to_bmad": self.beads_to_bmad,
            "conflicts": self.conflicts,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "summary": (
                f"{len(self.bmad_to_beads)} BMAD→Beads, "
                f"{len(self.beads_to_bmad)} Beads→BMAD, "
                f"{len(self.conflicts)} conflicts, "
                f"{len(self.unchanged)} unchanged"
            ),
        }


def sync_statuses(
    project_path: str | Path,
    direction: str = "auto",
    dry_run: bool = False,
) -> SyncResult:
    """Synchronize BMAD sprint-status.yaml ↔ Beads issue statuses.

    Direction:
        "auto" — detect which side changed based on metadata.bmad_status
        "bmad-to-beads" — force BMAD as source of truth
        "beads-to-bmad" — force Beads as source of truth

    For "auto" mode:
        1. Read BMAD story statuses from sprint-status.yaml
        2. Read Beads issues with bmad label
        3. Compare: if Beads metadata.bmad_status matches BMAD, but
           Beads status differs → Beads changed, sync to BMAD
        4. If metadata.bmad_status differs from BMAD → BMAD changed,
           sync to Beads
        5. If both changed → conflict
    """
    project_path = Path(project_path).resolve()
    result = SyncResult()

    bmad = BMADAdapter(project_path)
    if not bmad.exists():
        result.errors.append("sprint-status.yaml not found")
        return result

    beads = BeadsAdapter(project_path=str(project_path))
    if not beads.available():
        result.errors.append("bd CLI not available")
        return result

    # Get BMAD stories
    stories = bmad.list_stories()
    story_by_key = {s.key: s for s in stories}

    # Get Beads issues with bmad label
    beads_issues = beads.list(IssueQuery(labels=["bmad"]))
    beads_by_key: dict[str, Issue] = {}
    for issue in beads_issues:
        bmad_key = issue.metadata.get("bmad_key", "")
        if bmad_key:
            beads_by_key[bmad_key] = issue
        else:
            for label in issue.labels:
                if label.startswith("bmad:"):
                    beads_by_key[label.replace("bmad:", "")] = issue
                    break

    # Sync each story
    for story_key, story in story_by_key.items():
        beads_issue = beads_by_key.get(story_key)
        if not beads_issue:
            result.unchanged.append(story_key)
            continue

        try:
            _sync_one(
                bmad=bmad,
                beads=beads,
                story=story,
                beads_issue=beads_issue,
                direction=direction,
                dry_run=dry_run,
                result=result,
            )
        except Exception as e:
            result.errors.append(f"{story_key}: {e}")

    return result


def _sync_one(
    bmad: BMADAdapter,
    beads: BeadsAdapter,
    story,
    beads_issue: Issue,
    direction: str,
    dry_run: bool,
    result: SyncResult,
) -> None:
    """Sync a single story/issue pair."""
    bmad_status = story.status
    beads_status = beads_issue.status
    last_known_bmad = beads_issue.metadata.get("bmad_status", "")

    # Convert for comparison
    expected_beads = BMAD_TO_BEADS_STATUS.get(bmad_status, "open")
    expected_bmad = BEADS_TO_BMAD_STATUS.get(beads_status, "backlog")

    # Detect changes
    if direction == "bmad-to-beads":
        bmad_changed = True
        beads_changed = False
    elif direction == "beads-to-bmad":
        bmad_changed = False
        beads_changed = True
    else:
        # Auto-detect based on last_known_bmad
        bmad_changed = bmad_status != last_known_bmad
        beads_changed = beads_status != expected_beads and not bmad_changed

    if bmad_changed and beads_changed:
        result.conflicts.append(
            f"{story.key}: BMAD={bmad_status}, Beads={beads_status}, "
            f"last_known={last_known_bmad}"
        )
        return

    if bmad_changed and beads_status != expected_beads:
        # BMAD → Beads
        if not dry_run:
            beads.update(beads_issue.id,
                         status=expected_beads,
                         metadata={**beads_issue.metadata, "bmad_status": bmad_status})
        result.bmad_to_beads.append(
            f"{story.key}: {beads_status} → {expected_beads} (BMAD: {bmad_status})"
        )
        return

    if beads_changed:
        # Beads → BMAD
        # Refine BMAD status based on context
        new_bmad = _refine_bmad_status(expected_bmad, beads_issue)
        if new_bmad != bmad_status:
            if not dry_run:
                bmad.set_story_status(story.key, new_bmad)
                beads.update(beads_issue.id,
                             metadata={**beads_issue.metadata, "bmad_status": new_bmad})
            result.beads_to_bmad.append(
                f"{story.key}: {bmad_status} → {new_bmad} (Beads: {beads_status})"
            )
            return

    result.unchanged.append(story.key)


def _refine_bmad_status(base_bmad: str, beads_issue: Issue) -> str:
    """Refine the BMAD status based on Beads issue context.

    E.g., "open" could be "backlog" or "ready-for-dev" depending on
    whether a spec file exists.
    """
    if base_bmad == "backlog":
        # If spec_id is set, it's ready-for-dev
        if beads_issue.spec_id:
            return "ready-for-dev"
    if base_bmad == "in-progress":
        # If metadata has review indicator, use review
        if beads_issue.metadata.get("bmad_status") == "review":
            return "review"
    return base_bmad
