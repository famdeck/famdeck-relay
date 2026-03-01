"""Tests for transactional safety, conflict alerting, and desync detection."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from cli.sync import (
    SyncTransaction,
    SyncResult,
    sync_statuses,
    check_desync,
    _alert_conflicts,
    _execute_beads_to_bmad,
)
from cli.adapters import BeadsAdapter, AdapterError
from cli.bmad import BMADAdapter
from cli.models import Issue, IssueQuery


SAMPLE_SPRINT_STATUS = """\
# Sprint Status — Test
# generated: 2026-03-01

development_status:
  epic-1: in-progress
  1-1-feature-a: done
  1-2-feature-b: in-progress
  1-3-feature-c: ready-for-dev
"""


def _beads_issue(bmad_key: str, beads_status: str, bmad_status: str, **kwargs) -> dict:
    return {
        "id": f"FD-{bmad_key[:3]}",
        "title": f"Story for {bmad_key}",
        "status": beads_status,
        "priority": 2,
        "issue_type": "feature",
        "labels": ["bmad", f"bmad:{bmad_key}"],
        "metadata": {"bmad_key": bmad_key, "bmad_status": bmad_status, **kwargs},
    }


def _mock_run(stdout="", returncode=0, stderr=""):
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


@pytest.fixture
def project(tmp_path: Path) -> Path:
    artifacts = tmp_path / "_bmad-output" / "implementation-artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "sprint-status.yaml").write_text(SAMPLE_SPRINT_STATUS)
    return tmp_path


class TestSyncTransaction:
    def test_defaults(self):
        txn = SyncTransaction(story_key="1-1-test")
        assert txn.story_key == "1-1-test"
        assert not txn.beads_updated
        assert not txn.bmad_updated
        assert not txn.rolled_back
        assert txn.error == ""

    def test_direction_fields(self):
        txn = SyncTransaction(
            story_key="1-1-test",
            direction="bmad_to_beads",
            beads_status_before="open",
            beads_status_after="in_progress",
        )
        assert txn.direction == "bmad_to_beads"
        assert txn.beads_status_before == "open"


class TestRollback:
    """Test that Beads→BMAD sync rolls back on partial failure."""

    def test_rollback_on_beads_metadata_failure(self, project: Path):
        """If BMAD update succeeds but Beads metadata update fails, BMAD is rolled back."""
        bmad = BMADAdapter(project)
        beads = MagicMock(spec=BeadsAdapter)

        # Beads update raises
        beads.update.side_effect = AdapterError("bd update failed")

        story = MagicMock()
        story.key = "1-2-feature-b"
        beads_issue = Issue(
            id="FD-123",
            status="closed",
            metadata={"bmad_key": "1-2-feature-b", "bmad_status": "in-progress"},
        )

        txn = SyncTransaction(
            story_key="1-2-feature-b",
            direction="beads_to_bmad",
            bmad_status_before="in-progress",
            bmad_status_after="done",
            beads_metadata_before=dict(beads_issue.metadata),
            beads_metadata_after={**beads_issue.metadata, "bmad_status": "done"},
        )

        result = SyncResult()

        with pytest.raises(AdapterError):
            _execute_beads_to_bmad(bmad, beads, story, beads_issue, txn, result)

        # BMAD should be rolled back to original
        assert txn.bmad_updated  # step 1 succeeded
        assert txn.rolled_back  # rollback happened
        assert len(result.rollbacks) == 1
        assert "rolled back" in result.rollbacks[0]

        # Verify BMAD was set back to original
        current_status = bmad.get_story_status("1-2-feature-b")
        assert current_status == "in-progress"  # rolled back

    def test_no_rollback_when_bmad_update_fails(self, project: Path):
        """If BMAD update itself fails, no rollback needed."""
        bmad = MagicMock(spec=BMADAdapter)
        bmad.set_story_status.side_effect = KeyError("key not found")

        beads = MagicMock(spec=BeadsAdapter)
        story = MagicMock()
        story.key = "1-2-feature-b"
        beads_issue = Issue(id="FD-123", status="closed", metadata={})

        txn = SyncTransaction(
            story_key="1-2-feature-b",
            direction="beads_to_bmad",
            bmad_status_before="in-progress",
            bmad_status_after="done",
        )

        result = SyncResult()

        with pytest.raises(KeyError):
            _execute_beads_to_bmad(bmad, beads, story, beads_issue, txn, result)

        assert not txn.bmad_updated
        assert not txn.rolled_back
        assert len(result.rollbacks) == 0


class TestSyncTransactionalIntegration:
    """Integration test: sync with simulated partial failure."""

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_sync_records_rollback_on_error(self, mock_which, mock_run, project: Path):
        """Full sync with one story causing a rollback still processes others."""
        existing = [
            _beads_issue("1-2-feature-b", "closed", "in-progress"),  # Beads changed → done
        ]
        call_count = [0]

        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            if cmd[1] == "list":
                return _mock_run(stdout=json.dumps(existing))
            if cmd[1] == "update":
                # First update = BMAD metadata, simulate failure
                raise Exception("Connection refused")
            return _mock_run()

        mock_run.side_effect = side_effect
        result = sync_statuses(project, dry_run=False)

        # The error should be captured (not crash)
        assert len(result.errors) >= 1


class TestConflictAlerting:
    def test_alert_conflicts_creates_issues(self):
        beads = MagicMock(spec=BeadsAdapter)
        beads.create.return_value = Issue(id="FD-conflict-1")

        result = SyncResult()
        result.conflicts = [
            "1-2-feature-b: BMAD=done, Beads=open, last_known=in-progress"
        ]

        _alert_conflicts(beads, result)

        assert beads.create.call_count == 1
        assert len(result.conflict_issues) == 1
        assert result.conflict_issues[0] == "FD-conflict-1"

        # Verify issue details
        created_issue = beads.create.call_args[0][0]
        assert "sync-conflict" in created_issue.labels
        assert created_issue.issue_type == "bug"
        assert created_issue.priority == 1

    def test_alert_conflicts_handles_creation_failure(self):
        beads = MagicMock(spec=BeadsAdapter)
        beads.create.side_effect = AdapterError("bd create failed")

        result = SyncResult()
        result.conflicts = ["1-2-feature-b: BMAD=done, Beads=open, last_known=in-progress"]

        _alert_conflicts(beads, result)

        assert len(result.conflict_issues) == 0
        assert any("alert failed" in e for e in result.errors)

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    @patch("cli.sync._sync_one")
    def test_sync_with_alert_conflicts_flag(self, mock_sync_one, mock_which, mock_run, project: Path):
        """Conflicts with alert_conflicts=True create Beads issues."""
        existing = [_beads_issue("1-2-feature-b", "open", "in-progress")]

        def list_side_effect(cmd, **kwargs):
            if cmd[1] == "list":
                return _mock_run(stdout=json.dumps(existing))
            if cmd[1] == "create":
                return _mock_run(stdout="FD-conflict")
            return _mock_run()

        mock_run.side_effect = list_side_effect

        def fake_sync_one(*, bmad, beads, story, beads_issue, direction, dry_run, result):
            result.conflicts.append(f"{story.key}: BMAD=done, Beads=open")

        mock_sync_one.side_effect = fake_sync_one
        result = sync_statuses(project, alert_conflicts=True)

        assert len(result.conflicts) >= 1
        # _alert_conflicts should have been called — created an issue via bd create
        assert len(result.conflict_issues) >= 1


class TestCheckDesync:
    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_detects_desync(self, mock_which, mock_run, project: Path):
        """Desync detected when Beads status doesn't match expected."""
        existing = [
            _beads_issue("1-2-feature-b", "closed", "in-progress"),  # should be in_progress
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = check_desync(project)
        assert len(result.desynced) == 1
        assert "1-2-feature-b" in result.desynced[0]

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_no_desync_when_synced(self, mock_which, mock_run, project: Path):
        existing = [
            _beads_issue("1-1-feature-a", "closed", "done"),
            _beads_issue("1-2-feature-b", "in_progress", "in-progress"),
            _beads_issue("1-3-feature-c", "open", "ready-for-dev"),
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = check_desync(project)
        assert len(result.desynced) == 0

    def test_no_sprint_status(self, tmp_path: Path):
        result = check_desync(tmp_path)
        assert len(result.errors) == 1
        assert "not found" in result.errors[0]

    @patch("cli.adapters.shutil.which", return_value=None)
    def test_bd_not_available(self, mock_which, project: Path):
        result = check_desync(project)
        assert "bd CLI" in result.errors[0]

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_metadata_desync(self, mock_which, mock_run, project: Path):
        """Detects when metadata.bmad_status doesn't match BMAD."""
        existing = [
            _beads_issue("1-2-feature-b", "in_progress", "backlog"),  # metadata stale
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = check_desync(project)
        assert len(result.desynced) == 1
        assert "metadata.bmad_status" in result.desynced[0]


class TestSyncResultExtended:
    def test_rollbacks_in_dict(self):
        r = SyncResult()
        r.rollbacks = ["1-1: rolled back"]
        d = r.to_dict()
        assert "rollbacks" in d
        assert len(d["rollbacks"]) == 1

    def test_conflict_issues_in_dict(self):
        r = SyncResult()
        r.conflict_issues = ["FD-001"]
        d = r.to_dict()
        assert "conflict_issues" in d

    def test_desynced_in_dict(self):
        r = SyncResult()
        r.desynced = ["1-1: Beads=closed, expected=open"]
        d = r.to_dict()
        assert "desynced" in d

    def test_empty_result_no_extra_keys(self):
        r = SyncResult()
        d = r.to_dict()
        assert "rollbacks" not in d
        assert "conflict_issues" not in d
        assert "desynced" not in d
