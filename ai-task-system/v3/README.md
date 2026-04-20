# AI Task System V3

CodeBuddy 个人内网专属版 - 基于豆包 AI 设计的任务自动化执行平台

## 特性

- 🎯 **原生适配**：100% 遵循腾讯 CodeBuddy CLI 规范
- 🚀 **极简部署**：单机无容器、零配置一键启动
- 📊 **全链路可观测**：WebSocket 实时同步 + 日志文件兜底
- 🔄 **双友好沉淀**：固定 Markdown 结构，人和 AI 都能零歧义读取
- ⚡ **双超时防护**：绝对超时 + 无输出超时，防止进程卡死

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境（可选）

```bash
cp .env.example .env
```

### 3. 启动服务

```bash
python main.py
```

访问 http://localhost:8000

### 4. 使用 CLI

```bash
# 创建并执行任务
python cli.py create -p "用 Python 写一个 Hello World"

# 查看任务列表
python cli.py list

# 续跑任务
python cli.py resume a1b2c3d4 "优化代码"

# 启动定时调度
python cli.py scheduler start
```

## 目录结构

```
v3/
├── main.py                 # Web 服务入口
├── cli.py                  # CLI 命令行入口
├── core/                   # 核心模块
│   ├── models.py          # 数据模型
│   ├── storage.py         # SQLite 存储
│   ├── executor.py        # CodeBuddy 执行器
│   ├── scheduler.py       # 任务调度器
│   └── realtime.py        # WebSocket 实时推送
├── system_docs/           # AI 自迭代文档
├── data/                  # 数据库目录
└── workspace/             # 任务沙箱目录
```

## 任务流程

1. **创建任务** → 生成 TASK.md
2. **自动领取** → 调度器分配给空闲 Agent
3. **执行任务** → CodeBuddy CLI 无头模式执行
4. **日志沉淀** → RUN_LOG.md 实时写入
5. **结果归档** → RESULT.md 结构化输出
6. **Git 版本** → 本地仓库自动提交

## License

MIT
