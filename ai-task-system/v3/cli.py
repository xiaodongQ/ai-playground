#!/usr/bin/env python3
"""
AI Task System V3 - CLI Entry Point
与 CodeBuddy 官方风格一致的命令行工具
"""
import argparse
import asyncio
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import Storage, Executor, Scheduler
from core.models import Task


def main():
    parser = argparse.ArgumentParser(
        description="AI Task System V3 - 任务管理与执行 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 创建并执行任务
    create_parser = subparsers.add_parser("create", help="创建新任务")
    create_parser.add_argument("-p", "--print", action="store_true", help="无头模式执行")
    create_parser.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    create_parser.add_argument("--title", type=str, help="任务标题")
    create_parser.add_argument("--allowed-tools", type=str, default="Read,Write,Bash,Git", help="允许工具")
    create_parser.add_argument("--permission-mode", type=str, default="acceptEdits", help="权限模式")
    create_parser.add_argument("--max-iterations", type=int, default=3, help="最大迭代次数")
    create_parser.add_argument("--timeout", type=int, default=3600, help="超时时间(秒)")
    create_parser.add_argument("description", type=str, nargs="+", help="任务描述")
    
    # 续跑任务
    resume_parser = subparsers.add_parser("resume", help="续跑任务")
    resume_parser.add_argument("task_id", type=str, help="任务ID")
    resume_parser.add_argument("message", type=str, nargs="+", help="续跑消息")
    
    # 任务列表
    list_parser = subparsers.add_parser("list", help="列出所有任务")
    list_parser.add_argument("--status", type=str, choices=["pending", "running", "completed", "failed"], help="状态过滤")
    
    # 查看任务
    get_parser = subparsers.add_parser("get", help="查看任务详情")
    get_parser.add_argument("task_id", type=str, help="任务ID")
    
    # 删除任务
    delete_parser = subparsers.add_parser("delete", help="删除任务")
    delete_parser.add_argument("task_id", type=str, help="任务ID")
    
    # 调度器控制
    scheduler_parser = subparsers.add_parser("scheduler", help="调度器控制")
    scheduler_sub = scheduler_parser.add_subparsers(dest="scheduler_cmd")
    scheduler_sub.add_parser("start", help="启动调度器")
    scheduler_sub.add_parser("stop", help="停止调度器")
    scheduler_sub.add_parser("status", help="查看状态")
    
    args = parser.parse_args()
    
    # 初始化组件
    storage = Storage(os.getenv("TASK_DB_PATH", "./data/tasks.db"))
    executor = Executor(os.getenv("WORKSPACE_ROOT", "./workspace"))
    scheduler = Scheduler(storage, executor)
    
    if args.command == "create":
        task = Task(
            title=args.title or " ".join(args.description[:5]),
            description=" ".join(args.description),
            allowed_tools=args.allowed_tools,
            permission_mode=args.permission_mode,
            max_iterations=args.max_iterations,
            absolute_timeout=args.timeout
        )
        storage.create_task(task)
        print(f"✅ 任务已创建: {task.id}")
        
        if args.print or args.yes:
            asyncio.run(scheduler.pick_and_execute(task))
            print(f"✅ 任务执行完成")
    
    elif args.command == "resume":
        task = storage.get_task(args.task_id)
        if not task:
            print(f"❌ 任务 {args.task_id} 不存在")
            sys.exit(1)
        
        task.session_id = task.session_id or task.id
        task.current_iteration += 1
        storage.update_task(task)
        
        asyncio.run(scheduler.pick_and_execute(task))
        print(f"✅ 任务续跑完成")
    
    elif args.command == "list":
        tasks = storage.list_tasks()
        if args.status:
            tasks = [t for t in tasks if t.status.value == args.status]
        
        if not tasks:
            print("暂无任务")
            return
        
        print(f"{'ID':<12} {'状态':<10} {'标题':<30} {'创建时间'}")
        print("-" * 80)
        for t in tasks:
            print(f"{t.id:<12} {t.status.value:<10} {t.title[:28]:<30} {t.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    elif args.command == "get":
        task = storage.get_task(args.task_id)
        if not task:
            print(f"❌ 任务 {args.task_id} 不存在")
            sys.exit(1)
        
        print(f"任务ID: {task.id}")
        print(f"标题: {task.title}")
        print(f"状态: {task.status.value}")
        print(f"创建时间: {task.created_at}")
        print(f"描述: {task.description}")
        if task.workspace_path:
            print(f"工作目录: {task.workspace_path}")
    
    elif args.command == "delete":
        success = storage.delete_task(args.task_id)
        if success:
            print(f"✅ 任务已删除")
        else:
            print(f"❌ 任务 {args.task_id} 不存在")
    
    elif args.command == "scheduler":
        if args.scheduler_cmd == "start":
            result = scheduler.start()
            print(f"调度器已启动 (间隔: {result['interval']}秒)")
        elif args.scheduler_cmd == "stop":
            asyncio.run(scheduler.stop())
            print("调度器已停止")
        elif args.scheduler_cmd == "status":
            status = scheduler.get_status()
            print(f"调度器状态: {'运行中' if status['running'] else '已停止'}")
            print(f"轮询间隔: {status['interval']}秒")
            print(f"最大并发: {status['max_concurrent']}")
        else:
            scheduler_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
