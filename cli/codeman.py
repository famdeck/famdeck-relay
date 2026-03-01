"""Codeman adapter — query Ralph Loop session and plan task status."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanTask:
    """A plan task from Codeman Ralph Loop."""

    id: str = ""
    content: str = ""
    status: str = "pending"  # pending, in_progress, completed, failed
    priority: int = 0
    attempts: int = 0
    last_error: str = ""

    @classmethod
    def from_json(cls, data: dict) -> PlanTask:
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            status=data.get("status", "pending"),
            priority=data.get("priority", 0),
            attempts=data.get("attempts", 0),
            last_error=data.get("lastError", ""),
        )


@dataclass
class SessionStatus:
    """Status of a Codeman Ralph Loop session."""

    session_id: str = ""
    state: str = "unknown"  # running, completed, failed, unknown
    iteration: int = 0
    max_iterations: int = 0
    plan_tasks: list[PlanTask] = field(default_factory=list)
    error: str = ""

    @property
    def progress(self) -> str:
        """Human-readable progress summary."""
        if not self.plan_tasks:
            return f"{self.state} (iteration {self.iteration}/{self.max_iterations})"
        completed = sum(1 for t in self.plan_tasks if t.status == "completed")
        total = len(self.plan_tasks)
        return f"{completed}/{total} tasks done, {self.state} (iteration {self.iteration})"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "progress": self.progress,
            "plan_tasks": [
                {"id": t.id, "content": t.content, "status": t.status,
                 "attempts": t.attempts}
                for t in self.plan_tasks
            ],
            "error": self.error,
        }


class CodemanAdapter:
    """Query Codeman Ralph Loop for session and plan task status."""

    def __init__(self, api_url: str = "http://localhost:3000", password: str = "",
                 timeout: int = 15):
        self.api_url = api_url.rstrip("/")
        self.password = password
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.password:
            headers["Authorization"] = f"Bearer {self.password}"
        return headers

    def _get(self, path: str) -> Optional[dict]:
        """Make GET request to Codeman API."""
        url = f"{self.api_url}{path}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.warning("Codeman API error %d: %s", e.code, e.read().decode())
            return None
        except urllib.error.URLError as e:
            logger.warning("Codeman API unreachable: %s", e.reason)
            return None
        except Exception as e:
            logger.warning("Codeman API error: %s", e)
            return None

    def get_session_status(self, session_id: str) -> SessionStatus:
        """Get status of a Ralph Loop session."""
        data = self._get(f"/api/ralph-loop/{session_id}/status")
        if not data:
            return SessionStatus(session_id=session_id, state="unknown",
                                 error="Could not reach Codeman API")

        tasks = [PlanTask.from_json(t) for t in data.get("planTasks", [])]
        return SessionStatus(
            session_id=session_id,
            state=data.get("state", "unknown"),
            iteration=data.get("iteration", 0),
            max_iterations=data.get("maxIterations", 0),
            plan_tasks=tasks,
            error=data.get("error", ""),
        )

    def is_session_complete(self, session_id: str) -> bool:
        """Check if a session has completed (successfully or with error)."""
        status = self.get_session_status(session_id)
        return status.state in ("completed", "failed")

    def list_sessions(self) -> list[dict]:
        """List active Ralph Loop sessions."""
        data = self._get("/api/ralph-loop/sessions")
        if not data:
            return []
        return data if isinstance(data, list) else data.get("sessions", [])
