from abc import ABC, abstractmethod
from typing import Tuple, Optional


class BaseExecutor(ABC):
    """所有执行器的抽象基类"""

    @abstractmethod
    async def execute(
        self,
        task_id: str,
        model: str,
        description: str,
        feedback_md: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        执行任务，返回 (stdout, error)
        """
        pass

    @abstractmethod
    async def cancel(self, task_id: str) -> bool:
        """取消正在执行的任务，返回是否成功"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """执行器名称：cli / sdk"""
        pass
