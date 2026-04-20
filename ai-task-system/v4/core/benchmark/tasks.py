"""V4 Agent 能力评估基准：标准任务库

定义各类任务的标准化测试任务（prompts），用于评估不同 Agent 的能力。
每个任务包含：ID、名称、类别、难度、prompt、参考解决方案、评估标准。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable


class TaskCategory(Enum):
    """任务大类"""
    CODING = auto()           # 编码实现
    DEBUGGING = auto()        # 调试修复
    REFACTORING = auto()      # 重构优化
    ARCHITECTURE = auto()     # 架构设计
    RESEARCH = auto()         # 技术研究
    WRITING = auto()          # 写作文档
    DEVOPS = auto()           # DevOps/基础设施


class Difficulty(Enum):
    """任务难度"""
    EASY = auto()
    MEDIUM = auto()
    HARD = auto()


@dataclass
class BenchmarkTask:
    """单个 Benchmark 任务"""
    id: str                          # 唯一标识，如 "CODING-001"
    name: str                         # 任务名称
    category: TaskCategory            # 任务大类
    difficulty: Difficulty            # 难度等级
    prompt: str                       # 发送给 Agent 的 prompt
    reference: str | None = None      # 参考解决方案（可选）
    eval_criteria: list[str] = field(default_factory=list)  # 评估标准列表
    tags: list[str] = field(default_factory=list)           # 标签
    expected_time_estimate: int | None = None  # 预期耗时（秒）
    # 评估函数：(agent_output, reference) -> (pass: bool, score: float 0-1, reason: str)
    evaluator: Callable[[str, str | None], tuple[bool, float, str]] | None = None

    @property
    def category_name(self) -> str:
        return self.category.name

    @property
    def difficulty_name(self) -> str:
        return self.difficulty.name.lower()


# ============================================================
# 标准 Benchmark 任务库
# ============================================================

BENCHMARK_TASKS: list[BenchmarkTask] = [

    # ===== CODING 编码实现 =====
    BenchmarkTask(
        id="CODING-001",
        name="Python 文件处理工具",
        category=TaskCategory.CODING,
        difficulty=Difficulty.EASY,
        prompt=(
            "用 Python 实现一个文件处理工具，包含以下功能：\n"
            "1. 统计文件中单词数量（按空格分割）\n"
            "2. 找出最频繁出现的 5 个单词\n"
            "3. 替换文件中的敏感词（传入 replacement 参数）\n"
            "要求：封装成类 FileProcessor，支持流式处理大文件。"
        ),
        tags=["python", "file-processing", "class-design"],
        expected_time_estimate=180,
    ),

    BenchmarkTask(
        id="CODING-002",
        name="并发任务调度器",
        category=TaskCategory.CODING,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "用 Go 实现一个并发任务调度器：\n"
            "1. 支持最多 N 个并发任务（N 可配置）\n"
            "2. 提交任务后返回 task_id\n"
            "3. 可通过 task_id 查询任务状态（pending/running/done/failed）\n"
            "4. 任务完成后可获取返回值或错误信息\n"
            "要求：线程安全，提供单元测试。"
        ),
        tags=["go", "concurrency", "scheduler", "testing"],
        expected_time_estimate=300,
    ),

    BenchmarkTask(
        id="CODING-003",
        name="REST API 设计与实现",
        category=TaskCategory.CODING,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "使用 FastAPI 实现一个 Todo API：\n"
            "1. POST /todos - 创建 todo（title, description, due_date 可选）\n"
            "2. GET /todos - 列出所有 todos（支持分页 page/size）\n"
            "3. GET /todos/{id} - 获取单个 todo\n"
            "4. PUT /todos/{id} - 更新 todo\n"
            "5. DELETE /todos/{id} - 删除 todo\n"
            "6. 数据存储在 SQLite 中，提供数据库初始化脚本\n"
            "要求：符合 OpenAPI 规范，包含请求验证。"
        ),
        tags=["python", "fastapi", "rest-api", "sqlite"],
        expected_time_estimate=360,
    ),

    BenchmarkTask(
        id="CODING-004",
        name="简易依赖注入容器",
        category=TaskCategory.CODING,
        difficulty=Difficulty.HARD,
        prompt=(
            "用 TypeScript 实现一个依赖注入（DI）容器：\n"
            "1. 支持三种生命周期：Singleton（单例）、Transient（每次新建）、RequestScoped（请求级）\n"
            "2. 通过装饰器 @Injectable() 标记可注入的服务\n"
            "3. 容器自动解析依赖图，支持构造函数注入\n"
            "4. 支持循环依赖检测并给出清晰错误\n"
            "5. 提供 container.resolve<T>(token) 方法获取实例\n"
            "要求：完整的类型定义，包含测试用例。"
        ),
        tags=["typescript", "di", "design-patterns", "testing"],
        expected_time_estimate=480,
    ),

    # ===== DEBUGGING 调试修复 =====
    BenchmarkTask(
        id="DEBUG-001",
        name="修复并发计数器 bug",
        category=TaskCategory.DEBUGGING,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "以下 Python 代码在并发场景下计数不准确，请分析原因并修复：\n\n"
            "```python\n"
            "import threading\n"
            "counter = 0\n\n"
            "def increment():\n"
            "    global counter\n"
            "    for _ in range(100000):\n"
            "        counter += 1\n\n"
            "threads = [threading.Thread(target=increment) for _ in range(10)]\n"
            "[t.start() for t in threads]\n"
            "[t.join() for t in threads]\n"
            "print(f'Result: {counter}')  # 期望: 1000000，实际往往更小\n"
            "```\n\n"
            "要求：解释 race condition 原因，给出修复方案，并验证修复有效。"
        ),
        tags=["python", "concurrency", "race-condition", "threading"],
        expected_time_estimate=240,
    ),

    BenchmarkTask(
        id="DEBUG-002",
        name="修复内存泄漏",
        category=TaskCategory.DEBUGGING,
        difficulty=Difficulty.HARD,
        prompt=(
            "一个长期运行的 Python Web 服务内存持续增长直到 OOM，请帮忙排查：\n"
            "已知信息：使用 Flask + gunicorn，启用了多 worker，每小时内存增长约 50MB。\n"
            "请提供：\n"
            "1. 排查思路（列出你将使用的工具和方法）\n"
            "2. 最可能的泄漏原因分类\n"
            "3. 对应的修复方案代码示例\n"
            "4. 如何验证修复有效"
        ),
        tags=["python", "memory-leak", "flask", "profiling"],
        expected_time_estimate=360,
    ),

    BenchmarkTask(
        id="DEBUG-003",
        name="API 偶发性 500 错误排查",
        category=TaskCategory.DEBUGGING,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "生产环境 API 偶发返回 500 错误（千分之一概率），日志如下：\n\n"
            "\n```\nTraceback (most recent call last):\n"
            "    user = db.query(User).filter_by(id=user_id).first()\n"
            "AttributeError: 'NoneType' object has no attribute 'filter_by'\n"
            "```\n\n"
            "请分析：1. 可能原因 2. 如何复现 3. 修复方案 4. 预防措施"
        ),
        tags=["debugging", "python", "null-handling", "production"],
        expected_time_estimate=180,
    ),

    # ===== REFACTORING 重构优化 =====
    BenchmarkTask(
        id="REFACTOR-001",
        name="重构长函数",
        category=TaskCategory.REFACTORING,
        difficulty=Difficulty.EASY,
        prompt=(
            "以下函数过于冗长，请重构：\n\n"
            "```python\n"
            "def process_order(order_data):\n"
            "    # 验证订单数据\n"
            "    if not order_data.get('customer_id'):\n"
            "        raise ValueError('customer_id required')\n"
            "    if not order_data.get('items'):\n"
            "        raise ValueError('items required')\n"
            "    # 计算总价\n"
            "    total = 0\n"
            "    for item in order_data['items']:\n"
            "        total += item['price'] * item['quantity']\n"
            "    # 应用折扣\n"
            "    if total > 1000:\n"
            "        total *= 0.9\n"
            "    elif total > 500:\n"
            "        total *= 0.95\n"
            "    # 创建订单记录\n"
            "    order = Order(\n"
            "        customer_id=order_data['customer_id'],\n"
            "        total=total,\n"
            "        status='pending'\n"
            "    )\n"
            "    db.add(order)\n"
            "    # 发送通知\n"
            "    send_email(order_data.get('email', ''), 'Order confirmed')\n"
            "    return order\n"
            "```\n\n"
            "请：1. 识别违反的原则 2. 重构代码 3. 解释改进点"
        ),
        tags=["refactoring", "clean-code", "single-responsibility"],
        expected_time_estimate=180,
    ),

    BenchmarkTask(
        id="REFACTOR-002",
        name="微服务解耦重构",
        category=TaskCategory.REFACTORING,
        difficulty=Difficulty.HARD,
        prompt=(
            "当前单体应用存在以下问题，请设计重构方案：\n"
            "1. 用户模块、订单模块、支付模块紧耦合\n"
            "2. 任意模块 Bug 导致整体崩溃\n"
            "3. 部署时间长（30min+）\n"
            "4. 数据库单点，所有模块共享一个 DB\n\n"
            "请提供：\n"
            "1. 微服务拆分策略（边界、数据、通讯）\n"
            "2. 逐步迁移路径（避免 big bang）\n"
            "3. 关键技术方案（服务发现、分布式事务、日志追踪）\n"
            "4. 风险缓解措施\n"
            "5. 预期收益量化"
        ),
        tags=["refactoring", "microservices", "architecture", "migration"],
        expected_time_estimate=480,
    ),

    # ===== ARCHITECTURE 架构设计 =====
    BenchmarkTask(
        id="ARCH-001",
        name="高并发短链接服务设计",
        category=TaskCategory.ARCHITECTURE,
        difficulty=Difficulty.HARD,
        prompt=(
            "设计一个短链接服务（如 t.cn/abc123）：\n"
            "目标：\n"
            "- QPS 峰值 10万/秒\n"
            "- 延迟 P99 < 50ms\n"
            "- 99.99% 可用性\n"
            "- 存储 100 亿条链接\n\n"
            "请提供：\n"
            "1. 整体架构图（组件、流量、存储）\n"
            "2. 短码生成算法（防碰撞、防预测）\n"
            "3. 数据模型与存储选型（SQL vs NoSQL vs KV）\n"
            "4. 缓存策略（多级缓存、失效机制）\n"
            "5. 扩缩容方案\n"
            "6. 监控与告警指标"
        ),
        tags=["architecture", "high-concurrency", "system-design", "distributed-systems"],
        expected_time_estimate=600,
    ),

    BenchmarkTask(
        id="ARCH-002",
        name="消息队列选型对比",
        category=TaskCategory.ARCHITECTURE,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "场景：订单完成后需要发送通知（短信/邮件/推送），QPS 约 1000，\n"
            "允许最终一致性，允许少量消息丢失但需控制，允许重复消费（幂等处理）。\n\n"
            "请对比 Kafka / RabbitMQ / Redis Stream / RocketMQ：\n"
            "1. 各方案的优缺点\n"
            "2. 为什么选择（或不选）Kafka\n"
            "3. 消费者组设计\n"
            "4. 消息持久化与可靠性配置\n"
            "5. 失败重试与死信队列设计"
        ),
        tags=["architecture", "messaging", "kafka", "distributed-systems"],
        expected_time_estimate=360,
    ),

    # ===== RESEARCH 技术研究 =====
    BenchmarkTask(
        id="RESEARCH-001",
        name="Python GIL 深度研究",
        category=TaskCategory.RESEARCH,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "深入研究 Python GIL（Global Interpreter Lock）：\n"
            "1. GIL 是什么，为什么存在\n"
            "2. GIL 如何影响多线程性能\n"
            "3. IO 密集型 vs CPU 密集型任务在多线程中的表现差异\n"
            "4. 绕过 GIL 的方法（multiprocessing、uvloop、C 扩展）\n"
            "5. Python 3.13 的 no-GIL 实验进展\n"
            "6. 在 Web 服务中的最佳实践\n\n"
            "要求：包含代码示例和性能数据对比。"
        ),
        tags=["python", "gil", "concurrency", "performance"],
        expected_time_estimate=480,
    ),

    BenchmarkTask(
        id="RESEARCH-002",
        name="RAG vs Fine-tuning 对比研究",
        category=TaskCategory.RESEARCH,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "在企业知识库问答场景下，对比 RAG 和 Fine-tuning 两种方案：\n"
            "1. 两种方案的核心原理\n"
            "2. 在以下指标上的对比：\n"
            "   - 开发成本\n"
            "   - 推理成本\n"
            "   - 知识更新时效性\n"
            "   - 回答准确性\n"
            "   - 幻觉率控制\n"
            "3. 适用场景分析\n"
            "4. 混合方案的可能性\n"
            "5. 主流开源方案推荐"
        ),
        tags=["rag", "fine-tuning", "llm", "knowledge-base"],
        expected_time_estimate=360,
    ),

    # ===== WRITING 写作文档 =====
    BenchmarkTask(
        id="WRITING-001",
        name="技术博客：缓存设计",
        category=TaskCategory.WRITING,
        difficulty=Difficulty.EASY,
        prompt=(
            "撰写一篇技术博客，要求：\n"
            "标题：高性能系统设计之缓存策略\n"
            "读者：中级后端工程师\n"
            "内容包括：\n"
            "1. 缓存的本质（以空间换时间）\n"
            "2. 缓存读写模式（Cache-Aside / Read-Through / Write-Through）\n"
            "3. 缓存三大问题：穿透、击穿、雪崩\n"
            "4. 解决方案详解\n"
            "5. Redis vs Memcached 选择\n"
            "6. 实际案例代码\n\n"
            "要求：图文并茂，有代码示例，有流程图描述（文字版）。"
        ),
        tags=["writing", "blog", "cache", "system-design"],
        expected_time_estimate=300,
    ),

    BenchmarkTask(
        id="WRITING-002",
        name="API 文档编写",
        category=TaskCategory.WRITING,
        difficulty=Difficulty.EASY,
        prompt=(
            "为以下 API 编写完整的 API 文档（使用 OpenAPI 3.0 规范）：\n\n"
            "API 功能：用户管理\n"
            "- POST /users - 创建用户（username, email, password）\n"
            "- GET /users/{id} - 获取用户信息\n"
            "- PUT /users/{id} - 更新用户信息\n"
            "- DELETE /users/{id} - 删除用户\n"
            "- GET /users - 分页列表（page, page_size, sort）\n\n"
            "请输出完整的 OpenAPI YAML，并包含：\n"
            "请求/响应示例、错误码说明、认证方式、字段验证规则。"
        ),
        tags=["writing", "documentation", "openapi", "api-design"],
        expected_time_estimate=240,
    ),

    # ===== DEVOPS 基础设施 =====
    BenchmarkTask(
        id="DEVOPS-001",
        name="Docker Compose 生产配置",
        category=TaskCategory.DEVOPS,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "为一个 Flask API 服务编写生产级 Docker Compose 配置：\n"
            "服务组件：\n"
            "1. Flask API（gunicorn 多 worker）\n"
            "2. PostgreSQL 数据库\n"
            "3. Redis 缓存\n"
            "4. Nginx 反向代理\n\n"
            "要求：\n"
            "- 健康检查\n"
            "- 日志收集（结构化 JSON）\n"
            "- 资源限制（CPU/内存）\n"
            "- 重启策略\n"
            "- 敏感信息通过 env_file 管理\n"
            "- 合理的网络配置"
        ),
        tags=["devops", "docker", "docker-compose", "flask", "production"],
        expected_time_estimate=360,
    ),

    BenchmarkTask(
        id="DEVOPS-002",
        name="GitLab CI 流水线设计",
        category=TaskCategory.DEVOPS,
        difficulty=Difficulty.MEDIUM,
        prompt=(
            "为 Python FastAPI 项目设计 GitLab CI 流水线：\n\n"
            "阶段要求：\n"
            "1. 阶段 1（.pre）：环境检查\n"
            "2. 阶段 2（build）：依赖安装（缓存优化）\n"
            "3. 阶段 3（test）：单元测试 + 集成测试 + 覆盖率上传\n"
            "4. 阶段 4（security）：SAST 扫描、依赖审计\n"
            "5. 阶段 5（build-image）：构建并推送 Docker 镜像\n"
            "6. 阶段 6（deploy-staging）：部署到预发布环境\n"
            "7. 阶段 7（deploy-prod）：蓝绿部署到生产（手动触发）\n\n"
            "要求：.gitlab-ci.yml 完整配置，包含 rules（分支过滤）、artifacts、cache。"
        ),
        tags=["devops", "ci-cd", "gitlab", "python", "docker"],
        expected_time_estimate=480,
    ),
]


def get_tasks_by_category(category: TaskCategory) -> list[BenchmarkTask]:
    return [t for t in BENCHMARK_TASKS if t.category == category]


def get_tasks_by_difficulty(difficulty: Difficulty) -> list[BenchmarkTask]:
    return [t for t in BENCHMARK_TASKS if t.difficulty == difficulty]


def get_task_by_id(task_id: str) -> BenchmarkTask | None:
    for t in BENCHMARK_TASKS:
        if t.id == task_id:
            return t
    return None


def get_tasks_by_tags(tags: list[str]) -> list[BenchmarkTask]:
    """获取包含任一标签的任务"""
    return [t for t in BENCHMARK_TASKS if any(tag in t.tags for tag in tags)]


CATEGORY_DISPLAY_NAMES: dict[TaskCategory, str] = {
    TaskCategory.CODING: "🛠️ 编码实现",
    TaskCategory.DEBUGGING: "🔍 调试修复",
    TaskCategory.REFACTORING: "♻️ 重构优化",
    TaskCategory.ARCHITECTURE: "🏗️ 架构设计",
    TaskCategory.RESEARCH: "📚 技术研究",
    TaskCategory.WRITING: "✍️ 写作文档",
    TaskCategory.DEVOPS: "⚙️ DevOps",
}
