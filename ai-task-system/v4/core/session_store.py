"""V4 会话持久化管理器

存储和管理 AI Agent 会话 ID，支持跨任务、跨进程、跨重启的会话恢复。

会话存储路径：~/.ai_task_system/sessions.json

会话数据结构：
{
  "sessions": {
    "<session_id>": {
      "agent": "claude",
      "session_id": "sess_xxx",
      "created_at": 1713400000.0,
      "last_used_at": 1713400100.0,
      "task_ids": ["task-001", "task-002"],
      "note": "我的量化策略开发",
      "status": "active"  # active | archived
    }
  }
}
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ─── 数据模型 ────────────────────────────────────────────────────────────────


@dataclass
class SessionInfo:
    """单个会话的元信息"""
    agent: str
    session_id: str
    created_at: float
    last_used_at: float
    task_ids: list[str] = field(default_factory=list)
    note: str = ""
    status: str = "active"  # active | archived

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "task_ids": self.task_ids,
            "note": self.note,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionInfo":
        return cls(
            agent=data["agent"],
            session_id=data["session_id"],
            created_at=data["created_at"],
            last_used_at=data["last_used_at"],
            task_ids=data.get("task_ids", []),
            note=data.get("note", ""),
            status=data.get("status", "active"),
        )


# ─── 核心 Store ───────────────────────────────────────────────────────────────


class SessionStore:
    """
    会话持久化管理器。

    管理 AI Agent 会话 ID 的创建、查询、更新和删除。
    支持跨进程持久化（JSON 文件），所有操作原子化。

    使用方式：
        store = SessionStore()

        # 创建一个新会话
        info = store.create(agent="claude", note="我的项目")

        # 记录某次使用（task 执行后调用）
        store.record_task(info.session_id, "task-001")

        # 列出所有会话
        for info in store.list_sessions():
            print(info.session_id, info.agent)

        # 标记归档
        store.archive("sess_xxx")

        # 删除会话
        store.delete("sess_xxx")
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self._path = Path(db_path).expanduser()
        else:
            self._path = Path.home() / ".ai_task_system" / "sessions.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = str(self._path) + ".lock"

    # ── 内部工具 ──────────────────────────────────────────────────────────────

    def _load(self) -> dict:
        """加载 JSON 文件，返回原始字典（不含 sessions 键则为 {}）。"""
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self, data: dict) -> None:
        """原子化保存：先写 .tmp，再 rename。"""
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.rename(self._path)

    # ── CRUD 操作 ─────────────────────────────────────────────────────────────

    def create(
        self,
        agent: str,
        session_id: str,
        note: str = "",
    ) -> SessionInfo:
        """
        注册一个新会话。

        Args:
            agent: Agent 类型（claude | codex | codebuddy）
            session_id: Agent 返回的原始 session ID
            note: 用户备注

        Returns:
            SessionInfo 对象
        """
        now = time.time()
        info = SessionInfo(
            agent=agent,
            session_id=session_id,
            created_at=now,
            last_used_at=now,
            note=note,
            status="active",
        )
        data = self._load()
        data[session_id] = info.to_dict()
        self._save(data)
        return info

    def get(self, session_id: str) -> Optional[SessionInfo]:
        """
        根据 session_id 查找会话。

        Returns:
            SessionInfo 或 None（不存在）
        """
        data = self._load()
        raw = data.get(session_id)
        if raw is None:
            return None
        return SessionInfo.from_dict(raw)

    def record_task(self, session_id: str, task_id: str) -> bool:
        """
        记录一个任务使用了此会话（追加到 task_ids）。

        Returns:
            True 成功，False 会话不存在
        """
        data = self._load()
        if session_id not in data:
            return False
        info = SessionInfo.from_dict(data[session_id])
        if task_id not in info.task_ids:
            info.task_ids.append(task_id)
        info.last_used_at = time.time()
        data[session_id] = info.to_dict()
        self._save(data)
        return True

    def update_note(self, session_id: str, note: str) -> bool:
        """更新会话备注。"""
        data = self._load()
        if session_id not in data:
            return False
        info = SessionInfo.from_dict(data[session_id])
        info.note = note
        info.last_used_at = time.time()
        data[session_id] = info.to_dict()
        self._save(data)
        return True

    def touch(self, session_id: str) -> bool:
        """刷新 last_used_at 时间戳（表示会话被使用过）。"""
        data = self._load()
        if session_id not in data:
            return False
        info = SessionInfo.from_dict(data[session_id])
        info.last_used_at = time.time()
        data[session_id] = info.to_dict()
        self._save(data)
        return True

    def archive(self, session_id: str) -> bool:
        """将会话标记为归档（不再推荐使用但保留历史）。"""
        data = self._load()
        if session_id not in data:
            return False
        info = SessionInfo.from_dict(data[session_id])
        info.status = "archived"
        info.last_used_at = time.time()
        data[session_id] = info.to_dict()
        self._save(data)
        return True

    def delete(self, session_id: str) -> bool:
        """删除会话。"""
        data = self._load()
        if session_id not in data:
            return False
        del data[session_id]
        self._save(data)
        return True

    def list_sessions(
        self,
        agent: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[SessionInfo]:
        """
        列出所有会话。

        Args:
            agent: 按 Agent 类型过滤（None 不过滤）
            status: 按状态过滤（active | archived，None 不过滤）
            limit: 返回数量上限（按 last_used_at 倒序）
        """
        data = self._load()
        infos = []
        for raw in data.values():
            info = SessionInfo.from_dict(raw)
            if agent and info.agent != agent:
                continue
            if status and info.status != status:
                continue
            infos.append(info)
        infos.sort(key=lambda x: x.last_used_at, reverse=True)
        return infos[:limit]

    def count(self, agent: Optional[str] = None, status: str = "active") -> int:
        """统计会话数量。"""
        return len(self.list_sessions(agent=agent, status=status, limit=999999))

    # ── 便捷工具 ─────────────────────────────────────────────────────────────

    def find_by_agent(self, agent: str, status: str = "active") -> Optional[SessionInfo]:
        """
        查找某 Agent 最新可用的会话。

        Returns:
            最新的 active 会话，或 None
        """
        sessions = self.list_sessions(agent=agent, status=status, limit=1)
        return sessions[0] if sessions else None

    def export_session(self, session_id: str) -> Optional[dict]:
        """
        导出会话完整数据（用于迁移或备份）。
        """
        info = self.get(session_id)
        if info is None:
            return None
        return info.to_dict()

    def import_session(self, data: dict) -> bool:
        """
        从导出的数据恢复会话。

        Args:
            data: export_session() 导出的字典

        Returns:
            True 成功，False session_id 已存在
        """
        session_id = data.get("session_id")
        if not session_id:
            return False
        existing = self._load()
        if session_id in existing:
            return False
        existing[session_id] = data
        self._save(existing)
        return True

    def clear_archived(self) -> int:
        """
        清理所有已归档会话。

        Returns:
            清理数量
        """
        data = self._load()
        to_delete = [sid for sid, raw in data.items() if raw.get("status") == "archived"]
        for sid in to_delete:
            del data[sid]
        self._save(data)
        return len(to_delete)

    # ── 统计信息 ─────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """返回聚合统计信息。"""
        data = self._load()
        total = len(data)
        by_agent: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for raw in data.values():
            a = raw.get("agent", "unknown")
            s = raw.get("status", "unknown")
            by_agent[a] = by_agent.get(a, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total": total,
            "by_agent": by_agent,
            "by_status": by_status,
        }


# ─── 全局单例（懒初始化）──────────────────────────────────────────────────────

_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """获取全局 SessionStore 单例。"""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store


# ─── CLI 入口 ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    store = SessionStore()

    parser = argparse.ArgumentParser(description="AI Task System 会话管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list
    p_list = sub.add_parser("list", help="列出所有会话")
    p_list.add_argument("--agent", help="按 Agent 过滤")
    p_list.add_argument("--status", default="active", help="按状态过滤")
    p_list.add_argument("--limit", type=int, default=50)

    # create
    p_create = sub.add_parser("create", help="创建会话记录")
    p_create.add_argument("--agent", required=True, help="Agent 类型")
    p_create.add_argument("--session-id", required=True, help="会话 ID")
    p_create.add_argument("--note", default="", help="备注")

    # get
    p_get = sub.add_parser("get", help="查看会话详情")
    p_get.add_argument("session_id", help="会话 ID")

    # archive
    p_arch = sub.add_parser("archive", help="归档会话")
    p_arch.add_argument("session_id", help="会话 ID")

    # delete
    p_del = sub.add_parser("delete", help="删除会话")
    p_del.add_argument("session_id", help="会话 ID")

    # stats
    sub.add_parser("stats", help="统计信息")

    # clear-archived
    p_clear = sub.add_parser("clear-archived", help="清理已归档会话")

    args = parser.parse_args()

    if args.cmd == "list":
        for s in store.list_sessions(agent=args.agent, status=args.status, limit=args.limit):
            print(
                f"[{s.status}] {s.agent}  {s.session_id}  "
                f"tasks={len(s.task_ids)}  last_used={_fmt_time(s.last_used_at)}"
            )
            if s.note:
                print(f"         note: {s.note}")

    elif args.cmd == "create":
        info = store.create(agent=args.agent, session_id=args.session_id, note=args.note)
        print(f"Created: {info.session_id}")

    elif args.cmd == "get":
        info = store.get(args.session_id)
        if info is None:
            print(f"Not found: {args.session_id}")
        else:
            print(f"agent:     {info.agent}")
            print(f"session:   {info.session_id}")
            print(f"status:    {info.status}")
            print(f"created:   {_fmt_time(info.created_at)}")
            print(f"last_used: {_fmt_time(info.last_used_at)}")
            print(f"tasks:     {info.task_ids}")
            print(f"note:      {info.note}")

    elif args.cmd == "archive":
        ok = store.archive(args.session_id)
        print(f"{'Archived' if ok else 'Not found'}: {args.session_id}")

    elif args.cmd == "delete":
        ok = store.delete(args.session_id)
        print(f"{'Deleted' if ok else 'Not found'}: {args.session_id}")

    elif args.cmd == "stats":
        import json as _json
        print(_json.dumps(store.stats(), indent=2, ensure_ascii=False))

    elif args.cmd == "clear-archived":
        n = store.clear_archived()
        print(f"Cleared {n} archived sessions.")


def _fmt_time(ts: float) -> str:
    """格式化为可读时间字符串。"""
    import datetime
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")
