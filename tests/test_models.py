"""Tests for the universal issue model."""

from __future__ import annotations

import pytest

from cli.models import Issue, IssueQuery


class TestIssue:
    def test_defaults(self):
        issue = Issue()
        assert issue.id == ""
        assert issue.priority == 2
        assert issue.status == "open"
        assert issue.labels == []
        assert issue.metadata == {}

    def test_to_dict_omits_empty(self):
        issue = Issue(id="FD-001", title="Test", priority=0)
        d = issue.to_dict()
        assert d["id"] == "FD-001"
        assert d["title"] == "Test"
        assert d["priority"] == 0
        assert "description" not in d
        assert "labels" not in d
        assert "metadata" not in d

    def test_from_beads_json(self):
        data = {
            "id": "FD-abc",
            "title": "Fix bug",
            "description": "Something broken",
            "status": "in_progress",
            "priority": 1,
            "issue_type": "bug",
            "owner": "alice",
            "created_at": "2026-03-01T00:00:00Z",
            "created_by": "Alice",
            "updated_at": "2026-03-01T01:00:00Z",
            "dependency_count": 2,
            "dependent_count": 1,
        }
        issue = Issue.from_beads_json(data)
        assert issue.id == "FD-abc"
        assert issue.title == "Fix bug"
        assert issue.status == "in_progress"
        assert issue.priority == 1
        assert issue.assignee == "alice"
        assert issue.dependency_count == 2

    def test_from_beads_json_missing_fields(self):
        data = {"id": "FD-xyz"}
        issue = Issue.from_beads_json(data)
        assert issue.id == "FD-xyz"
        assert issue.title == ""
        assert issue.priority == 2
        assert issue.status == "open"

    def test_from_github_json(self):
        data = {
            "number": 42,
            "title": "Fix CI",
            "body": "CI is broken",
            "state": "OPEN",
            "labels": [{"name": "bug"}, {"name": "P-high"}],
            "assignees": [{"login": "bob"}],
            "createdAt": "2026-03-01T00:00:00Z",
            "url": "https://github.com/org/repo/issues/42",
        }
        issue = Issue.from_github_json(data)
        assert issue.id == "42"
        assert issue.title == "Fix CI"
        assert issue.status == "open"
        assert "bug" in issue.labels
        assert issue.assignee == "bob"
        assert issue.external_ref == "https://github.com/org/repo/issues/42"

    def test_from_github_json_closed(self):
        data = {"number": 1, "state": "CLOSED", "labels": [], "assignees": []}
        issue = Issue.from_github_json(data)
        assert issue.status == "closed"

    def test_priority_label(self):
        assert Issue(priority=0).priority_label() == "critical"
        assert Issue(priority=1).priority_label() == "high"
        assert Issue(priority=2).priority_label() == "medium"
        assert Issue(priority=3).priority_label() == "low"
        assert Issue(priority=4).priority_label() == "backlog"

    def test_labels_independent(self):
        """Each Issue instance should have independent labels list."""
        a = Issue(title="A")
        b = Issue(title="B")
        a.labels.append("x")
        assert b.labels == []

    def test_metadata_independent(self):
        """Each Issue instance should have independent metadata dict."""
        a = Issue(title="A")
        b = Issue(title="B")
        a.metadata["key"] = "val"
        assert b.metadata == {}


class TestIssueQuery:
    def test_defaults(self):
        q = IssueQuery()
        assert q.status == ""
        assert q.limit == 50

    def test_to_bd_args_empty(self):
        q = IssueQuery()
        assert q.to_bd_args() == []

    def test_to_bd_args_full(self):
        q = IssueQuery(
            status="open",
            issue_type="bug",
            labels=["urgent", "backend"],
            assignee="alice",
            parent_id="FD-001",
        )
        args = q.to_bd_args()
        assert "--status" in args
        assert "open" in args
        assert "--type" in args
        assert "bug" in args
        assert args.count("--label") == 2
        assert "--assignee" in args
        assert "--parent" in args

    def test_to_bd_args_all_status(self):
        q = IssueQuery(status="all")
        assert q.to_bd_args() == []
