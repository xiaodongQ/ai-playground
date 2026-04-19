import logging
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from codebuddy_agent_sdk import CodeBuddySDKClient, CodeBuddyAgentOptions  # noqa: F401
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
        client: Optional[CodeBuddySDKClient] = None

        # Load/update session file
        session_data = self._load_session(task_id)
        self._save_session(task_id, session_data)

        try:
            options = self._build_options(timeout, task_id)
            client = CodeBuddySDKClient(options=options)
            self._clients[task_id] = client

            # Connect in streaming mode (prompt=None) so we control when to send
            await client.connect(prompt=None)

            # Send the prompt
            await client.query(prompt)

            # Process messages with aggressive interrupt checking
            async for message in client.receive_messages():
                # Check interrupt flag after every message block
                if self._interrupt_flags.get(task_id):
                    return "\n".join(output_parts), "Interrupted by user"

                # Extract text content from message blocks
                if hasattr(message, 'content') and message.content:
                    for block in message.content:
                        if hasattr(block, 'text') and block.text:
                            output_parts.append(block.text)

                # Check interrupt again after processing content blocks
                if self._interrupt_flags.get(task_id):
                    return "\n".join(output_parts), "Interrupted by user"

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

        finally:
            # Clean up client
            if client is not None:
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.warning(f"SDKExecutor[{task_id}] disconnect error: {e}")
            self._clients.pop(task_id, None)
            self._interrupt_flags.pop(task_id, None)

    async def interrupt(self, task_id: str) -> bool:
        """Send native SDK interrupt to the task's CodeBuddy client.

        Tries to use the SDK's native interrupt capability if a client
        is active for this task. Falls back to flag-based interrupt.
        """
        # Set the flag first to ensure interrupt is triggered
        self._interrupt_flags[task_id] = True

        client = self._clients.get(task_id)
        if client is not None:
            try:
                await client.interrupt()
                logger.info(f"SDKExecutor[{task_id}] native interrupt sent")
            except Exception as e:
                logger.warning(f"SDKExecutor[{task_id}] native interrupt failed: {e}")
        else:
            logger.info(f"SDKExecutor[{task_id}] no active client, using flag only")

        return True

    async def cancel(self, task_id: str) -> bool:
        """Public API: cancel a running task.

        Calls interrupt() to send native SDK interrupt, then performs
        cleanup of the client and session state.
        """
        await self.interrupt(task_id)

        # Additional cleanup
        client = self._clients.pop(task_id, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

        self._interrupt_flags.pop(task_id, None)
        return True
