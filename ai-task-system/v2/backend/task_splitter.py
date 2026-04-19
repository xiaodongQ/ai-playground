"""
任务拆分器 - 根据用户描述或分析，将复杂任务拆分为子任务树
支持线性串行和树状并行两种拆分模式
"""
import uuid
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class SplitMode(Enum):
    LINEAR = "linear"    # A→B→C, 前序产出作为下游输入
    PARALLEL = "parallel"  # 根任务拆多个独立子任务，最终合并验收
    TREE = "tree"       # 混合模式

@dataclass
class SubTask:
    id: str
    parent_id: Optional[str]
    title: str
    description: str
    mode: SplitMode = SplitMode.LINEAR
    dependencies: List[str] = field(default_factory=list)  # artifact_ids this task depends on
    input_artifacts: List[str] = field(default_factory=list)  # artifact_ids to use as input
    output_artifacts: List[str] = field(default_factory=list)  # artifact_ids this task produces
    status: str = "pending"
    assigned_agent: Optional[str] = None
    is_root: bool = False
    is_merge: bool = False  # 最终合并验收任务

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "title": self.title,
            "description": self.description,
            "mode": self.mode.value,
            "dependencies": self.dependencies,
            "input_artifacts": self.input_artifacts,
            "output_artifacts": self.output_artifacts,
            "status": self.status,
            "assigned_agent": self.assigned_agent,
            "is_root": self.is_root,
            "is_merge": self.is_merge,
        }


class TaskSplitter:
    """
    任务拆分器 - 将复杂任务拆分为可调度的子任务树
    """

    # LLM prompt for analyzing how to split a task
    SPLIT_ANALYSIS_PROMPT = """你是一个任务规划专家。请分析以下复杂任务，决定如何拆分。

任务：{task_description}

请决定拆分策略（linear | parallel | tree），然后输出子任务列表。

拆分策略说明：
- linear（线性串行）：任务可以分解为严格按顺序执行的步骤 A→B→C，每步产出作为下一步输入
- parallel（树状并行）：任务可以分解为多个独立子任务，同时执行，最后合并结果
- tree（混合）：部分串行部分并行

请以以下JSON格式输出（只需输出JSON，不要其他内容）：
{{
  "strategy": "linear|parallel|tree",
  "sub_tasks": [
    {{
      "title": "子任务标题",
      "description": "具体描述",
      "mode": "linear|parallel",
      "depends_on": ["前置子任务编号，如1"]  // 可选
    }}
  ]
}}
"""

    def __init__(self):
        self._tasks: Dict[str, SubTask] = {}

    def split_task(
        self,
        task_description: str,
        root_task_id: str,
        strategy: str = None,
        sub_tasks_def: List[Dict] = None,
    ) -> List[SubTask]:
        """
        Split a task into sub-tasks.
        
        If strategy and sub_tasks_def are provided, use them directly.
        Otherwise use LLM to analyze and determine split (placeholder for future LLM integration).
        
        Returns list of SubTask objects including the root task.
        """
        self._tasks.clear()
        
        # Create root task
        root = SubTask(
            id=root_task_id,
            parent_id=None,
            title="Root Task",
            description=task_description,
            is_root=True,
        )
        self._tasks[root_task_id] = root

        if sub_tasks_def:
            for i, st_def in enumerate(sub_tasks_def):
                st_id = f"{root_task_id}-sub-{i+1}"
                parent_id = root_task_id
                
                # Find parent based on depends_on
                if st_def.get("depends_on"):
                    dep_idx = st_def["depends_on"][0] - 1  # 1-based to 0-based
                    if 0 <= dep_idx < len(sub_tasks_def):
                        # This subtask depends on another subtask
                        parent_id = f"{root_task_id}-sub-{st_def['depends_on'][0]}"
                
                mode = SplitMode(st_def.get("mode", "linear"))
                subtask = SubTask(
                    id=st_id,
                    parent_id=parent_id,
                    title=st_def.get("title", f"Sub-task {i+1}"),
                    description=st_def.get("description", ""),
                    mode=mode,
                    is_merge=st_def.get("is_merge", False),
                )
                self._tasks[st_id] = subtask
        else:
            # Default: treat as single linear task
            pass

        return list(self._tasks.values())

    def get_ready_tasks(self) -> List[SubTask]:
        """Get tasks whose dependencies are all satisfied (for waiting state)"""
        ready = []
        for task in self._tasks.values():
            if task.status != "pending":
                continue
            if not task.dependencies:
                ready.append(task)
            # TODO: integrate with ArtifactsManager to check dependency validity
        return ready

    def mark_running(self, task_id: str, agent_id: str):
        if task_id in self._tasks:
            self._tasks[task_id].status = "running"
            self._tasks[task_id].assigned_agent = agent_id

    def mark_completed(self, task_id: str):
        if task_id in self._tasks:
            self._tasks[task_id].status = "completed"

    def to_json(self) -> str:
        return json.dumps([t.to_dict() for t in self._tasks.values()], indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "TaskSplitter":
        splitter = cls()
        splitter._tasks = {}
        for d in json.loads(data):
            splitter._tasks[d["id"]] = SubTask(
                id=d["id"],
                parent_id=d["parent_id"],
                title=d["title"],
                description=d["description"],
                mode=SplitMode(d.get("mode", "linear")),
                dependencies=d.get("dependencies", []),
                input_artifacts=d.get("input_artifacts", []),
                output_artifacts=d.get("output_artifacts", []),
                status=d.get("status", "pending"),
                assigned_agent=d.get("assigned_agent"),
                is_root=d.get("is_root", False),
                is_merge=d.get("is_merge", False),
            )
        return splitter
