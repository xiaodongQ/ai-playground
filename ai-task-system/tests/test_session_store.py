"""
Tests for SessionStore - session persistence management.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

import pytest
from ai_task_system.v4.core.session_store import SessionStore


class TestSessionStore:
    def test_create_session(self, temp_session_store):
        info = temp_session_store.create(
            agent="claude",
            session_id="sess_test_001",
            note="Test session",
        )
        assert info.session_id == "sess_test_001"
        assert info.agent == "claude"
        assert info.note == "Test session"
        assert info.status == "active"

    def test_get_session(self, temp_session_store):
        temp_session_store.create(
            agent="claude",
            session_id="sess_test_001",
        )
        info = temp_session_store.get("sess_test_001")
        assert info is not None
        assert info.session_id == "sess_test_001"

    def test_get_nonexistent(self, temp_session_store):
        info = temp_session_store.get("nonexistent")
        assert info is None

    def test_list_sessions(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        temp_session_store.create(agent="claude", session_id="s2")
        sessions = temp_session_store.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_by_agent(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        temp_session_store.create(agent="codex", session_id="s2")
        sessions = temp_session_store.list_sessions(agent="claude")
        assert len(sessions) == 1
        assert sessions[0].agent == "claude"

    def test_archive_session(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        temp_session_store.archive("s1")
        sessions = temp_session_store.list_sessions(status="archived")
        assert len(sessions) == 1
        assert sessions[0].session_id == "s1"

    def test_delete_session(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        temp_session_store.delete("s1")
        assert temp_session_store.get("s1") is None

    def test_record_task(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        temp_session_store.record_task("s1", "task-001")
        info = temp_session_store.get("s1")
        assert "task-001" in info.task_ids

    def test_find_by_agent(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        time.sleep(0.01)
        temp_session_store.create(agent="claude", session_id="s2")
        # s2 should be found (most recent)
        info = temp_session_store.find_by_agent("claude")
        assert info.session_id == "s2"

    def test_stats(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        temp_session_store.create(agent="claude", session_id="s2")
        temp_session_store.create(agent="codex", session_id="s3")
        stats = temp_session_store.stats()
        assert stats["total"] == 3
        assert stats["by_agent"]["claude"] == 2
        assert stats["by_agent"]["codex"] == 1

    def test_export_session(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1", note="test")
        exported = temp_session_store.export_session("s1")
        assert exported is not None
        assert exported["session_id"] == "s1"
        assert "created_at" in exported

    def test_import_session_new(self, temp_session_store):
        session_data = {
            "agent": "claude",
            "session_id": "s_new",
            "created_at": time.time(),
            "last_used_at": time.time(),
            "task_ids": [],
            "note": "imported",
            "status": "active",
        }
        ok = temp_session_store.import_session(session_data)
        assert ok is True
        assert temp_session_store.get("s_new") is not None

    def test_clear_archived(self, temp_session_store):
        temp_session_store.create(agent="claude", session_id="s1")
        temp_session_store.archive("s1")
        temp_session_store.clear_archived()
        sessions = temp_session_store.list_sessions(status="archived")
        assert len(sessions) == 0
