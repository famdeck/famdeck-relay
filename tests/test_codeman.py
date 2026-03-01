"""Tests for Codeman adapter — Ralph Loop session and plan task status."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from cli.codeman import CodemanAdapter, PlanTask, SessionStatus


class TestPlanTask:
    def test_from_json(self):
        data = {
            "id": "task-1",
            "content": "Implement feature",
            "status": "completed",
            "priority": 1,
            "attempts": 2,
            "lastError": "",
        }
        task = PlanTask.from_json(data)
        assert task.id == "task-1"
        assert task.status == "completed"
        assert task.attempts == 2

    def test_from_json_minimal(self):
        task = PlanTask.from_json({})
        assert task.status == "pending"
        assert task.content == ""


class TestSessionStatus:
    def test_progress_with_tasks(self):
        status = SessionStatus(
            session_id="s-1",
            state="running",
            iteration=5,
            max_iterations=50,
            plan_tasks=[
                PlanTask(id="1", status="completed"),
                PlanTask(id="2", status="completed"),
                PlanTask(id="3", status="in_progress"),
                PlanTask(id="4", status="pending"),
            ],
        )
        assert "2/4 tasks done" in status.progress
        assert "running" in status.progress

    def test_progress_without_tasks(self):
        status = SessionStatus(state="running", iteration=3, max_iterations=50)
        assert "running" in status.progress
        assert "3/50" in status.progress

    def test_to_dict(self):
        status = SessionStatus(
            session_id="s-1",
            state="completed",
            plan_tasks=[PlanTask(id="1", content="Task", status="completed")],
        )
        d = status.to_dict()
        assert d["session_id"] == "s-1"
        assert len(d["plan_tasks"]) == 1
        assert "progress" in d


class TestCodemanAdapter:
    @pytest.fixture
    def adapter(self):
        return CodemanAdapter(api_url="http://localhost:3000", password="test")

    def _mock_response(self, data: dict):
        mock = MagicMock()
        mock.read.return_value = json.dumps(data).encode()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    @patch("cli.codeman.urllib.request.urlopen")
    def test_get_session_status(self, mock_urlopen, adapter):
        mock_urlopen.return_value = self._mock_response({
            "state": "running",
            "iteration": 5,
            "maxIterations": 50,
            "planTasks": [
                {"id": "1", "content": "Build", "status": "completed"},
                {"id": "2", "content": "Test", "status": "in_progress"},
            ],
        })
        status = adapter.get_session_status("s-123")
        assert status.state == "running"
        assert status.iteration == 5
        assert len(status.plan_tasks) == 2
        assert status.plan_tasks[0].status == "completed"

    @patch("cli.codeman.urllib.request.urlopen")
    def test_get_session_status_api_down(self, mock_urlopen, adapter):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("refused")
        status = adapter.get_session_status("s-123")
        assert status.state == "unknown"
        assert "Could not reach" in status.error

    @patch("cli.codeman.urllib.request.urlopen")
    def test_is_session_complete_true(self, mock_urlopen, adapter):
        mock_urlopen.return_value = self._mock_response({"state": "completed"})
        assert adapter.is_session_complete("s-done") is True

    @patch("cli.codeman.urllib.request.urlopen")
    def test_is_session_complete_false(self, mock_urlopen, adapter):
        mock_urlopen.return_value = self._mock_response({"state": "running"})
        assert adapter.is_session_complete("s-running") is False

    @patch("cli.codeman.urllib.request.urlopen")
    def test_is_session_complete_failed(self, mock_urlopen, adapter):
        mock_urlopen.return_value = self._mock_response({"state": "failed"})
        assert adapter.is_session_complete("s-fail") is True

    @patch("cli.codeman.urllib.request.urlopen")
    def test_list_sessions(self, mock_urlopen, adapter):
        mock_urlopen.return_value = self._mock_response({
            "sessions": [{"id": "s-1"}, {"id": "s-2"}]
        })
        sessions = adapter.list_sessions()
        assert len(sessions) == 2

    @patch("cli.codeman.urllib.request.urlopen")
    def test_list_sessions_empty(self, mock_urlopen, adapter):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("refused")
        assert adapter.list_sessions() == []

    def test_headers_with_password(self, adapter):
        headers = adapter._headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test"

    def test_headers_without_password(self):
        adapter = CodemanAdapter(password="")
        headers = adapter._headers()
        assert "Authorization" not in headers
