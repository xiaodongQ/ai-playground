import pytest
from backend.evaluator import Evaluator

def test_evaluator_initialization():
    evaluator = Evaluator()
    assert evaluator.default_model is not None

def test_build_evaluation_prompt():
    evaluator = Evaluator()
    prompt = evaluator.build_evaluation_prompt(
        task_description="实现登录功能",
        execution_output="已实现登录功能...",
        iteration_count=1
    )
    assert "实现登录功能" in prompt
    assert "已实现登录功能" in prompt
    assert "评分" in prompt
    assert "优点" in prompt
    assert "问题" in prompt
    assert "改进建议" in prompt

def test_build_feedback_md():
    evaluator = Evaluator()
    feedback = evaluator.build_feedback_md(
        task_description="实现登录功能",
        execution_output="已实现...",
        evaluation_result="评分: 6/10\n优点: ...\n问题: ...",
        iteration_count=1
    )
    assert "## 任务" in feedback
    assert "## 执行结果" in feedback
    assert "## 评估报告" in feedback
    assert "## 反馈给执行引擎" in feedback