"""
产物管理器 - 负责管理任务执行产生的 artifacts
存储路径: ~/.ai_task_system/artifacts/{root_task_id}/{sub_task_id}/{version}/
"""
import json
import os
import shutil
import hashlib
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

ARTIFACTS_DIR = Path.home() / ".ai_task_system" / "artifacts"

@dataclass
class Artifact:
    id: str
    root_task_id: str
    parent_task_id: Optional[str]
    artifact_name: str
    artifact_type: str  # file | directory | text
    file_path: str
    file_hash: str
    version: int
    dependency_declaration: str  # JSON string
    is_valid: bool
    is_final: bool
    created_by: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> 'Artifact':
        return cls(**d)


class ArtifactsManager:
    """管理所有 artifacts 的存储、查询和生命周期"""

    def __init__(self, artifacts_dir: Path = ARTIFACTS_DIR, db=None, ws_manager=None):
        self.artifacts_dir = artifacts_dir
        self.db = db
        self.ws_manager = ws_manager

    def _task_dir(self, root_task_id: str, sub_task_id: str) -> Path:
        d = self.artifacts_dir / root_task_id / sub_task_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _version_dir(self, root_task_id: str, sub_task_id: str, version: int) -> Path:
        vd = self._task_dir(root_task_id, sub_task_id) / str(version)
        vd.mkdir(parents=True, exist_ok=True)
        return vd

    def _meta_file(self, root_task_id: str, sub_task_id: str, version: int) -> Path:
        return self._version_dir(root_task_id, sub_task_id, version) / ".meta.json"

    def _compute_hash(self, file_path: Path) -> str:
        if not file_path.exists():
            return ""
        if file_path.is_dir():
            # Hash directory as a marker
            return hashlib.sha256(str(sorted(file_path.rglob("*"))).encode()).hexdigest()[:16]
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def save_artifact(
        self,
        root_task_id: str,
        parent_task_id: Optional[str],
        artifact_name: str,
        artifact_type: str,
        content: str | bytes,
        dependency_declaration: List[str] = None,
        created_by: str = "executor",
    ) -> Artifact:
        """保存 artifact，返回 Artifact 对象"""
        sub_task_id = parent_task_id or root_task_id
        
        # Find current latest version
        existing_versions = []
        task_dir = self._task_dir(root_task_id, sub_task_id)
        if task_dir.exists():
            for v in task_dir.iterdir():
                if v.is_dir() and v.name != ".meta":
                    try:
                        existing_versions.append(int(v.name))
                    except ValueError:
                        pass
        
        version = max(existing_versions, default=0) + 1
        vd = self._version_dir(root_task_id, sub_task_id, version)

        # Save content
        file_path = vd / artifact_name
        if artifact_type == "text":
            file_path.write_text(content if isinstance(content, str) else content.decode())
        else:
            if isinstance(content, str):
                file_path.write_text(content)
            else:
                file_path.write_bytes(content)

        # Create artifact record
        artifact = Artifact(
            id=str(uuid.uuid4()),
            root_task_id=root_task_id,
            parent_task_id=parent_task_id,
            artifact_name=artifact_name,
            artifact_type=artifact_type,
            file_path=str(file_path),
            file_hash=self._compute_hash(file_path),
            version=version,
            dependency_declaration=json.dumps(dependency_declaration or []),
            is_valid=True,
            is_final=False,
            created_by=created_by,
            created_at=datetime.now().isoformat(),
        )

        # Save metadata
        with open(self._meta_file(root_task_id, sub_task_id, version), "w") as f:
            json.dump(artifact.to_dict(), f, indent=2)

        return artifact

    def get_latest_version(self, root_task_id: str, sub_task_id: str) -> Optional[Artifact]:
        """获取最新版本的 artifact"""
        task_dir = self._task_dir(root_task_id, sub_task_id)
        if not task_dir.exists():
            return None
        versions = []
        for v in task_dir.iterdir():
            if v.is_dir() and v.name != ".meta":
                try:
                    versions.append(int(v.name))
                except ValueError:
                    pass
        if not versions:
            return None
        latest = max(versions)
        meta_path = self._meta_file(root_task_id, sub_task_id, latest)
        if meta_path.exists():
            with open(meta_path) as f:
                return Artifact.from_dict(json.load(f))
        return None

    def get_artifact(self, root_task_id: str, sub_task_id: str, version: int) -> Optional[Artifact]:
        """获取指定版本的 artifact"""
        meta_path = self._meta_file(root_task_id, sub_task_id, version)
        if meta_path.exists():
            with open(meta_path) as f:
                return Artifact.from_dict(json.load(f))
        return None

    def list_artifacts(self, root_task_id: str) -> List[Artifact]:
        """列出 root_task_id 下所有 artifacts"""
        results = []
        root_dir = self.artifacts_dir / root_task_id
        if not root_dir.exists():
            return results
        for sub_task_dir in root_dir.iterdir():
            if sub_task_dir.is_dir():
                for v_dir in sub_task_dir.iterdir():
                    if v_dir.is_dir() and v_dir.name != ".meta":
                        try:
                            meta_path = v_dir / ".meta.json"
                            if meta_path.exists():
                                with open(meta_path) as f:
                                    results.append(Artifact.from_dict(json.load(f)))
                        except (ValueError, json.JSONDecodeError):
                            pass
        return results

    def mark_invalid(self, artifact_id: str, root_task_id: str):
        """标记某个 artifact 为无效（上游依赖更新时）"""
        for artifact in self.list_artifacts(root_task_id):
            if artifact.id == artifact_id:
                artifact.is_valid = False
                meta_path = Path(artifact.file_path).parent / ".meta.json"
                if meta_path.exists():
                    with open(meta_path, "w") as f:
                        json.dump(artifact.to_dict(), f, indent=2)
        # Notify downstream tasks that this artifact is now invalid
        self.notify_downstream_invalidation(root_task_id, artifact_id)

    def notify_downstream_invalidation(self, root_task_id: str, artifact_id: str) -> List[str]:
        """
        When an artifact is marked invalid, find all downstream tasks that depend on it
        and notify them. Downgrades pending tasks back to waiting.
        Returns list of affected task IDs.
        """
        if not self.db:
            return []

        affected_task_ids = []

        async def _do_notify():
            nonlocal affected_task_ids
            import sqlite3
            # Query tasks where dependency_artifact_ids contains artifact_id
            async with self.db._conn_lock:
                conn = self.db._db_conn
                cursor = await conn.execute(
                    """SELECT id, dependency_artifact_ids FROM tasks
                       WHERE root_task_id = ? AND (status = 'waiting' OR status = 'pending')""",
                    (root_task_id,)
                )
                rows = await cursor.fetchall()

            for row in rows:
                task_id, dep_json = row[0], row[1]
                try:
                    deps = json.loads(dep_json or "[]")
                except json.JSONDecodeError:
                    deps = []
                if artifact_id in deps:
                    affected_task_ids.append(task_id)
                    # Downgrade pending -> waiting
                    await self.db.update_task_status(task_id, "waiting")

            # Broadcast to WebSocket clients
            if self.ws_manager and affected_task_ids:
                await self.ws_manager.broadcast({
                    "type": "artifact_invalidated",
                    "artifact_id": artifact_id,
                    "affected_task_ids": affected_task_ids,
                })

        # Run the async logic
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # Already in async context — create task
            import contextvars
            ctx = contextvars.copy_context()
            loop.create_task(_do_notify())
        except RuntimeError:
            # No running loop — run synchronously
            asyncio.run(_do_notify())

        return affected_task_ids

    def mark_final(self, artifact_id: str, root_task_id: str):
        """标记 artifact 为最终版本（合并验收后）"""
        for artifact in self.list_artifacts(root_task_id):
            if artifact.id == artifact_id:
                artifact.is_final = True
                meta_path = Path(artifact.file_path).parent / ".meta.json"
                if meta_path.exists():
                    with open(meta_path, "w") as f:
                        json.dump(artifact.to_dict(), f, indent=2)

    def get_dependencies_ready(self, root_task_id: str, dependency_ids: List[str]) -> bool:
        """检查所有依赖 artifact 是否 valid 且 final"""
        artifacts = {a.id: a for a in self.list_artifacts(root_task_id)}
        for dep_id in dependency_ids:
            if dep_id not in artifacts or not artifacts[dep_id].is_valid:
                return False
        return True
