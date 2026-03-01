"""Tests for BMAD import — sync sprint-status.yaml stories into Beads."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from cli.importer import ImportResult, import_bmad_stories, _epic_to_priority

SAMPLE_SPRINT_STATUS = """\
# Sprint Status — Test
# generated: 2026-03-01
# project: test
# project_key: TST
# tracking_system: file-system
# story_location: "_bmad-output/implementation-artifacts"

development_status:
  epic-1: in-progress
  1-1-feature-a: done
  1-2-feature-b: in-progress
  1-3-feature-c: backlog

  epic-2: backlog
  2-1-integration: backlog
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a temp project with sprint-status.yaml."""
    artifacts = tmp_path / "_bmad-output" / "implementation-artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "sprint-status.yaml").write_text(SAMPLE_SPRINT_STATUS)
    return tmp_path


class TestImportResult:
    def test_empty(self):
        r = ImportResult()
        assert r.total == 0
        d = r.to_dict()
        assert "0 created" in d["summary"]

    def test_summary(self):
        r = ImportResult()
        r.created = ["FD-001", "FD-002"]
        r.updated = ["FD-003"]
        r.skipped = ["1-1-test"]
        assert r.total == 4
        d = r.to_dict()
        assert "2 created" in d["summary"]
        assert "1 updated" in d["summary"]
        assert "1 skipped" in d["summary"]


class TestImportBmadStories:
    def _mock_run(self, stdout="", returncode=0, stderr=""):
        mock = MagicMock()
        mock.stdout = stdout
        mock.stderr = stderr
        mock.returncode = returncode
        return mock

    def test_no_sprint_status(self, tmp_path: Path):
        result = import_bmad_stories(tmp_path)
        assert len(result.errors) == 1
        assert "not found" in result.errors[0]

    @patch("cli.adapters.shutil.which", return_value=None)
    def test_bd_not_available(self, mock_which, project: Path):
        result = import_bmad_stories(project)
        assert len(result.errors) == 1
        assert "bd CLI" in result.errors[0]

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_dry_run_creates_nothing(self, mock_which, mock_run, project: Path):
        # bd list returns empty (no existing issues)
        mock_run.return_value = self._mock_run(stdout="[]")
        result = import_bmad_stories(project, dry_run=True)
        assert len(result.created) == 4  # 4 stories
        assert all("dry-run" in c for c in result.created)
        # No bd create calls (only bd list)
        create_calls = [c for c in mock_run.call_args_list
                       if c[0][0][1] == "create"]
        assert len(create_calls) == 0

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_creates_new_issues(self, mock_which, mock_run, project: Path):
        call_count = [0]

        def side_effect(cmd, **kwargs):
            if cmd[1] == "list":
                return self._mock_run(stdout="[]")
            elif cmd[1] == "create":
                call_count[0] += 1
                return self._mock_run(stdout=f"FD-{call_count[0]:03d}")
            elif cmd[1] == "update":
                return self._mock_run()
            return self._mock_run()

        mock_run.side_effect = side_effect
        result = import_bmad_stories(project)
        assert len(result.created) == 4
        assert result.created[0] == "FD-001"

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_skips_synced_issues(self, mock_which, mock_run, project: Path):
        # bd list returns existing issue for story 1-1
        existing_issues = [{
            "id": "FD-exist",
            "title": "Story 1.1: Feature A",
            "status": "closed",
            "priority": 1,
            "issue_type": "feature",
            "labels": ["bmad", "bmad:1-1-feature-a"],
            "metadata": {"bmad_key": "1-1-feature-a", "bmad_status": "done"},
        }]
        call_count = [0]

        def side_effect(cmd, **kwargs):
            if cmd[1] == "list":
                return self._mock_run(stdout=json.dumps(existing_issues))
            elif cmd[1] == "create":
                call_count[0] += 1
                return self._mock_run(stdout=f"FD-new-{call_count[0]}")
            elif cmd[1] == "update":
                return self._mock_run()
            return self._mock_run()

        mock_run.side_effect = side_effect
        result = import_bmad_stories(project)
        # 1-1-feature-a should be skipped (status matches: done → closed)
        assert "1-1-feature-a" in result.skipped
        # Other 3 stories should be created
        assert len(result.created) == 3

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_updates_changed_status(self, mock_which, mock_run, project: Path):
        # Existing issue has "open" but BMAD says "in-progress"
        existing_issues = [{
            "id": "FD-002",
            "title": "Story 1.2: Feature B",
            "status": "open",  # mismatched — BMAD says in-progress → in_progress
            "priority": 1,
            "issue_type": "feature",
            "labels": ["bmad", "bmad:1-2-feature-b"],
            "metadata": {"bmad_key": "1-2-feature-b", "bmad_status": "backlog"},
        }]
        call_count = [0]

        def side_effect(cmd, **kwargs):
            if cmd[1] == "list":
                return self._mock_run(stdout=json.dumps(existing_issues))
            elif cmd[1] == "create":
                call_count[0] += 1
                return self._mock_run(stdout=f"FD-new-{call_count[0]}")
            elif cmd[1] == "update":
                return self._mock_run()
            return self._mock_run()

        mock_run.side_effect = side_effect
        result = import_bmad_stories(project)
        assert "FD-002" in result.updated

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_epic_filter(self, mock_which, mock_run, project: Path):
        call_count = [0]

        def side_effect(cmd, **kwargs):
            if cmd[1] == "list":
                return self._mock_run(stdout="[]")
            elif cmd[1] == "create":
                call_count[0] += 1
                return self._mock_run(stdout=f"FD-{call_count[0]:03d}")
            elif cmd[1] == "update":
                return self._mock_run()
            return self._mock_run()

        mock_run.side_effect = side_effect
        result = import_bmad_stories(project, epic_filter=1)
        # Only epic 1 stories (3 of them)
        assert len(result.created) == 3

    @patch("cli.adapters.subprocess.run")
    @patch("cli.adapters.shutil.which", return_value="/usr/bin/bd")
    def test_create_error_captured(self, mock_which, mock_run, project: Path):
        def side_effect(cmd, **kwargs):
            if cmd[1] == "list":
                return self._mock_run(stdout="[]")
            elif cmd[1] == "create":
                return self._mock_run(returncode=1, stderr="db locked")
            return self._mock_run()

        mock_run.side_effect = side_effect
        result = import_bmad_stories(project)
        assert len(result.errors) == 4  # All 4 stories fail


class TestEpicToPriority:
    def test_epic_1(self):
        assert _epic_to_priority(1) == 1

    def test_epic_2_3(self):
        assert _epic_to_priority(2) == 2
        assert _epic_to_priority(3) == 2

    def test_epic_5_plus(self):
        assert _epic_to_priority(5) == 3
        assert _epic_to_priority(6) == 3
