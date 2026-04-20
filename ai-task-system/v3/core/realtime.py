"""
AI Task System V3 - Realtime Module
WebSocket 实时推送
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket


class RealtimeManager:
    """WebSocket 实时管理器"""

    def __init__(self):
        # 全局连接池
        self._global_connections: Set[WebSocket] = set()
        # 单任务连接池
        self._task_connections: Dict[str, Set[WebSocket]] = {}
        # 心跳任务
        self._heartbeat_task: asyncio.Task = None

    async def connect_global(self, websocket: WebSocket):
        """连接全局事件"""
        await websocket.accept()
        self._global_connections.add(websocket)

    async def connect_task(self, task_id: str, websocket: WebSocket):
        """连接单任务事件"""
        await websocket.accept()
        if task_id not in self._task_connections:
            self._task_connections[task_id] = set()
        self._task_connections[task_id].add(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str = None):
        """断开连接"""
        if task_id:
            if task_id in self._task_connections:
                self._task_connections[task_id].discard(websocket)
        else:
            self._global_connections.discard(websocket)

    async def broadcast(self, event_type: str, data: dict, task_id: str = None):
        """广播事件"""
        event = {
            "event_id": f"{datetime.now().timestamp()}",
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "version": "1.0"
        }
        
        message = json.dumps(event)
        
        # 发送给全局连接
        if not task_id:
            disconnected = []
            for ws in self._global_connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self._global_connections.discard(ws)
        
        # 发送给任务连接
        if task_id and task_id in self._task_connections:
            disconnected = []
            for ws in self._task_connections[task_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self._task_connections[task_id].discard(ws)

    async def send_task_created(self, task: dict):
        """发送任务创建事件"""
        await self.broadcast("task_created", {"task": task})

    async def send_task_status_changed(self, task_id: str, old_status: str, new_status: str):
        """发送任务状态变更事件"""
        await self.broadcast("task_status_changed", {
            "task_id": task_id,
            "old_status": old_status,
            "new_status": new_status
        }, task_id)

    async def send_task_log(self, task_id: str, log: str, level: str = "info"):
        """发送任务日志事件"""
        await self.broadcast("task_log_appended", {
            "task_id": task_id,
            "log": log,
            "level": level,
            "timestamp": datetime.now().isoformat()
        }, task_id)

    async def send_task_completed(self, task_id: str, result: dict):
        """发送任务完成事件"""
        await self.broadcast("task_completed", {
            "task_id": task_id,
            "result": result
        }, task_id)

    async def send_task_failed(self, task_id: str, error: str):
        """发送任务失败事件"""
        await self.broadcast("task_failed", {
            "task_id": task_id,
            "error": error
        }, task_id)

    async def _heartbeat_loop(self):
        """心跳保活循环"""
        while True:
            await asyncio.sleep(30)
            # 清理断开的连接
            for ws in list(self._global_connections):
                try:
                    await ws.send_text(json.dumps({"type": "heartbeat"}))
                except Exception:
                    self._global_connections.discard(ws)

    def start_heartbeat(self):
        """启动心跳"""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def stop_heartbeat(self):
        """停止心跳"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
