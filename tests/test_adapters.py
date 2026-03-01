"""Tests for BeadsAdapter and legacy adapter functions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from cli.adapters import (
    AdapterError,
    BeadsAdapter,
    check_adapter,
    create_issue,
    list_issues,
)
from cli.models import Issue, IssueQuery


# --- BeadsAdapter tests ---

class TestBeadsAdapter:
    @pytest.fixture
    def adapter(self, tmp_path):
        return BeadsAdapter(project_path=str(tmp_path))

    def _mock_run(self, stdout="", returncode=0, stderr=""):
        mock = MagicMock()
        mock.stdout = stdout
        mock.stderr = stderr
        mock.returncode = returncode
        return mock

    @patch("cli.adapters.shutil.which", return_value="/usr/local/bin/bd")
    def test_available(self, mock_which):
        adapter = BeadsAdapter()
        assert adapter.available()
        mock_which.assert_called_with("bd")

    @patch("cli.adapters.shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        adapter = BeadsAdapter()
        assert not adapter.available()

    @patch("cli.adapters.subprocess.run")
    def test_create_minimal(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(stdout="FD-new")
        issue = Issue(title="Test issue", issue_type="task", priority=2)
        result = adapter.create(issue)
        assert result.id == "FD-new"
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "bd"
        assert cmd[1] == "create"
        assert "Test issue" in cmd
        assert "--silent" in cmd

    @patch("cli.adapters.subprocess.run")
    def test_create_with_rich_fields(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(stdout="FD-rich")
        issue = Issue(
            title="Story 1.1",
            description="Implement feature",
            issue_type="feature",
            priority=1,
            labels=["sprint-1", "epic-1"],
            assignee="alice",
            spec_id="_bmad-output/stories/1.1.md",
            external_ref="gh-42",
            parent_id="FD-epic",
            acceptance="AC1: Must pass tests",
            notes="From sprint planning",
        )
        result = adapter.create(issue)
        assert result.id == "FD-rich"
        cmd = mock_run.call_args_list[0][0][0]
        assert "--spec-id" in cmd
        assert "--external-ref" in cmd
        assert "--parent" in cmd
        assert "--acceptance" in cmd
        assert "--notes" in cmd

    @patch("cli.adapters.subprocess.run")
    def test_create_with_metadata(self, mock_run, adapter):
        # First call: create (returns ID), second call: update (sets metadata)
        mock_run.side_effect = [
            self._mock_run(stdout="FD-meta"),
            self._mock_run(stdout=""),
        ]
        issue = Issue(
            title="With metadata",
            metadata={"bmad_status": "ready-for-dev", "source_system": "bmad"},
        )
        result = adapter.create(issue)
        assert result.id == "FD-meta"
        # Verify update call was made for metadata
        assert mock_run.call_count == 2
        update_cmd = mock_run.call_args_list[1][0][0]
        assert "update" in update_cmd
        assert "--metadata" in update_cmd

    @patch("cli.adapters.subprocess.run")
    def test_create_failure(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(returncode=1, stderr="db locked")
        issue = Issue(title="Fail")
        with pytest.raises(AdapterError, match="bd create failed"):
            adapter.create(issue)

    @patch("cli.adapters.subprocess.run")
    def test_update_fields(self, mock_run, adapter):
        mock_run.return_value = self._mock_run()
        adapter.update("FD-001", status="in_progress", priority=0)
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["bd", "update", "FD-001"]
        assert "--status" in cmd
        assert "--priority" in cmd

    @patch("cli.adapters.subprocess.run")
    def test_update_metadata(self, mock_run, adapter):
        mock_run.return_value = self._mock_run()
        adapter.update("FD-001", metadata={"key": "val"})
        cmd = mock_run.call_args[0][0]
        assert "--metadata" in cmd
        idx = cmd.index("--metadata")
        assert json.loads(cmd[idx + 1]) == {"key": "val"}

    @patch("cli.adapters.subprocess.run")
    def test_update_labels(self, mock_run, adapter):
        mock_run.return_value = self._mock_run()
        adapter.update("FD-001", add_labels=["a", "b"], remove_labels=["c"])
        cmd = mock_run.call_args[0][0]
        assert cmd.count("--add-label") == 2
        assert cmd.count("--remove-label") == 1

    @patch("cli.adapters.subprocess.run")
    def test_update_noop(self, mock_run, adapter):
        adapter.update("FD-001")
        mock_run.assert_not_called()

    @patch("cli.adapters.subprocess.run")
    def test_close(self, mock_run, adapter):
        mock_run.return_value = self._mock_run()
        adapter.close("FD-001")
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["bd", "close", "FD-001"]

    @patch("cli.adapters.subprocess.run")
    def test_close_with_reason(self, mock_run, adapter):
        mock_run.return_value = self._mock_run()
        adapter.close("FD-001", reason="Duplicate")
        cmd = mock_run.call_args[0][0]
        assert "--reason" in cmd
        assert "Duplicate" in cmd

    @patch("cli.adapters.subprocess.run")
    def test_close_failure(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(returncode=1, stderr="not found")
        with pytest.raises(AdapterError, match="bd close failed"):
            adapter.close("FD-999")

    @patch("cli.adapters.subprocess.run")
    def test_show(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(
            stdout=json.dumps([{
                "id": "FD-001",
                "title": "Test",
                "status": "open",
                "priority": 2,
                "issue_type": "task",
            }])
        )
        issue = adapter.show("FD-001")
        assert issue is not None
        assert issue.id == "FD-001"
        assert issue.title == "Test"

    @patch("cli.adapters.subprocess.run")
    def test_show_not_found(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(returncode=1, stderr="not found")
        issue = adapter.show("FD-999")
        assert issue is None

    @patch("cli.adapters.subprocess.run")
    def test_list_default(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(
            stdout=json.dumps([
                {"id": "FD-001", "title": "A", "status": "open", "priority": 2, "issue_type": "task"},
                {"id": "FD-002", "title": "B", "status": "open", "priority": 1, "issue_type": "bug"},
            ])
        )
        issues = adapter.list()
        assert len(issues) == 2
        assert issues[0].id == "FD-001"
        assert issues[1].priority == 1

    @patch("cli.adapters.subprocess.run")
    def test_list_with_query(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(stdout="[]")
        query = IssueQuery(status="open", issue_type="bug")
        adapter.list(query)
        cmd = mock_run.call_args[0][0]
        assert "--status" in cmd
        assert "open" in cmd
        assert "--type" in cmd
        assert "bug" in cmd

    @patch("cli.adapters.subprocess.run")
    def test_add_dependency(self, mock_run, adapter):
        mock_run.return_value = self._mock_run()
        adapter.add_dependency("FD-002", "FD-001")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["bd", "dep", "add", "FD-002", "FD-001"]

    @patch("cli.adapters.subprocess.run")
    def test_ready(self, mock_run, adapter):
        mock_run.return_value = self._mock_run(
            stdout=json.dumps([
                {"id": "FD-003", "title": "Ready task", "status": "open", "priority": 0, "issue_type": "feature"},
            ])
        )
        issues = adapter.ready()
        assert len(issues) == 1
        assert issues[0].id == "FD-003"


# --- Legacy function tests ---

class TestCheckAdapter:
    @patch("cli.adapters.shutil.which", return_value="/usr/local/bin/bd")
    def test_beads_available(self, mock_which):
        result = check_adapter("beads")
        assert result["available"]
        assert result["tool"] == "bd"

    @patch("cli.adapters.shutil.which", return_value=None)
    def test_beads_not_available(self, mock_which):
        result = check_adapter("beads")
        assert not result["available"]

    def test_gitlab_mcp(self):
        result = check_adapter("gitlab")
        assert result["available"]
        assert result.get("needs_mcp")

    def test_unknown(self):
        result = check_adapter("unknown")
        assert result["install_hint"] == "Unknown tracker type"


class TestCreateIssue:
    @patch("cli.adapters.subprocess.run")
    def test_beads_create(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="FD-new", stderr="")
        result = create_issue(
            tracker={"type": "beads"},
            title="Test",
            body="desc",
            issue_type="task",
            priority="medium",
            labels=["test"],
        )
        assert result["status"] == "ok"

    def test_unknown_adapter(self):
        result = create_issue(
            tracker={"type": "unknown"},
            title="Test",
            body="",
            issue_type="task",
            priority="medium",
            labels=[],
        )
        assert result["status"] == "error"

    def test_gitlab_returns_mcp(self):
        result = create_issue(
            tracker={"type": "gitlab", "project_id": "group/proj"},
            title="Test",
            body="",
            issue_type="bug",
            priority="high",
            labels=[],
        )
        assert result["status"] == "needs_mcp"
        assert "gitlab" in result["tool"]
