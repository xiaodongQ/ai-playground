"""V4 Agent 能力评估基准：分数数据库（SQLite）"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from ..base import AgentType
from .result import BenchmarkResult, ResultStatus, TaskResult


class BenchmarkDB:
    """Benchmark 分数持久化数据库"""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS benchmark_runs (
        run_id         TEXT PRIMARY KEY,
        agent_types    TEXT NOT NULL,    -- JSON array of agent names
        task_ids       TEXT NOT NULL,    -- JSON array of task ids
        started_at     REAL NOT NULL,
        completed_at   REAL NOT NULL,
        duration_secs  REAL NOT NULL,
        config         TEXT NOT NULL,    -- JSON config
        created_at     REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS task_results (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id         TEXT NOT NULL,
        task_id        TEXT NOT NULL,
        agent_type     TEXT NOT NULL,
        status         TEXT NOT NULL,
        duration_secs  REAL NOT NULL,
        quality_score  REAL NOT NULL,
        correctness    REAL NOT NULL,
        completeness   REAL NOT NULL,
        code_quality   REAL NOT NULL,
        clarity        REAL NOT NULL,
        output_tokens  INTEGER NOT NULL DEFAULT 0,
        prompt_tokens  INTEGER NOT NULL DEFAULT 0,
        raw_output     TEXT,
        error_message  TEXT,
        metadata       TEXT,    -- JSON
        created_at     REAL NOT NULL,
        FOREIGN KEY (run_id) REFERENCES benchmark_runs(run_id)
    );

    CREATE INDEX IF NOT EXISTS idx_results_agent ON task_results(agent_type);
    CREATE INDEX IF NOT EXISTS idx_results_task  ON task_results(task_id);
    CREATE INDEX IF NOT EXISTS idx_results_run    ON task_results(run_id);

    -- Agent 历史平均分（用于路由参考）
    CREATE TABLE IF NOT EXISTS agent_scores (
        agent_type     TEXT NOT NULL,
        task_id        TEXT NOT NULL,
        run_id         TEXT NOT NULL,
        quality_score  REAL NOT NULL,
        pass           INTEGER NOT NULL,
        duration_secs  REAL NOT NULL,
        created_at     REAL NOT NULL,
        PRIMARY KEY (agent_type, task_id)
    );
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            base = Path.home() / ".openclaw" / "workspace" / "ai-task-system"
            base.mkdir(parents=True, exist_ok=True)
            db_path = str(base / "benchmark_scores.db")
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    def save_result(self, result: BenchmarkResult) -> None:
        """保存完整的 benchmark 运行结果"""
        with sqlite3.connect(self.db_path) as conn:
            # 保存 run
            conn.execute(
                """INSERT INTO benchmark_runs
                   (run_id, agent_types, task_ids, started_at, completed_at,
                    duration_secs, config, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.run_id,
                    json.dumps([a.name for a in result.agent_types]),
                    json.dumps(result.task_ids),
                    result.started_at,
                    result.completed_at,
                    result.duration_seconds,
                    json.dumps({
                        "timeout_per_task": result.timeout_per_task,
                        "parallel": result.parallel,
                    }),
                    time.time(),
                ),
            )

            # 保存每个 task result
            for tr in result.task_results:
                conn.execute(
                    """INSERT INTO task_results
                       (run_id, task_id, agent_type, status, duration_secs,
                        quality_score, correctness, completeness, code_quality, clarity,
                        output_tokens, prompt_tokens, raw_output, error_message, metadata, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.run_id,
                        tr.task_id,
                        tr.agent_type.name,
                        tr.status.name,
                        tr.duration_seconds,
                        tr.quality_score,
                        tr.correctness,
                        tr.completeness,
                        tr.code_quality,
                        tr.clarity,
                        tr.output_tokens,
                        tr.prompt_tokens,
                        tr.raw_output[:10000],  # 截断
                        tr.error_message,
                        json.dumps(tr.metadata),
                        time.time(),
                    ),
                )

                # 更新 agent_scores（最新分数）
                conn.execute(
                    """INSERT OR REPLACE INTO agent_scores
                       (agent_type, task_id, run_id, quality_score, pass, duration_secs, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tr.agent_type.name,
                        tr.task_id,
                        result.run_id,
                        tr.quality_score,
                        1 if tr.passed else 0,
                        tr.duration_seconds,
                        time.time(),
                    ),
                )

            conn.commit()

    def load_recent_runs(self, limit: int = 10) -> list[BenchmarkResult]:
        """加载最近 N 次 benchmark 运行"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM benchmark_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        results = []
        for row in rows:
            run_id = dict(row)["run_id"]
            task_results = self._load_task_results(run_id)
            br = BenchmarkResult(
                run_id=run_id,
                agent_types=[AgentType[a] for a in json.loads(dict(row)["agent_types"])],
                task_ids=json.loads(dict(row)["task_ids"]),
                started_at=dict(row)["started_at"],
                completed_at=dict(row)["completed_at"],
            )
            br.task_results = task_results
            results.append(br)
        return results

    def _load_task_results(self, run_id: str) -> list[TaskResult]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM task_results WHERE run_id = ?", (run_id,)
            ).fetchall()
        return [self._row_to_task_result(dict(r)) for r in rows]

    def _row_to_task_result(self, row: dict) -> TaskResult:
        return TaskResult(
            task_id=row["task_id"],
            agent_type=AgentType[row["agent_type"]],
            status=ResultStatus[row["status"]],
            duration_seconds=row["duration_secs"],
            quality_score=row["quality_score"],
            correctness=row["correctness"],
            completeness=row["completeness"],
            code_quality=row["code_quality"],
            clarity=row["clarity"],
            output_tokens=row["output_tokens"],
            prompt_tokens=row["prompt_tokens"],
            raw_output=row["raw_output"] or "",
            error_message=row["error_message"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def get_agent_task_scores(self, agent_type: AgentType) -> dict[str, float]:
        """获取某 Agent 对所有任务的最新质量分"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT task_id, quality_score, pass, duration_secs
                   FROM agent_scores
                   WHERE agent_type = ?
                   ORDER BY created_at DESC""",
                (agent_type.name,),
            ).fetchall()

        scores = {}
        seen = set()
        for row in rows:
            tid = dict(row)["task_id"]
            if tid not in seen:
                scores[tid] = dict(row)["quality_score"]
                seen.add(tid)
        return scores

    def get_comparison(self, task_ids: list[str], agent_types: list[AgentType]) -> dict:
        """获取多个 Agent 在指定任务上的对比数据"""
        result = {}
        for agent in agent_types:
            scores = self.get_agent_task_scores(agent)
            agent_data = {"scores": {}, "avg_quality": 0}
            task_scores = []
            for tid in task_ids:
                s = scores.get(tid, None)
                agent_data["scores"][tid] = s
                if s is not None:
                    task_scores.append(s)
            if task_scores:
                agent_data["avg_quality"] = round(sum(task_scores) / len(task_scores), 3)
            result[agent.name] = agent_data
        return result

    def list_runs(self, limit: int = 20) -> list[dict]:
        """列出 benchmark runs 摘要"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT run_id, agent_types, task_ids, duration_secs, created_at
                   FROM benchmark_runs
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "run_id": r["run_id"],
                "agents": json.loads(r["agent_types"]),
                "task_count": len(json.loads(r["task_ids"])),
                "duration_secs": round(r["duration_secs"], 1),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def delete_run(self, run_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM task_results WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM benchmark_runs WHERE run_id = ?", (run_id,))
            conn.commit()
