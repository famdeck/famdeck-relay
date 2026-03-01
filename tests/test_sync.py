"""Tests for sync engine — bidirectional BMAD ↔ Beads status sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli.sync import SyncResult, sync_statuses, _refine_bmad_status
from cli.models import Issue

SAMPLE_SPRINT_STATUS = """\
# Sprint Status — Test
# generated: 2026-03-01
# project: test

development_status:
  epic-1: in-progress
  1-1-feature-a: done
  1-2-feature-b: in-progress
  1-3-feature-c: ready-for-dev
  1-4-feature-d: backlog
"""


def _beads_issue(bmad_key: str, beads_status: str, bmad_status: str, **kwargs) -> dict:
    """Helper to create a Beads issue JSON dict."""
    return {
        "id": f"FD-{bmad_key[:3]}",
        "title": f"Story for {bmad_key}",
        "status": beads_status,
        "priority": 2,
        "issue_type": "feature",
        "labels": ["bmad", f"bmad:{bmad_key}"],
        "metadata": {"bmad_key": bmad_key, "bmad_status": bmad_status, **kwargs},
    }


@pytest.fixture
def project(tmp_path: Path) -> Path:
    artifacts = tmp_path / "_bmad-output" / "implementation-artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "sprint-status.yaml").write_text(SAMPLE_SPRINT_STATUS)
    return tmp_path


def _mock_run(stdout="", returncode=0, stderr=""):
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


class TestSyncResult:
    def test_empty(self):
        r = SyncResult()
        d = r.to_dict()
        assert "0 BMAD→Beads" in d["summary"]
        assert "0 conflicts" in d["summary"]

    def test_with_data(self):
        r = SyncResult()
        r.bmad_to_beads = ["a"]
        r.beads_to_bmad = ["b", "c"]
        r.conflicts = ["d"]
        d = r.to_dict()
        assert "1 BMAD→Beads" in d["summary"]
        assert "2 Beads→BMAD" in d["summary"]


class TestSyncStatuses:
    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_all_synced(self, mock_which, mock_run, project: Path):
        """All Beads issues match BMAD statuses — nothing to sync."""
        existing = [
            _beads_issue("1-1-feature-a", "closed", "done"),
            _beads_issue("1-2-feature-b", "in_progress", "in-progress"),
            _beads_issue("1-3-feature-c", "open", "ready-for-dev"),
            _beads_issue("1-4-feature-d", "open", "backlog"),
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = sync_statuses(project)
        assert len(result.unchanged) == 4
        assert len(result.bmad_to_beads) == 0
        assert len(result.beads_to_bmad) == 0

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_bmad_changed(self, mock_which, mock_run, project: Path):
        """BMAD story advanced from backlog → in-progress, Beads should update."""
        # Beads still shows "open" with bmad_status "backlog"
        # But BMAD now shows "in-progress"
        existing = [
            _beads_issue("1-2-feature-b", "open", "backlog"),  # stale
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = sync_statuses(project, dry_run=True)
        assert len(result.bmad_to_beads) == 1
        assert "1-2-feature-b" in result.bmad_to_beads[0]

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_beads_changed(self, mock_which, mock_run, project: Path):
        """Beads status changed (closed) but BMAD still shows in-progress."""
        existing = [
            _beads_issue("1-2-feature-b", "closed", "in-progress"),  # Beads ahead
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = sync_statuses(project, dry_run=True)
        assert len(result.beads_to_bmad) == 1
        assert "1-2-feature-b" in result.beads_to_bmad[0]

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_force_bmad_to_beads(self, mock_which, mock_run, project: Path):
        """Force BMAD→Beads direction."""
        existing = [
            _beads_issue("1-2-feature-b", "open", "backlog"),
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = sync_statuses(project, direction="bmad-to-beads", dry_run=True)
        assert len(result.bmad_to_beads) == 1

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_force_beads_to_bmad(self, mock_which, mock_run, project: Path):
        """Force Beads→BMAD direction."""
        existing = [
            _beads_issue("1-3-feature-c", "in_progress", "ready-for-dev"),
        ]
        mock_run.return_value = _mock_run(stdout=json.dumps(existing))

        result = sync_statuses(project, direction="beads-to-bmad", dry_run=True)
        assert len(result.beads_to_bmad) == 1

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_no_beads_issues(self, mock_which, mock_run, project: Path):
        """No Beads issues with bmad label — all unchanged."""
        mock_run.return_value = _mock_run(stdout="[]")
        result = sync_statuses(project)
        assert len(result.unchanged) == 4

    def test_no_sprint_status(self, tmp_path: Path):
        result = sync_statuses(tmp_path)
        assert len(result.errors) == 1
        assert "not found" in result.errors[0]

    @patch("cli.adapters.shutil.which", return_value=None)
    def test_bd_not_available(self, mock_which, project: Path):
        result = sync_statuses(project)
        assert "bd CLI" in result.errors[0]

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_actual_sync_calls_update(self, mock_which, mock_run, project: Path):
        """Non-dry-run actually calls bd update."""
        existing = [
            _beads_issue("1-2-feature-b", "open", "backlog"),  # BMAD changed
        ]
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append(cmd)
            if cmd[1] == "list":
                return _mock_run(stdout=json.dumps(existing))
            return _mock_run()

        mock_run.side_effect = side_effect
        result = sync_statuses(project, dry_run=False)
        assert len(result.bmad_to_beads) == 1
        # Should have called bd update
        update_calls = [c for c in calls if len(c) > 1 and c[1] == "update"]
        assert len(update_calls) == 1


class TestRefineBmadStatus:
    def test_backlog_with_spec(self):
        issue = Issue(spec_id="some/path.md")
        assert _refine_bmad_status("backlog", issue) == "ready-for-dev"

    def test_backlog_without_spec(self):
        issue = Issue()
        assert _refine_bmad_status("backlog", issue) == "backlog"

    def test_in_progress_passthrough(self):
        issue = Issue()
        assert _refine_bmad_status("in-progress", issue) == "in-progress"

    def test_done_passthrough(self):
        issue = Issue()
        assert _refine_bmad_status("done", issue) == "done"
