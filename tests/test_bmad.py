"""Tests for BMAD adapter — sprint-status.yaml read/write and issue mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.bmad import (
    BMAD_TO_BEADS_STATUS,
    BEADS_TO_BMAD_STATUS,
    BMADAdapter,
    BMADEpic,
    BMADStory,
)

SAMPLE_SPRINT_STATUS = """\
# Sprint Status — TestProject
# generated: 2026-03-01
# project: testproject
# project_key: TP
# tracking_system: file-system
# story_location: "_bmad-output/implementation-artifacts"

# STATUS DEFINITIONS:
# Epic Status: backlog | in-progress | done
# Story Status: backlog | ready-for-dev | in-progress | review | done

development_status:
  # Epic 1: Core Features
  epic-1: in-progress
  1-1-user-authentication: done
  1-2-dashboard-layout: in-progress
  1-3-api-endpoints: ready-for-dev
  1-4-data-validation: backlog
  epic-1-retrospective: optional

  # Epic 2: Integrations
  epic-2: backlog
  2-1-github-integration: backlog
  2-2-slack-notifications: backlog
"""


@pytest.fixture
def sprint_dir(tmp_path: Path) -> Path:
    """Create a temp project with sprint-status.yaml."""
    artifacts = tmp_path / "_bmad-output" / "implementation-artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "sprint-status.yaml").write_text(SAMPLE_SPRINT_STATUS)
    return tmp_path


@pytest.fixture
def adapter(sprint_dir: Path) -> BMADAdapter:
    return BMADAdapter(sprint_dir)


class TestBMADStory:
    def test_from_key_basic(self):
        story = BMADStory.from_key("1-1-user-authentication", "done")
        assert story is not None
        assert story.epic_num == 1
        assert story.story_num == 1
        assert story.title_text == "User Authentication"
        assert story.status == "done"
        assert story.story_id == "1.1"

    def test_from_key_multi_digit(self):
        story = BMADStory.from_key("5-10-relay-sync-engine", "backlog")
        assert story is not None
        assert story.epic_num == 5
        assert story.story_num == 10
        assert story.story_id == "5.10"

    def test_from_key_invalid(self):
        assert BMADStory.from_key("epic-1", "in-progress") is None
        assert BMADStory.from_key("not-a-story", "backlog") is None

    def test_repr(self):
        story = BMADStory.from_key("1-1-test", "done")
        assert "1-1-test" in repr(story)


class TestBMADEpic:
    def test_basic(self):
        epic = BMADEpic(number=1, status="in-progress")
        assert epic.key == "epic-1"
        assert epic.status == "in-progress"
        assert "1" in repr(epic)


class TestBMADAdapter:
    def test_exists(self, adapter: BMADAdapter):
        assert adapter.exists()

    def test_not_exists(self, tmp_path: Path):
        adapter = BMADAdapter(tmp_path / "nonexistent")
        assert not adapter.exists()

    def test_read_raw(self, adapter: BMADAdapter):
        raw = adapter.read_raw()
        assert raw["epic-1"] == "in-progress"
        assert raw["1-1-user-authentication"] == "done"
        assert raw["2-1-github-integration"] == "backlog"

    def test_read_metadata(self, adapter: BMADAdapter):
        meta = adapter.read_metadata()
        assert meta["project"] == "testproject"
        assert meta["project_key"] == "TP"
        assert meta["story_location"] == "_bmad-output/implementation-artifacts"

    def test_list_stories(self, adapter: BMADAdapter):
        stories = adapter.list_stories()
        assert len(stories) == 6
        keys = [s.key for s in stories]
        assert "1-1-user-authentication" in keys
        assert "2-2-slack-notifications" in keys

    def test_list_stories_no_epics_or_retros(self, adapter: BMADAdapter):
        stories = adapter.list_stories()
        keys = [s.key for s in stories]
        assert "epic-1" not in keys
        assert "epic-1-retrospective" not in keys

    def test_list_epics(self, adapter: BMADAdapter):
        epics = adapter.list_epics()
        assert len(epics) == 2
        assert epics[0].number == 1
        assert epics[0].status == "in-progress"
        assert epics[1].number == 2
        assert epics[1].status == "backlog"

    def test_get_story_status(self, adapter: BMADAdapter):
        assert adapter.get_story_status("1-1-user-authentication") == "done"
        assert adapter.get_story_status("1-3-api-endpoints") == "ready-for-dev"
        assert adapter.get_story_status("nonexistent") is None

    def test_set_story_status(self, adapter: BMADAdapter):
        adapter.set_story_status("1-4-data-validation", "ready-for-dev")
        assert adapter.get_story_status("1-4-data-validation") == "ready-for-dev"

    def test_set_story_status_preserves_comments(self, adapter: BMADAdapter):
        adapter.set_story_status("1-4-data-validation", "in-progress")
        content = adapter.status_path.read_text()
        assert "# Epic 1: Core Features" in content
        assert "# Sprint Status" in content

    def test_set_story_status_invalid(self, adapter: BMADAdapter):
        with pytest.raises(ValueError, match="Invalid story status"):
            adapter.set_story_status("1-1-user-authentication", "invalid")

    def test_set_epic_status(self, adapter: BMADAdapter):
        adapter.set_epic_status("epic-2", "in-progress")
        raw = adapter.read_raw()
        assert raw["epic-2"] == "in-progress"

    def test_set_epic_status_invalid(self, adapter: BMADAdapter):
        with pytest.raises(ValueError, match="Invalid epic status"):
            adapter.set_epic_status("epic-1", "review")

    def test_update_key_not_found(self, adapter: BMADAdapter):
        with pytest.raises(KeyError, match="Key not found"):
            adapter._update_key("nonexistent-key", "done")

    def test_to_issues(self, adapter: BMADAdapter):
        issues = adapter.to_issues()
        assert len(issues) == 6

        # Check first story mapping
        auth = [i for i in issues if "1.1" in i.title][0]
        assert auth.status == "closed"  # done → closed
        assert auth.source_system == "bmad"
        assert auth.metadata["bmad_key"] == "1-1-user-authentication"
        assert auth.metadata["bmad_status"] == "done"
        assert "epic-1" in auth.labels
        assert "bmad" in auth.labels
        assert auth.spec_id.endswith("1-1-user-authentication.md")

        # Check in-progress mapping
        dash = [i for i in issues if "1.2" in i.title][0]
        assert dash.status == "in_progress"

        # Check ready-for-dev mapping
        api = [i for i in issues if "1.3" in i.title][0]
        assert api.status == "open"

    def test_next_story(self, adapter: BMADAdapter):
        # Should return first ready-for-dev
        story = adapter.next_story()
        assert story is not None
        assert story.key == "1-3-api-endpoints"
        assert story.status == "ready-for-dev"

    def test_next_story_falls_back_to_backlog(self, sprint_dir: Path):
        # Modify sprint-status to have no ready-for-dev
        path = sprint_dir / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"
        content = path.read_text().replace("ready-for-dev", "done")
        path.write_text(content)
        adapter = BMADAdapter(sprint_dir)
        story = adapter.next_story()
        assert story is not None
        assert story.status == "backlog"

    def test_next_story_none(self, sprint_dir: Path):
        # All stories done
        path = sprint_dir / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"
        content = path.read_text()
        for s in ("backlog", "ready-for-dev", "in-progress", "review"):
            content = content.replace(f": {s}", ": done")
        path.write_text(content)
        adapter = BMADAdapter(sprint_dir)
        assert adapter.next_story() is None

    def test_sprint_counts(self, adapter: BMADAdapter):
        counts = adapter.sprint_counts()
        assert counts["done"] == 1
        assert counts["in-progress"] == 1
        assert counts["ready-for-dev"] == 1
        assert counts["backlog"] == 3


class TestStatusMapping:
    def test_bmad_to_beads_all_statuses(self):
        assert BMAD_TO_BEADS_STATUS["backlog"] == "open"
        assert BMAD_TO_BEADS_STATUS["ready-for-dev"] == "open"
        assert BMAD_TO_BEADS_STATUS["in-progress"] == "in_progress"
        assert BMAD_TO_BEADS_STATUS["review"] == "in_progress"
        assert BMAD_TO_BEADS_STATUS["done"] == "closed"

    def test_beads_to_bmad_all_statuses(self):
        assert BEADS_TO_BMAD_STATUS["open"] == "backlog"
        assert BEADS_TO_BMAD_STATUS["in_progress"] == "in-progress"
        assert BEADS_TO_BMAD_STATUS["closed"] == "done"
