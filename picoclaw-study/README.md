# PicoClaw 源码学习笔记

> 📚 系统性学习 PicoClaw 超轻量级 AI Agent 框架的完整指南

**学习时间**: 2026-03-29 启动  
**目标**: 深入理解 PicoClaw 架构设计，掌握嵌入式 AI Agent 开发能力

---

## 📖 目录结构

```
picoclaw-study/
├── README.md                 # 本文件 - 学习导航
├── 00-learning-path.md       # 学习路径规划
├── notes/                    # 学习笔记
│   ├── 01-architecture.md    # 架构解析
│   ├── 02-core-components.md # 核心组件
│   ├── 03-execution-flow.md  # 执行流程
│   └── 04-design-patterns.md # 设计模式
├── src-analysis/             # 源码分析
│   ├── agent-instance.md     # AgentInstance 分析
│   ├── agent-loop.md         # AgentLoop 分析
│   ├── tool-registry.md      # ToolRegistry 分析
│   └── gateway.md            # Gateway 分析
├── diagrams/                 # 架构图
│   ├── architecture.png      # 整体架构
│   └── flow-chart.md         # 流程图（Mermaid）
├── examples/                 # 实践示例
│   ├── custom-tool.go        # 自定义工具
│   └── multi-agent.md        # 多 Agent 示例
└── references/               # 参考资料
    ├── official-docs.md      # 官方文档
    └── comparisons.md        # 框架对比
```

---

## 🎯 学习目标

### 阶段一：理解架构（1-2 天）
- [ ] 理解 PicoClaw 的设计哲学和定位
- [ ] 掌握核心组件和它们的关系
- [ ] 画出完整的架构图

### 阶段二：源码精读（3-5 天）
- [ ] 深入阅读 `pkg/agent/instance.go`
- [ ] 深入阅读 `pkg/agent/loop.go`
- [ ] 理解工具注册和执行机制
- [ ] 分析 Gateway 多通道集成

### 阶段三：实践应用（2-3 天）
- [ ] 编写自定义工具
- [ ] 配置多 LLM 提供商
- [ ] 部署到边缘设备（可选）

### 阶段四：扩展开发（可选）
- [ ] 添加新通道支持
- [ ] 实现自定义持久化
- [ ] 优化性能瓶颈

---

## 📚 快速开始

### 前置知识
- ✅ Go 语言基础
- ✅ HTTP API 调用
- ✅ LLM 基础概念（Prompt/Tool Calling）

### 环境准备
```bash
# 克隆 PicoClaw
git clone https://github.com/sipeed/picoclaw.git

# 本学习笔记
cd ai-playground/picoclaw-study
```

---

## 📋 学习笔记索引

| 笔记 | 内容 | 预计时间 |
|------|------|---------|
| [01-架构解析](notes/01-architecture.md) | 整体架构、设计理念 | 1h |
| [02-核心组件](notes/02-core-components.md) | 四大核心模块详解 | 2h |
| [03-执行流程](notes/03-execution-flow.md) | AgentLoop 执行循环 | 1.5h |
| [04-设计模式](notes/04-design-patterns.md) | Go 设计模式应用 | 1h |

---

## 🔗 相关链接

- **PicoClaw 官方**: https://github.com/sipeed/picoclaw
- **官方文档**: https://mintlify.com/sipeed/picoclaw
- **OpenClaw 对比**: [references/comparisons.md](references/comparisons.md)

---

## 📝 学习记录

| 日期 | 内容 | 进度 |
|------|------|------|
| 2026-03-29 | 启动学习项目，创建仓库结构 | ✅ 完成 |
| 2026-03-29 | 完成架构解析笔记 | ✅ 完成 |
| 2026-03-29 | 完成核心组件分析 | ✅ 完成 |

---

**持续更新中...** 🖤
