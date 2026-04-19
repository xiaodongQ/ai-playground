"""
Tests for BenchmarkScoreDB - persistent benchmark score database.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

import pytest
from ai_task_system.v4.core.benchmark_scores import BenchmarkScoreDB, AgentScores


class TestBenchmarkScoreDB:
    def test_load_empty(self, tmp_path):
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB.load(path=db_path)
        assert db.agents == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB()
        db.agents = {
            "claude": AgentScores(
                overall=0.67,
                categories={"CODING": 0.67, "DEBUGGING": 0.50},
                last_updated=time.time(),
            ),
            "codex": AgentScores(
                overall=0.67,
                categories={"CODING": 0.67, "DEBUGGING": 1.00},
                last_updated=time.time(),
            ),
        }
        db.save(path=db_path)
        # Reload and verify
        db2 = BenchmarkScoreDB.load(path=db_path)
        assert db2.get_score("claude", "CODING") == 0.67
        assert db2.get_score("codex", "DEBUGGING") == 1.00

    def test_get_score(self, tmp_path):
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB()
        db.agents = {
            "claude": AgentScores(
                overall=0.67,
                categories={"CODING": 0.67},
                last_updated=time.time(),
            ),
        }
        db.save(path=db_path)
        db2 = BenchmarkScoreDB.load(path=db_path)
        score = db2.get_score("claude", "CODING")
        assert score == 0.67

    def test_get_score_missing(self, tmp_path):
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB.load(path=db_path)
        score = db.get_score("claude", "CODING")
        assert score is None

    def test_get_best_agent(self, tmp_path):
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB()
        db.agents = {
            "claude": AgentScores(overall=0.67, categories={"CODING": 0.67}, last_updated=time.time()),
            "codex": AgentScores(overall=0.80, categories={"CODING": 0.80}, last_updated=time.time()),
        }
        db.save(path=db_path)
        db2 = BenchmarkScoreDB.load(path=db_path)
        best = db2.get_best_agent("CODING")
        assert best == "codex"

    def test_get_best_agent_missing_category(self, tmp_path):
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB.load(path=db_path)
        best = db.get_best_agent("NONEXISTENT_CATEGORY")
        assert best is None

    def test_get_ranking(self, tmp_path):
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB()
        db.agents = {
            "claude": AgentScores(overall=0.67, categories={"CODING": 0.67}, last_updated=time.time()),
            "codex": AgentScores(overall=0.80, categories={"CODING": 0.80}, last_updated=time.time()),
        }
        db.save(path=db_path)
        db2 = BenchmarkScoreDB.load(path=db_path)
        ranking = db2.get_ranking("CODING")
        assert ranking[0] == ("codex", 0.80)
        assert ranking[1] == ("claude", 0.67)

    def test_atomic_save(self, tmp_path):
        """Verify that save creates valid JSON file."""
        db_path = str(tmp_path / "scores.json")
        db = BenchmarkScoreDB()
        db.agents = {
            "claude": AgentScores(overall=0.5, categories={}, last_updated=time.time()),
        }
        db.save(path=db_path)
        # File should be valid JSON
        with open(db_path) as f:
            data = json.load(f)
        assert "claude" in data["agents"]
