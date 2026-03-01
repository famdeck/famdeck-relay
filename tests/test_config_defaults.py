"""Tests for configurable defaults from relay.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.config import get_defaults, read_config, write_config
from cli.bmad import BMADAdapter, DEFAULT_SPRINT_STATUS_PATHS
from cli.adapters import BeadsAdapter


class TestGetDefaults:
    def test_all_defaults(self):
        """Empty config returns all default values."""
        defaults = get_defaults({})
        assert defaults["cli_timeout"] == 30
        assert defaults["git_timeout"] == 5
        assert defaults["handoff_timeout"] == 15
        assert defaults["codeman_api_url"] == "http://localhost:3000"
        assert defaults["codeman_timeout"] == 15
        assert defaults["status_list_limit"] == 20
        assert len(defaults["sprint_status_paths"]) == 3

    def test_custom_values(self):
        config = {
            "defaults": {
                "cli_timeout": 60,
                "codeman_api_url": "http://codeman.local:8080",
                "sprint_status_paths": ["custom/sprint-status.yaml"],
            }
        }
        defaults = get_defaults(config)
        assert defaults["cli_timeout"] == 60
        assert defaults["codeman_api_url"] == "http://codeman.local:8080"
        assert defaults["sprint_status_paths"] == ["custom/sprint-status.yaml"]
        # Others stay default
        assert defaults["git_timeout"] == 5

    def test_partial_override(self):
        config = {"defaults": {"cli_timeout": 45}}
        defaults = get_defaults(config)
        assert defaults["cli_timeout"] == 45
        assert defaults["git_timeout"] == 5  # unchanged

    def test_no_defaults_section(self):
        config = {"issue_trackers": [{"name": "beads", "type": "beads"}]}
        defaults = get_defaults(config)
        assert defaults["cli_timeout"] == 30

    def test_roundtrip_config(self, tmp_path: Path):
        """Config with defaults survives write/read cycle."""
        config = {
            "issue_trackers": [{"name": "beads", "type": "beads", "default": True}],
            "defaults": {"cli_timeout": 45, "git_timeout": 10},
        }
        write_config(tmp_path, config)
        loaded = read_config(tmp_path)
        defaults = get_defaults(loaded)
        assert defaults["cli_timeout"] == 45
        assert defaults["git_timeout"] == 10


class TestBMADAdapterPaths:
    def test_default_paths(self, tmp_path: Path):
        adapter = BMADAdapter(tmp_path)
        assert adapter._search_paths == DEFAULT_SPRINT_STATUS_PATHS

    def test_custom_paths(self, tmp_path: Path):
        custom = ["custom/status.yaml"]
        adapter = BMADAdapter(tmp_path, sprint_status_paths=custom)
        assert adapter._search_paths == custom

    def test_custom_path_found(self, tmp_path: Path):
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        status_file = custom_dir / "status.yaml"
        status_file.write_text("development_status:\n  1-1-test: backlog\n")

        adapter = BMADAdapter(tmp_path, sprint_status_paths=["custom/status.yaml"])
        assert adapter.exists()
        stories = adapter.list_stories()
        assert len(stories) == 1


class TestBeadsAdapterTimeout:
    def test_default_timeout(self):
        adapter = BeadsAdapter(project_path="/tmp")
        assert adapter.cli_timeout == 30

    def test_custom_timeout(self):
        adapter = BeadsAdapter(project_path="/tmp", cli_timeout=60)
        assert adapter.cli_timeout == 60
