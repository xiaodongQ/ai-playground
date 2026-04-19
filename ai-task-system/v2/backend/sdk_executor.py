import logging
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from .base_executor import BaseExecutor

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path.home() / ".ai_task_system" / "sessions"


class SDKExecutor(BaseExecutor):
    """CodeBuddy 官方 Python SDK 执行器"""

    name = "sdk"

    def __init__(self, cli_path: str = "claw"):
        self.cli_path = cli_path
        self._sessions: Dict[str, Any] = {}
        self._interrupt_flags: Dict[str, bool] = {}
        self._clients: Dict[str, CodeBuddySDKClient] = {}
        self._load_sessions_from_disk()

    def _load_sessions_from_disk(self):
        """Load existing sessions from disk on startup."""
        if not SESSIONS_DIR.exists():
            return
        for f in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                task_id = data.get("task_id")
                if task_id:
                    self._sessions[task_id] = data
            except Exception as e:
                logger.warning(f"Failed to load session file {f}: {e}")

    def _get_session_file(self, task_id: str) -> Path:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        return SESSIONS_DIR / f"{task_id}.json"

    def _load_session(self, task_id: str) -> Dict[str, Any]:
        """Load or create session file for a task."""
        fpath = self._get_session_file(task_id)
        if fpath.exists():
            try:
                return json.loads(fpath.read_text())
            except Exception:
                pass
        return {
            "task_id": task_id,
            "session_id": task_id,
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
        }

    def _save_session(self, task_id: str, session_data: Dict[str, Any]):
        """Persist session data to disk."""
        session_data["last_used"] = datetime.now().isoformat()
        fpath = self._get_session_file(task_id)
        try:
            fpath.write_text(json.dumps(session_data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save session file {fpath}: {e}")
        self._sessions[task_id] = session_data

    def _build_options(self, timeout: Optional[int], task_id: str) -> CodeBuddyAgentOptions:
        """构建 CodeBuddyAgentOptions，timeout 通过 request_timeout_ms 传入"""
        return CodeBuddyAgentOptions(
            codebuddy_code_path=self.cli_path,
            session_id=task_id,
            request_timeout_ms=(timeout * 1000) if timeout else None,
        )

    async def execute(
        self,
        task_id: str,
        model: str,
        description: str,
        feedback_md: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[str, Optional[str]]:
        prompt = description
        if feedback_md:
            prompt = (
                f"{feedback_md}\n\n"
                f"---\n"
                f"请继续根据上述反馈执行任务。\n\n"
                f"任务：{description}"
            )

        self._interrupt_flags[task_id] = False
        output_parts = []

        # Load/update session file
        session_data = self._load_session(task_id)
        self._save_session(task_id, session_data)

        try:
            from codebuddy_agent_sdk import CodeBuddySDKClient, CodeBuddyAgentOptions
            options = self._build_options(timeout, task_id)

            # SDK top-level query() returns AsyncIterator[Message]
            async for message in query(
                prompt=prompt,
                options=options,
            ):
                if self._interrupt_flags.get(task_id):
                    return "\n".join(output_parts), "Interrupted by user"

                if hasattr(message, 'content') and message.content:
                    for block in message.content:
                        if hasattr(block, 'text') and block.text:
                            output_parts.append(block.text)

                if hasattr(message, 'is_error') and message.is_error:
                    err_msg = getattr(message, 'error', 'Unknown SDK error')
                    return "\n".join(output_parts), f"SDK error: {err_msg}"

            return "\n".join(output_parts), None

        except ImportError:
            logger.warning(
                "codebuddy_agent_sdk not installed, SDKExecutor will not be usable. "
                "Install with: pip install codebuddy-agent-sdk"
            )
            return "", "codebuddy_agent_sdk not installed"

        except Exception as e:
            logger.error(f"SDKExecutor[{task_id}] error: {e}")
            return "\n".join(output_parts), str(e)

    async def cancel(self, task_id: str) -> bool:
        self._interrupt_flags[task_id] = True
        return True
