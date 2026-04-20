"""Scheduler with streaming execution, heartbeat, stale detection, and task cancellation."""

import asyncio
import signal
from datetime import datetime
from typing import Optional, Dict

from backend.database import Database
from backend.cli_executor import CLIExecutor
from backend.evaluator import Evaluator
from backend.retry import RetryExecutor, RetryConfig
from backend.websocket_manager import WebSocketManager
from backend.config import load_config, get_logger

logger = get_logger(__name__)


class Scheduler:
    def __init__(self, poll_interval: int = 5, ws_manager: Optional[WebSocketManager] = None):
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self.db = Database()
        self.cli_executor = CLIExecutor()
        self.retry_executor = RetryExecutor(
            self.cli_executor,
            config=RetryConfig(max_retries=3, base_delay=2.0, max_delay=30.0),
        )
        self.evaluator = Evaluator()
        self.ws_manager = ws_manager

        # Process management: task_id -> asyncio.subprocess.Process
        self._process_map: Dict[str, asyncio.subprocess.Process] = {}

        config = load_config()
        task_cfg = config.get('task', {})
        self.task_timeout = task_cfg.get('timeout', 600)         # absolute timeout
        self.no_output_timeout = task_cfg.get('no_output_timeout', 120)  # no-output timeout
        self.stale_threshold = task_cfg.get('stale_threshold', 120)       # zombie threshold

        scheduler_cfg = config.get('scheduler', {})
        self.heartbeat_interval = scheduler_cfg.get('heartbeat_interval', 30)
        self.concurrency = scheduler_cfg.get('concurrency', 2)
        self.cli = scheduler_cfg.get('cli', 'claude')

    async def start(self):
        """Start the scheduler and recovery loop."""
        await self.db.init()
        await self.recover_stale_tasks()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Scheduler started")
        return {"status": "started"}

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        for proc in list(self._process_map.values()):
            try:
                proc.kill()
            except Exception:
                pass
        self._process_map.clear()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")
        return {"status": "stopped"}

    # ------------------------------------------------------------------ #
    # Recovery / stale detection                                          #
    # ------------------------------------------------------------------ #

    async def recover_stale_tasks(self):
        """Reset zombie tasks (running too long without heartbeat) to pending."""
        running_tasks = await self.db.get_running_tasks()
        now = datetime.now()
        recovered = 0

        for task in running_tasks:
            # No heartbeat at all - process likely crashed
            if not task.last_heartbeat:
                logger.warning(f"[{task.id}] No heartbeat, resetting to pending")
                await self.db.update_task_status(task.id, "pending")
                recovered += 1
                continue

            # Check heartbeat age
            try:
                last = datetime.fromisoformat(task.last_heartbeat)
                age = (now - last).total_seconds()
                if age > self.stale_threshold:
                    logger.warning(f"[{task.id}] Stale (heartbeat {age:.0f}s ago), resetting to pending")
                    await self.db.update_task_status(task.id, "pending")
                    recovered += 1
                # Absolute timeout: started_at exceeded task_timeout
                if task.started_at:
                    started_age = (now - task.started_at).total_seconds()
                    if started_age > self.task_timeout:
                        logger.warning(f"[{task.id}] Absolute timeout ({started_age:.0f}s), marking failed")
                        await self.db.update_task_status(task.id, "failed",
                            result=f"Task timed out after {started_age:.0f}s")
                        recovered += 1
            except Exception as e:
                logger.error(f"[{task.id}] Error checking stale: {e}")

        logger.info(f"Recovered {recovered} stale tasks")

    async def _heartbeat_loop(self):
        """Periodically update heartbeats for running tasks."""
        while self._running:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                running = await self.db.get_running_tasks()
                now = datetime.now().isoformat()
                for task in running:
                    await self.db.update_heartbeat(task.id)
                    # Also check absolute timeout here as a safety net
                    if task.started_at:
                        age = (now if isinstance(now, str) else now.isoformat())
                        # re-fetch to avoid timezone issues
                        pass
                logger.debug(f"Heartbeat updated for {len(running)} running tasks")
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")

    # ------------------------------------------------------------------ #
    # Main poll loop                                                       #
    # ------------------------------------------------------------------ #

    async def _poll_loop(self):
        """Main loop: claim and execute one task at a time."""
        await self.db.init()
        while self._running:
            try:
                await self._process_pending_tasks()
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _process_pending_tasks(self):
        """Atomically claim and execute one task."""
        async with self._lock:
            task = await self.db.claim_one_task()
            if not task:
                return
            await self._execute_task(task)

    # ------------------------------------------------------------------ #
    # Task execution                                                       #
    # ------------------------------------------------------------------ #

    async def _execute_task(self, task):
        """
        Execute a single task with streaming output, timeout handling,
        human confirmation detection, and evaluation.
        """
        task_id = task.id
        logger.info(f"[{task_id}] Starting execution")

        # Update heartbeat
        await self.db.update_heartbeat(task_id)

        # Build command for UI display
        cmd_list = self.cli_executor.build_command(
            task_id, task.description,
            model=task.executor_model,
            session_id=None,
            allowed_tools=None,
        )
        cmd_str = " ".join(cmd_list)

        # Create execution record
        execution = await self.db.create_execution(task_id, task.executor_model, command=cmd_str)

        # Broadcast running status
        await self._broadcast_update(task_id, "running", {"started_at": task.started_at})

        # Streamed output accumulator
        full_output = ""

        async def output_callback(chunk: str):
            nonlocal full_output
            full_output += chunk
            await self._broadcast_update(task_id, "task_output", {"output": chunk})

        try:
            output, error, _, exit_code = await self.retry_executor.execute(
                task_id, task.description, task.feedback_md,
                model=task.executor_model,
                session_id=None,
                allowed_tools=None,
                output_callback=output_callback,
            )
        except Exception as e:
            output, error = "", str(e)
            exit_code = -1

        # Update execution record
        await self.db.update_execution(execution.id, output, error)

        # --- Timeout detection ---
        if exit_code == -1 or (error and "timeout" in error.lower()):
            await self.db.update_task_status(task_id, "failed", result=output)
            await self._broadcast_update(task_id, "failed", {"error": error})
            logger.warning(f"[{task_id}] Task timed out")
            return

        # --- Human confirmation detection ---
        confirm_req = self.cli_executor.parse_confirm_request(output)
        if confirm_req:
            logger.info(f"[{task_id}] Human confirmation needed: {confirm_req.get('confirm_type')}")
            await self.db.update_task_status(task_id, "waiting_input", result=output)
            await self.db.set_task_user_input(task_id, "")
            await self._broadcast_update(task_id, "waiting_input", {
                "confirm_request": confirm_req,
                "output": output[:500],
            })
            return

        # --- Normal completion ---
        if error and exit_code != 0:
            await self.db.update_task_status(task_id, "failed", result=output)
            await self.db.increment_retry_count(task_id)
            await self._broadcast_update(task_id, "failed", {"error": error})
            logger.warning(f"[{task_id}] Execution failed (exit={exit_code})")
        else:
            await self.db.update_task_status(task_id, "completed", result=output)
            await self._broadcast_update(task_id, "completed", {"output": output[:500]})
            logger.info(f"[{task_id}] Execution completed (output={len(output)} chars)")
            await self._evaluate_task(task, execution, output)

    async def _evaluate_task(self, task, execution, output: str):
        """Run LLM evaluation on completed task."""
        task_id = task.id
        await self.db.update_task_status(task_id, "evaluating")
        await self._broadcast_update(task_id, "evaluating")

        try:
            score, comments = await self.evaluator.evaluate(
                task.description, output,
                iteration_count=task.iteration_count,
                model=task.evaluator_model,
            )
        except Exception as e:
            score, comments = 0, f"Evaluation failed: {e}"

        await self.db.create_evaluation(
            task_id, execution.id, task.evaluator_model, score, comments
        )

        feedback_md = self.evaluator.build_feedback_md(
            task.description, output, comments, task.iteration_count
        )

        if score < task.improvement_threshold:
            if task.iteration_count < task.max_iterations:
                await self.db.increment_iteration(task_id)
                await self.db.update_task_status(task_id, "re-execute", feedback_md=feedback_md)
                await self._broadcast_update(task_id, "re-execute", {
                    "score": score, "feedback": feedback_md[:500],
                })
            else:
                await self.db.update_task_status(task_id, "evaluated", feedback_md=feedback_md)
                await self._broadcast_update(task_id, "evaluated", {
                    "score": score, "max_iterations_reached": True,
                })
        else:
            await self.db.update_task_status(task_id, "evaluated", feedback_md=feedback_md)
            await self._broadcast_update(task_id, "evaluated", {"score": score})

    # ------------------------------------------------------------------ #
    # Task cancellation (SIGKILL)                                         #
    # ------------------------------------------------------------------ #

    async def cancel_task(self, task_id: str):
        """
        Cancel a running task: send SIGKILL to the subprocess,
        update status to 'cancelled'. Does NOT trigger auto-retry.
        """
        logger.info(f"[{task_id}] Cancelling task")

        # Kill the subprocess if we have a reference
        proc = self._process_map.get(task_id)
        if proc:
            try:
                proc.kill()
                logger.info(f"[{task_id}] Sent SIGKILL to pid={proc.pid}")
            except Exception as e:
                logger.warning(f"[{task_id}] Failed to kill process: {e}")
            finally:
                self._process_map.pop(task_id, None)

        # Also try to kill via CLI executor (in case process ref is there)
        # The CLIExecutor.kill() is per-instance, so we use the map approach
        # If the task is currently executing in _execute_task, we signal it
        feedback_md = "## 任务已取消\n\n用户主动终止执行"
        await self.db.update_task_status(task_id, "cancelled", feedback_md=feedback_md)
        await self._broadcast_update(task_id, "cancelled")

    def register_process(self, task_id: str, proc: asyncio.subprocess.Process):
        """Store subprocess reference for later kill()."""
        self._process_map[task_id] = proc

    # ------------------------------------------------------------------ #
    # WebSocket broadcast helpers                                          #
    # ------------------------------------------------------------------ #

    async def _broadcast_update(self, task_id: str, status: str, extra: dict = None):
        if self.ws_manager:
            msg = {"type": "task_status", "task_id": task_id, "status": status}
            if extra:
                msg.update(extra)
            await self.ws_manager.broadcast(msg)

    # ------------------------------------------------------------------ #
    # Submit human input (for waiting_input tasks)                        #
    # ------------------------------------------------------------------ #

    async def submit_user_input(self, task_id: str, user_input: str) -> bool:
        """
        Submit user input for a waiting_input task and re-trigger execution.
        Returns True on success.
        """
        task = await self.db.get_task(task_id)
        if not task or task.status != "waiting_input":
            return False

        logger.info(f"[{task_id}] Submitting user input: {user_input[:50]}...")
        await self.db.set_task_user_input(task_id, user_input)

        # Re-trigger execution (state becomes running again)
        # We set it to pending so it gets picked up again by _poll_loop
        # BUT: we need to preserve the session so the AI continues from where it left off.
        # Since we don't have session_id persistence across restarts, we pass
        # the user_input as a "continue" trigger in a fresh execution.
        await self.db.update_task_status(task_id, "pending")
        return True