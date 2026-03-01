"""Sync engine — bidirectional status sync between BMAD and Beads."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .adapters import BeadsAdapter, AdapterError
from .bmad import BMADAdapter, BMAD_TO_BEADS_STATUS, BEADS_TO_BMAD_STATUS
from .models import Issue, IssueQuery

logger = logging.getLogger(__name__)


@dataclass
class SyncTransaction:
    """Captures before/after state for a single sync operation, enabling rollback."""

    story_key: str
    direction: str = ""  # "bmad_to_beads" | "beads_to_bmad"

    # Before state
    bmad_status_before: str = ""
    beads_status_before: str = ""
    beads_metadata_before: dict = field(default_factory=dict)

    # After state (intended)
    bmad_status_after: str = ""
    beads_status_after: str = ""
    beads_metadata_after: dict = field(default_factory=dict)

    # Execution tracking
    beads_updated: bool = False
    bmad_updated: bool = False
    rolled_back: bool = False
    error: str = ""


class SyncResult:
    """Result of a sync operation."""

    def __init__(self):
        self.bmad_to_beads: list[str] = []  # story keys synced BMAD → Beads
        self.beads_to_bmad: list[str] = []  # story keys synced Beads → BMAD
        self.conflicts: list[str] = []  # both changed — needs resolution
        self.unchanged: list[str] = []
        self.errors: list[str] = []
        self.rollbacks: list[str] = []  # rolled-back transactions
        self.conflict_issues: list[str] = []  # Beads issue IDs for conflicts
        self.desynced: list[str] = []  # desync entries (check mode)

    def to_dict(self) -> dict:
        d = {
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
        if self.rollbacks:
            d["rollbacks"] = self.rollbacks
        if self.conflict_issues:
            d["conflict_issues"] = self.conflict_issues
        if self.desynced:
            d["desynced"] = self.desynced
        return d


def check_desync(
    project_path: str | Path,
    config_defaults: Optional[dict] = None,
) -> SyncResult:
    """Check for desynchronization without making changes.

    Reads both BMAD and Beads state and reports any mismatches.
    """
    project_path = Path(project_path).resolve()
    result = SyncResult()
    defaults = config_defaults or {}

    bmad = BMADAdapter(project_path, sprint_status_paths=defaults.get("sprint_status_paths"))
    if not bmad.exists():
        result.errors.append("sprint-status.yaml not found")
        return result

    beads = BeadsAdapter(project_path=str(project_path),
                         cli_timeout=defaults.get("cli_timeout", 30))
    if not beads.available():
        result.errors.append("bd CLI not available")
        return result

    stories = bmad.list_stories()
    story_by_key = {s.key: s for s in stories}

    beads_issues = beads.list(IssueQuery(labels=["bmad"]))
    beads_by_key = _index_beads_by_key(beads_issues)

    for story_key, story in story_by_key.items():
        beads_issue = beads_by_key.get(story_key)
        if not beads_issue:
            continue

        expected_beads = BMAD_TO_BEADS_STATUS.get(story.status, "open")
        last_known = beads_issue.metadata.get("bmad_status", "")

        issues = []
        if beads_issue.status != expected_beads:
            issues.append(f"Beads={beads_issue.status}, expected={expected_beads}")
        if last_known and last_known != story.status:
            issues.append(f"metadata.bmad_status={last_known}, BMAD={story.status}")

        if issues:
            result.desynced.append(f"{story_key}: {'; '.join(issues)}")

    return result


def sync_statuses(
    project_path: str | Path,
    direction: str = "auto",
    dry_run: bool = False,
    alert_conflicts: bool = False,
    config_defaults: Optional[dict] = None,
) -> SyncResult:
    """Synchronize BMAD sprint-status.yaml ↔ Beads issue statuses.

    Direction:
        "auto" — detect which side changed based on metadata.bmad_status
        "bmad-to-beads" — force BMAD as source of truth
        "beads-to-bmad" — force Beads as source of truth

    Args:
        alert_conflicts: If True, create Beads issues for detected conflicts.
    """
    project_path = Path(project_path).resolve()
    result = SyncResult()
    defaults = config_defaults or {}

    bmad = BMADAdapter(project_path, sprint_status_paths=defaults.get("sprint_status_paths"))
    if not bmad.exists():
        result.errors.append("sprint-status.yaml not found")
        return result

    beads = BeadsAdapter(project_path=str(project_path),
                         cli_timeout=defaults.get("cli_timeout", 30))
    if not beads.available():
        result.errors.append("bd CLI not available")
        return result

    # Get BMAD stories
    stories = bmad.list_stories()
    story_by_key = {s.key: s for s in stories}

    # Get Beads issues with bmad label
    beads_issues = beads.list(IssueQuery(labels=["bmad"]))
    beads_by_key = _index_beads_by_key(beads_issues)

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

    # Create Beads issues for conflicts if requested
    if alert_conflicts and result.conflicts and not dry_run:
        _alert_conflicts(beads, result)

    return result


def _index_beads_by_key(beads_issues: list[Issue]) -> dict[str, Issue]:
    """Build a dict mapping bmad_key → Issue from a list of Beads issues."""
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
    return beads_by_key


def _sync_one(
    bmad: BMADAdapter,
    beads: BeadsAdapter,
    story,
    beads_issue: Issue,
    direction: str,
    dry_run: bool,
    result: SyncResult,
) -> None:
    """Sync a single story/issue pair with transactional rollback."""
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
            txn = SyncTransaction(
                story_key=story.key,
                direction="bmad_to_beads",
                beads_status_before=beads_status,
                beads_metadata_before=dict(beads_issue.metadata),
                beads_status_after=expected_beads,
                beads_metadata_after={**beads_issue.metadata, "bmad_status": bmad_status},
            )
            _execute_bmad_to_beads(beads, beads_issue, txn, result)
        result.bmad_to_beads.append(
            f"{story.key}: {beads_status} → {expected_beads} (BMAD: {bmad_status})"
        )
        return

    if beads_changed:
        # Beads → BMAD
        new_bmad = _refine_bmad_status(expected_bmad, beads_issue)
        if new_bmad != bmad_status:
            if not dry_run:
                txn = SyncTransaction(
                    story_key=story.key,
                    direction="beads_to_bmad",
                    bmad_status_before=bmad_status,
                    beads_metadata_before=dict(beads_issue.metadata),
                    bmad_status_after=new_bmad,
                    beads_metadata_after={**beads_issue.metadata, "bmad_status": new_bmad},
                )
                _execute_beads_to_bmad(bmad, beads, story, beads_issue, txn, result)
            result.beads_to_bmad.append(
                f"{story.key}: {bmad_status} → {new_bmad} (Beads: {beads_status})"
            )
            return

    result.unchanged.append(story.key)


def _execute_bmad_to_beads(
    beads: BeadsAdapter,
    beads_issue: Issue,
    txn: SyncTransaction,
    result: SyncResult,
) -> None:
    """Execute BMAD→Beads sync with rollback on failure."""
    try:
        beads.update(beads_issue.id,
                     status=txn.beads_status_after,
                     metadata=txn.beads_metadata_after)
        txn.beads_updated = True
    except (AdapterError, Exception) as e:
        txn.error = str(e)
        result.errors.append(f"{txn.story_key}: Beads update failed: {e}")
        raise


def _execute_beads_to_bmad(
    bmad: BMADAdapter,
    beads: BeadsAdapter,
    story,
    beads_issue: Issue,
    txn: SyncTransaction,
    result: SyncResult,
) -> None:
    """Execute Beads→BMAD sync with rollback on partial failure.

    Two-step write:
      1. Update BMAD sprint-status.yaml
      2. Update Beads metadata to record new bmad_status

    If step 2 fails, roll back step 1.
    """
    # Step 1: Update BMAD
    try:
        bmad.set_story_status(story.key, txn.bmad_status_after)
        txn.bmad_updated = True
    except Exception as e:
        txn.error = str(e)
        result.errors.append(f"{txn.story_key}: BMAD update failed: {e}")
        raise

    # Step 2: Update Beads metadata
    try:
        beads.update(beads_issue.id,
                     metadata=txn.beads_metadata_after)
        txn.beads_updated = True
    except (AdapterError, Exception) as e:
        # Step 2 failed — roll back step 1
        txn.error = str(e)
        logger.warning("Rolling back BMAD update for %s: Beads metadata update failed: %s",
                       txn.story_key, e)
        try:
            bmad.set_story_status(story.key, txn.bmad_status_before)
            txn.rolled_back = True
            result.rollbacks.append(
                f"{txn.story_key}: rolled back BMAD {txn.bmad_status_after} → {txn.bmad_status_before}"
            )
        except Exception as rb_err:
            logger.error("Rollback failed for %s: %s", txn.story_key, rb_err)
            result.errors.append(
                f"{txn.story_key}: PARTIAL SYNC — BMAD={txn.bmad_status_after} but Beads metadata stale. "
                f"Rollback also failed: {rb_err}"
            )
            raise
        result.errors.append(f"{txn.story_key}: Beads metadata update failed (rolled back): {e}")
        raise


def _alert_conflicts(beads: BeadsAdapter, result: SyncResult) -> None:
    """Create Beads issues for sync conflicts so they don't go unnoticed."""
    for conflict_desc in result.conflicts:
        story_key = conflict_desc.split(":")[0].strip()
        try:
            created = beads.create(Issue(
                title=f"Sync conflict: {story_key}",
                description=(
                    f"Bidirectional sync detected a conflict for story {story_key}.\n\n"
                    f"Details: {conflict_desc}\n\n"
                    f"Both BMAD and Beads changed since last sync. "
                    f"Resolve by choosing a direction:\n"
                    f"  relay sync --direction bmad-to-beads\n"
                    f"  relay sync --direction beads-to-bmad"
                ),
                issue_type="bug",
                priority=1,
                labels=["sync-conflict", "bmad", f"bmad:{story_key}"],
                source_system="relay",
            ))
            result.conflict_issues.append(created.id)
            logger.info("Created conflict issue %s for %s", created.id, story_key)
        except Exception as e:
            logger.warning("Failed to create conflict issue for %s: %s", story_key, e)
            result.errors.append(f"Conflict alert failed for {story_key}: {e}")


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
