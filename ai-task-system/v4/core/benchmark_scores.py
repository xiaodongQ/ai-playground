"""
V4 基准分数持久化与加载

将 AgentBenchmarker 的评估结果保存为 JSON，
供 TaskRouter 在路由决策时参考真实性能数据。

文件格式：~/.ai_task_system/benchmark_scores.json
{
  "version": 1,
  "updated_at": "2026-04-18T...",
  "agents": {
    "claude": {
      "overall": 0.72,
      "categories": {
        "CODING": 0.67,
        "DEBUGGING": 0.50,
        "REFACTORING": 0.33,
        ...
      }
    },
    ...
  }
}
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .benchmark import BenchmarkReport

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class AgentScores:
    """单个 Agent 的基准分数据"""
    overall: float       # 总体得分 0.0 ~ 1.0
    categories: dict[str, float]  # 各分类得分
    last_updated: float  # Unix timestamp


@dataclass
class BenchmarkScoreDB:
    """
    基准分数数据库（持久化到 JSON）

    用法：
        db = BenchmarkScoreDB.load()
        score = db.get_score("claude", "CODING")   # → 0.67 或 None
        score = db.get_best_agent("CODING")         # → "claude"
        db.save(report)   # 追加/更新报告
    """
    agents: dict[str, AgentScores] = field(default_factory=dict)
    version: int = 1
    updated_at: str | None = None
    _lock: threading.RLock = field(init=False, repr=False)

    # 类变量
    DEFAULT_PATH: str = "~/.ai_task_system/benchmark_scores.json"

    def __post_init__(self):
        self._lock = threading.RLock()

    @classmethod
    def load(cls, path: str | None = None) -> "BenchmarkScoreDB":
        """从 JSON 文件加载分数数据（文件不存在则返回空 DB）"""
        p = cls._resolve_path(path)
        if not p.exists():
            return cls(agents={})
        try:
            data = json.loads(p.read_text())
            agents = {}
            for agent_name, agent_data in data.get("agents", {}).items():
                agents[agent_name] = AgentScores(
                    overall=agent_data.get("overall", 0.0),
                    categories=agent_data.get("categories", {}),
                    last_updated=agent_data.get("last_updated", 0.0),
                )
            return cls(
                agents=agents,
                version=data.get("version", 1),
                updated_at=data.get("updated_at"),
            )
        except (json.JSONDecodeError, KeyError):
            return cls(agents={})

    def save(self, path: str | None = None) -> None:
        """持久化到 JSON 文件（线程安全）"""
        p = self._resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # 确保 updated_at 是 ISO 格式
        import time
        updated = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = {
            "version": self.version,
            "updated_at": updated,
            "agents": {},
        }
        for name, scores in self.agents.items():
            data["agents"][name] = {
                "overall": scores.overall,
                "categories": scores.categories,
                "last_updated": scores.last_updated,
            }

        with self._lock:
            # 原子写入：先写 .tmp，再 rename
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            tmp.rename(p)

    # ---------------------------------------------------------------------------
    # 写入
    # ---------------------------------------------------------------------------

    def upsert_report(self, report: "BenchmarkReport") -> None:
        """
        将 BenchmarkReport 追加/更新到数据库

        Args:
            report: AgentBenchmarker.run() 返回的报告
        """
        import time
        with self._lock:
            self.agents[report.agent] = AgentScores(
                overall=report.overall_score,
                categories=dict(report.category_scores),
                last_updated=time.time(),
            )
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---------------------------------------------------------------------------
    # 查询
    # ---------------------------------------------------------------------------

    def get_score(self, agent: str, category: str) -> float | None:
        """
        获取指定 Agent + 分类的得分

        Args:
            agent: Agent 名称（如 "claude", "codex"）
            category: 分类名称（如 "CODING", "REFACTORING"）

        Returns:
            得分（0.0 ~ 1.0），无数据时返回 None
        """
        agent_scores = self.agents.get(agent)
        if agent_scores is None:
            return None
        return agent_scores.categories.get(category)

    def get_overall(self, agent: str) -> float | None:
        """获取 Agent 的总体得分"""
        agent_scores = self.agents.get(agent)
        return agent_scores.overall if agent_scores else None

    def get_best_agent(self, category: str) -> str | None:
        """
        获取某分类下得分最高的 Agent

        Returns:
            Agent 名称，无数据时返回 None
        """
        best_agent = None
        best_score = -1.0
        for name, scores in self.agents.items():
            cat_score = scores.categories.get(category, 0.0)
            if cat_score > best_score:
                best_score = cat_score
                best_agent = name
        return best_agent

    def get_ranking(self, category: str) -> list[tuple[str, float]]:
        """获取某分类下所有 Agent 的排名（降序）"""
        ranking = []
        for name, scores in self.agents.items():
            ranking.append((name, scores.categories.get(category, 0.0)))
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking

    def has_data(self) -> bool:
        """是否已有基准数据"""
        return len(self.agents) > 0

    def agent_names(self) -> list[str]:
        """所有已记录 Agent 名称"""
        return list(self.agents.keys())

    def category_names(self) -> list[str]:
        """所有已记录分类名称"""
        cats = set()
        for scores in self.agents.values():
            cats.update(scores.categories.keys())
        return sorted(cats)

    # ---------------------------------------------------------------------------
    # 工具
    # ---------------------------------------------------------------------------

    @staticmethod
    def _resolve_path(path: str | None) -> Path:
        p = path or BenchmarkScoreDB.DEFAULT_PATH
        return Path(p).expanduser().resolve()

    def compare(self) -> str:
        """返回所有 Agent 的分类排名对比（含胜负记录）"""
        if not self.agents:
            return "No benchmark data available. Run `benchmark` command first."

        agents = sorted(self.agents.keys())
        categories = sorted(self.category_names())
        num_agents = len(agents)
        lines = []

        # Win/loss matrix
        lines.append("\n" + "=" * 60)
        lines.append("  Agent Comparison — Win/Loss Matrix")
        lines.append("=" * 60)

        if num_agents >= 2:
            # Matrix: rows=agents, cols=categories
            # Each cell: "W" if agent beats opponent, "L" if loses, "T" if tie
            try:
                from rich.console import Console
                from rich.table import Table
                from io import StringIO
                console = Console()

                # Per-category rankings table
                cat_table = Table(title="Category Rankings", show_footer=True)
                cat_table.add_column("Category", style="cyan", footer="Wins")
                for i, agent in enumerate(agents):
                    wins = sum(1 for cat in categories if self._wins(agent, cat, agents))
                    cat_table.add_column(agent, justify="center", footer=str(wins))

                medals = ["🥇", "🥈", "🥉"]

                # Per-category rows: show each agent's rank+score for each category
                for cat in categories:
                    ranking = self.get_ranking(cat)
                    # Compute rank map (handle ties: same score = same rank)
                    rank_map = {}
                    prev_score = None
                    prev_rank = -1
                    for name, score in ranking:
                        if score == prev_score:
                            rank_map[name] = prev_rank
                        else:
                            rank_map[name] = prev_rank + 1
                            prev_rank = rank_map[name]
                        prev_score = score

                    row = [cat]
                    for agent in agents:
                        agent_score = self.get_score(agent, cat) or 0.0
                        rank_pos = rank_map.get(agent, num_agents)
                        medal = medals[rank_pos] if rank_pos < len(medals) else "  "
                        row.append(f"{medal} {agent_score:.2f}")
                    cat_table.add_row(*row)

                buf = StringIO()
                tmp_console = Console(file=buf, force_terminal=True)
                tmp_console.print(cat_table)
                lines.append(buf.getvalue())

                # Win/loss summary
                if num_agents == 2:
                    a0, a1 = agents
                    wins = {a0: 0, a1: 0, "tie": 0}
                    for cat in categories:
                        r = self.get_ranking(cat)
                        top_score = r[0][1] if r else 0
                        cat_scores = {name: self.get_score(name, cat) or 0 for name in agents}
                        if cat_scores[a0] == cat_scores[a1] == top_score:
                            wins["tie"] += 1
                        elif a0 == r[0][0]:
                            wins[a0] += 1
                        else:
                            wins[a1] += 1
                    lines.append(f"\n  {a0} vs {a1}: {wins[a0]}W-{wins[a1]}L-{wins['tie']}T")

                # Overall ranking
                overall_ranking = sorted(
                    [(name, scores.overall) for name, scores in self.agents.items()],
                    key=lambda x: x[1], reverse=True
                )
                lines.append("\n  Overall Ranking:")
                medals = ["🥇", "🥈", "🥉"]
                for rank, (name, score) in enumerate(overall_ranking):
                    medal = medals[rank] if rank < len(medals) else f" #{rank+1}"
                    lines.append(f"    {medal}  {name:<12} {score:.2f}")

            except ImportError:
                # Plain text fallback
                lines.append("\n  Category Rankings:")
                for cat in categories:
                    ranking = self.get_ranking(cat)
                    lines.append(f"\n  {cat}:")
                    for rank, (name, score) in enumerate(ranking):
                        lines.append(f"    {rank+1}. {name:<12} {score:.2f}")
                lines.append("\n  Overall Ranking:")
                overall = sorted([(n, s.overall) for n, s in self.agents.items()],
                                 key=lambda x: x[1], reverse=True)
                for rank, (name, score) in enumerate(overall):
                    lines.append(f"    {rank+1}. {name:<12} {score:.2f}")
        else:
            lines.append("  (Need at least 2 agents for comparison)")

        return "\n".join(lines)

    def _wins(self, agent: str, category: str, all_agents: list[str]) -> bool:
        """Return True if agent uniquely wins the category (strictly top score, no tie)"""
        ranking = self.get_ranking(category)
        if not ranking:
            return False
        top_score = ranking[0][1]
        # Count how many agents share the top score
        tied_winners = [name for name, score in ranking if score == top_score]
        # Only a unique winner counts as a win
        return len(tied_winners) == 1 and tied_winners[0] == agent

    def summary(self) -> str:
        """返回人类可读的摘要"""
        if not self.agents:
            return "No benchmark data available. Run `benchmark` command first."

        lines = [
            f"Benchmark Score DB (updated: {self.updated_at or 'unknown'})",
            f"Agents: {', '.join(self.agent_names())}",
            f"Categories: {', '.join(self.category_names())}",
            "",
        ]

        try:
            from rich.console import Console
            from rich.table import Table
            console = Console()
        except ImportError:
            console = None

        if console:
            table = Table(title="Benchmark Scores")
            table.add_column("Category", style="cyan")
            for agent in sorted(self.agents.keys()):
                table.add_column(agent, justify="right")

            all_cats = sorted(self.category_names())
            for cat in all_cats:
                row = [cat]
                for agent in sorted(self.agents.keys()):
                    score = self.agents[agent].categories.get(cat, 0.0)
                    row.append(f"{score:.2f}" if score > 0 else "—")
                table.add_row(*row)

            # Overall row
            overall_row = ["OVERALL"]
            for agent in sorted(self.agents.keys()):
                overall_row.append(f"{self.agents[agent].overall:.2f}")
            table.add_row(*overall_row, style="bold")

            from io import StringIO
            buf = StringIO()
            tmp_console = Console(file=buf, force_terminal=True)
            tmp_console.print(table)
            lines.append(buf.getvalue())
        else:
            # Plain text fallback
            agents = sorted(self.agents.keys())
            cat_width = 20
            agent_width = 10
            header = f"{'Category':<{cat_width}}" + "".join(f"{a:<{agent_width}}" for a in agents)
            lines.append(header)
            lines.append("-" * len(header))
            for cat in sorted(self.category_names()):
                row = f"{cat:<{cat_width}}"
                for agent in agents:
                    score = self.agents[agent].categories.get(cat, 0.0)
                    row += f"{score:>{agent_width}.2f}" if score > 0 else f"{'—':>{agent_width}}"
                lines.append(row)
            lines.append("-" * len(header))
            overall = f"{'OVERALL':<{cat_width}}"
            for agent in agents:
                overall += f"{self.agents[agent].overall:>{agent_width}.2f}"
            lines.append(overall)

        return "\n".join(lines)
