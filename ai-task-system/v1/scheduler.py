"""
AI Task Pickup System - Auto-Pickup Scheduler
Automatically picks and executes pending tasks
"""
import asyncio
import threading
from datetime import datetime
from typing import Optional, Callable

from models import Task, TaskStatus
from database import Database
from executor import TaskExecutor
from evaluator import TaskEvaluator


class TaskScheduler:
    def __init__(
        self,
        db: Database,
        executor: TaskExecutor,
        evaluator: TaskEvaluator,
        poll_interval: int = 30,  # seconds
        agent_name: str = "Claude Code"
    ):
        self.db = db
        self.executor = executor
        self.evaluator = evaluator
        self.poll_interval = poll_interval
        self.agent_name = agent_name
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks = []
    
    def add_callback(self, callback: Callable[[str, Task], None]):
        """Add callback for task status changes"""
        self._callbacks.append(callback)
    
    def _notify(self, event: str, task: Task):
        """Notify callbacks of task events"""
        for callback in self._callbacks:
            try:
                callback(event, task)
            except Exception as e:
                print(f"Callback error: {e}")
    
    async def pick_and_execute(self) -> Optional[Task]:
        """
        Pick a pending task and execute it
        Returns the completed task or None if no tasks available
        """
        # Get pending tasks
        pending_tasks = self.db.get_pending_tasks()
        
        if not pending_tasks:
            return None
        
        # Pick the first task (already sorted by priority)
        task = pending_tasks[0]
        
        # Update status to picked
        task = self.db.update_task_status(task.id, TaskStatus.PICKED)
        self._notify("picked", task)
        
        # Update status to executing
        task = self.db.update_task_status(task.id, TaskStatus.EXECUTING)
        self._notify("executing", task)
        
        # Add initial log
        self.db.add_task_log(task.id, f"[{datetime.now().strftime('%H:%M:%S')}] Task picked by {self.agent_name}")
        self.db.add_task_log(task.id, f"[{datetime.now().strftime('%H:%M:%S')}] Starting execution...")
        
        # Execute the task
        solution, result, logs = await self.executor.execute_task_sync(task)
        
        # Save logs
        for log in logs:
            self.db.add_task_log(task.id, log)
        
        # Save result
        task = self.db.set_task_result(task.id, solution, result)
        
        # Update status to completed
        task = self.db.update_task_status(task.id, TaskStatus.COMPLETED)
        self._notify("completed", task)
        
        # Auto-evaluate
        self.db.add_task_log(task.id, f"[{datetime.now().strftime('%H:%M:%S')}] Starting evaluation...")
        evaluation = await self.evaluator.evaluate_task_simple(task)
        task = self.db.set_task_evaluation(task.id, evaluation)
        
        # Update status to evaluated
        task = self.db.update_task_status(task.id, TaskStatus.EVALUATED)
        self._notify("evaluated", task)
        
        self.db.add_task_log(
            task.id, 
            f"[{datetime.now().strftime('%H:%M:%S')}] Evaluation complete: {evaluation.overall_score:.1f}/100"
        )
        
        return task
    
    def run_once(self):
        """Run one pickup cycle"""
        try:
            asyncio.run(self.pick_and_execute())
        except Exception as e:
            print(f"Pickup cycle error: {e}")
    
    def _run_loop(self):
        """Run the scheduler loop in a separate thread"""
        while self._running:
            self.run_once()
            # Sleep before next cycle
            for _ in range(self.poll_interval):
                if not self._running:
                    break
                import time
                time.sleep(1)
    
    def start(self):
        """Start the scheduler in background"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[Scheduler] Started, polling every {self.poll_interval}s")
    
    def stop(self):
        """Stop the scheduler"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[Scheduler] Stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._running


class MultiAgentScheduler(TaskScheduler):
    """
    Scheduler that manages multiple AI agents
    Each agent can pick tasks independently
    """
    def __init__(self, *args, num_agents: int = 2, **kwargs):
        super().__init__(*args, **kwargs)
        self.num_agents = num_agents
        self._agent_threads = []
    
    def start(self):
        """Start multiple agent pickers"""
        if self._running:
            return
        
        self._running = True
        
        # Start main scheduler thread
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        print(f"[MultiAgentScheduler] Started with {self.num_agents} agents")
    
    def _run_loop(self):
        """Run loop with multiple concurrent pickers"""
        import concurrent.futures
        
        while self._running:
            # Try to pick and execute multiple tasks concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_agents) as executor:
                # Submit pickup tasks
                futures = [executor.submit(self._pickup_one) for _ in range(self.num_agents)]
                
                # Wait for at least one to complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Agent error: {e}")
            
            # Sleep before next cycle
            import time
            time.sleep(self.poll_interval)
    
    def _pickup_one(self):
        """Pick and execute one task"""
        try:
            asyncio.run(self.pick_and_execute())
        except Exception as e:
            print(f"Pickup error: {e}")
