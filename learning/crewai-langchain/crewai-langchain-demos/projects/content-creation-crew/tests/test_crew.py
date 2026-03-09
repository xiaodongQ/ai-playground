"""
测试模块

测试内容创作 Crew 的基本功能
"""

import unittest
from pathlib import Path
import sys

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents import create_researcher, create_writer
from tasks import create_research_task

class TestAgents(unittest.TestCase):
    """测试 Agent 创建"""
    
    def test_researcher_creation(self):
        """测试研究员 Agent 创建"""
        agent = create_researcher()
        self.assertIsNotNone(agent)
        self.assertEqual(agent.role, "高级技术研究员")
        self.assertTrue(agent.verbose)
    
    def test_writer_creation(self):
        """测试作家 Agent 创建"""
        agent = create_writer()
        self.assertIsNotNone(agent)
        self.assertEqual(agent.role, "资深技术作家")

class TestTasks(unittest.TestCase):
    """测试 Task 创建"""
    
    def test_research_task_creation(self):
        """测试调研任务创建"""
        agent = create_researcher()
        task = create_research_task(agent)
        self.assertIsNotNone(task)
        self.assertEqual(task.agent, agent)
        self.assertTrue("调研" in task.description)

if __name__ == "__main__":
    unittest.main()
