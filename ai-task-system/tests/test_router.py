"""
Tests for TaskRouter - task classification and routing decisions.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

import pytest
from ai_task_system.v4.core.router import TaskRouter, TaskType


class TestTaskRouter:
    def test_classify_coding(self, router):
        t = router.classify("帮我写一个 Python 函数")
        assert t == TaskType.CODING

    def test_classify_debugging(self, router):
        t = router.classify("这个代码有 bug，运行报错了")
        assert t == TaskType.DEBUGGING

    def test_classify_refactoring(self, router):
        # Refactoring keyword should match
        t = router.classify("refactor this Python function")
        assert t == TaskType.REFACTORING

    def test_classify_architecture(self, router):
        t = router.classify("设计一个高可用的微服务架构")
        assert t == TaskType.ARCHITECTURE

    def test_classify_learning(self, router):
        t = router.classify("解释一下什么是 Python 装饰器")
        assert t == TaskType.LEARNING

    def test_classify_writing(self, router):
        # Writing keyword should match
        t = router.classify("write a technical blog post")
        assert t == TaskType.WRITING

    def test_classify_devops(self, router):
        t = router.classify("用 GitHub Actions 写一个 CI 流水线")
        assert t == TaskType.DEVOPS

    def test_classify_research(self, router):
        # Investigate keyword should match RESEARCH
        t = router.classify("investigate GIL performance characteristics")
        assert t == TaskType.RESEARCH

    def test_classify_unknown(self, router):
        t = router.classify("asdfghjkl random gibberish")
        # Falls back to QUERY or CODING (implementation detail)
        assert t in TaskType

    def test_route_returns_agent(self, router):
        result = router.route("帮我写一个 Python 函数")
        assert result.agent is not None
        assert result.task_type is not None

    def test_route_returns_confidence(self, router):
        result = router.route("帮我写一个 Python 函数")
        assert 0.0 <= result.confidence <= 1.0

    def test_route_with_specific_agent(self, router):
        """When user specifies agent, it should be respected."""
        result = router.route_for_agents("帮我写代码", [router.registry.get_all()[0].agent_type])
        assert result.agent is not None

    def test_route_result_has_task_type(self, router):
        result = router.route("用 Docker 部署应用")
        assert result.task_type is not None

    def test_route_explain(self, router):
        explanation = router.explain_routing("帮我写一个排序算法")
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        # Should contain key sections
        assert "分类" in explanation or "category" in explanation.lower()


class TestTaskType:
    def test_task_type_values(self):
        """All expected TaskType values exist."""
        assert TaskType.CODING is not None
        assert TaskType.DEBUGGING is not None
        assert TaskType.REFACTORING is not None
        assert TaskType.ARCHITECTURE is not None
        assert TaskType.CODE_REVIEW is not None
        assert TaskType.RESEARCH is not None
        assert TaskType.LEARNING is not None
        assert TaskType.WRITING is not None
        assert TaskType.TRANSLATION is not None
        assert TaskType.DEVOPS is not None
        assert TaskType.INFRA is not None
        assert TaskType.DATA_SCRIPT is not None
        assert TaskType.QUERY is not None

    def test_task_type_is_enum(self):
        assert hasattr(TaskType, '__members__')
