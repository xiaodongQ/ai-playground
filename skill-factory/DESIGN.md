# Skill 自动化工厂 — 方案设计文档

## 一、需求分析

### 背景与目标

搭建标准化、可复用、可沉淀、可自动迭代的**业务问题定位 Skill 开发工厂**，统一 Skill 定义、开发、验证、沉淀、复用全流程。核心目标：**用 Skill 生产 Skill** 的自动化闭环。

### 系统角色

| 角色 | 职责 |
|------|------|
| 平台管理员 | 创建任务、完善经验库、审核结果 |
| 后台管理系统 | 任务管理、经验库、API 输出 |
| Factory Skill | 自动拉取任务、TDD 开发、多轮迭代验收 |
| Redis 集群 Skill（示例业务） | 业务定位能力，作为工厂产出物 |

---

## 二、系统架构

### 后台管理系统（Go + SQLite）

**数据模型**：

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    experience_id TEXT,
    resources TEXT,
    acceptance TEXT,
    version TEXT DEFAULT 'v0.0.1',
    created_at DATETIME,
    claimed_at DATETIME,
    maintainer TEXT,
    repo_address TEXT,
    archived_at DATETIME,
    result TEXT
);

CREATE TABLE experiences (
    id TEXT PRIMARY KEY,
    module TEXT NOT NULL,
    keywords TEXT,
    log_paths TEXT,
    tool_usage TEXT,
    scene TEXT,
    log_samples TEXT,
    code_snippets TEXT,
    version TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

**API 接口**：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/tasks | 查询任务列表（支持状态过滤） |
| POST | /api/tasks | 创建任务 |
| GET | /api/tasks/:id | 获取任务详情 |
| PUT | /api/tasks/:id/status | 更新任务状态 |
| GET | /api/experiences | 查询经验库（支持模糊查询） |
| POST | /api/experiences | 创建经验记录 |

### 自动化工厂 Skill

**运行流程**：

```
1. 初始化：调用 GET /api/tasks?status=pending 拉取待认领任务
2. 任务认领：PUT /api/tasks/:id/status → in_progress
3. 获取经验：GET /api/experiences/:module 获取前置知识
4. TDD 开发（最多 20 轮）：
   a. 写测试用例
   b. 实现 Skill
   c. 运行测试，收集结果
   d. 准确率达标？用例全覆盖？无误判漏判？
      - 是 → 进入步骤 5
      - 否 → 迭代回到 4a
5. 上传产物，更新任务状态为 archived
6. 达到 20 轮未达标 → status=exception
```

**验收标准**：

| 维度 | 要求 |
|------|------|
| 准确率 | 正向用例全部通过（pass_rate = 1.0） |
| 误判（false_pos） | 0 |
| 漏判（false_neg） | 0 |
| 迭代上限 | 20 轮 |

---

## 三、Redis 分布式集群 Skill（示例业务）

### 前置经验库（Redis 模块）

```yaml
module: redis-cluster
keywords:
  - "CLUSTERDOWN"
  - "MOVED/ASK redirect"
  - "READONLY"
  - "slowlog"
  - "mem_fragmentation_ratio"
log_paths:
  - /var/log/redis/redis-server.log
tools:
  - redis-cli cluster nodes
  - redis-cli slowlog get 10
  - redis-cli --bigkeys
  - redis-cli memory stats
scenes:
  - 集群节点失联定位
  - 内存异常增长分析
  - 慢查询根因排查
```

### 验收样例

**正向用例**：

| 输入 | 预期输出 |
|------|---------|
| `CLUSTERDOWN The cluster is gone` | 定位 cluster-node-timeout，给出 redis.conf 调优建议 |
| `READONLY You can't write` | 识别只读场景，输出 replica 配置检查步骤 |
| slowlog 显示 > 5s 的 KEYS 命令 | 给出 SCAN 替换方案 |
| `mem_fragmentation_ratio > 1.5` | 给出 MEMORY PURGE + activedefrag 配置 |

**反向用例（脏数据）**：

| 输入 | 预期行为 |
|------|---------|
| 空 slowlog 输出 | 跳过分析，返回"无慢查询记录" |
| 非 Redis 日志 | 明确拒绝，输出"非 Redis 日志格式" |
| 二进制日志内容 | 友好提示"请提供文本日志" |

---

## 四、目录结构

```
skill-factory/
  cmd/server/
    main.go          # HTTP 服务入口
    index.html       # 内嵌 Web UI
  internal/
    backend/
      models.go      # 数据模型
      repo.go        # Repo 层（Task / Experience）
      server.go      # DB 初始化
      sqlite.go      # sqlite driver import
    task/            # TaskRepo TDD 测试
    experience/       # ExperienceRepo TDD 测试
  go.mod
  DESIGN.md

skills/
  redis-cluster-troubleshoot/  # 示例产出物
  skill-factory/               # Factory Skill
```

---

## 五、核心价值

1. **统一范式**：所有 Skill 开发遵循 4 项标准输入 + 验收闭环
2. **经验沉淀**：可查询、可导出、可团队复用
3. **自动化闭环**：TDD 迭代、量化验收、工业化自迭代生产
4. **职责清晰**：极简入参框架，剥离冗余环境配置