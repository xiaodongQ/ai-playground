# PicoClaw 学习路径规划

> 🗺️ 基于实际源码的学习路线（2026 年版本）

---

## 📊 学习地图

```
Week 1: 基础理解                    Week 2: 源码精读
┌─────────────────────┐           ┌─────────────────────┐
│ Day 1-2: 架构概览    │           │ Day 8-9: AgentLoop  │
│ - 项目定位与特点     │           │ - 主循环结构        │
│ - 核心组件           │           │ - 消息处理流程      │
│ - 与 OpenClaw 对比   │           │ - 工具调用机制      │
├─────────────────────┤           ├─────────────────────┤
│ Day 3-4: 组件深入    │           │ Day 10-11: Registry │
│ - AgentLoop         │           │ - 多 Agent 管理       │
│ - AgentInstance     │           │ - 路由解析          │
│ - ToolRegistry      │           │ - SubAgent 机制      │
├─────────────────────┤           ├─────────────────────┤
│ Day 5-7: 数据流     │            │ Day 12-14: Gateway  │
│ - MessageBus        │            │ - 服务启动流程      │
│ - Channels 管理      │            │ - 配置热更新        │
│ - Provider 适配      │            │ - 通道集成          │
└─────────────────────┘           └─────────────────────┘
```

---

## 📖 详细学习大纲

### 第一阶段：基础理解（Day 1-7）

#### Day 1: 项目概览
- [ ] 阅读官方 README 和 ROADMAP
- [ ] 理解 PicoClaw 的定位（vs OpenClaw/Nanobot）
- [ ] 搭建本地开发环境
- [ ] 运行 Hello World 示例

**关键文件**:
- `README.md` - 项目介绍
- `ROADMAP.md` - 开发路线图
- `docs/configuration.md` - 配置说明

**产出**: [notes/01-architecture.md](notes/01-architecture.md)

#### Day 2: 架构解析
- [ ] 绘制整体架构图
- [ ] 理解核心组件职责
- [ ] 分析组件间依赖关系
- [ ] 了解数据流向

**关键文件**:
- `pkg/gateway/gateway.go` - 服务入口
- `pkg/bus/message_bus.go` - 消息总线
- `pkg/channels/manager.go` - 通道管理

**产出**: 架构图（diagrams/architecture.png）

#### Day 3-4: 核心组件深入

- [ ] **AgentLoop**: 执行循环
  - 主循环结构
  - 消息处理流程
  - 事件系统
  
- [ ] **AgentInstance**: Agent 实例
  - 初始化流程
  - 工具注册
  - 会话管理

- [ ] **ToolRegistry**: 工具注册与发现
  - 工具接口定义
  - 内置工具实现
  - 自定义工具扩展

**关键文件**:
- `pkg/agent/loop.go`
- `pkg/agent/instance.go`
- `pkg/agent/registry.go`
- `pkg/tools/registry.go`

**产出**: [notes/02-core-components.md](notes/02-core-components.md)

#### Day 5-7: 数据流分析

- [ ] **MessageBus**: 消息总线
  - Inbound 消息流
  - Outbound 消息流
  - 发布订阅机制

- [ ] **Channels**: 通道管理
  - 通道接口定义
  - 通道注册机制
  - 消息转换逻辑

- [ ] **Provider**: LLM 适配层
  - Provider 接口
  - 降级链实现
  - 限流机制

**关键文件**:
- `pkg/bus/`
- `pkg/channels/`
- `pkg/providers/`

**产出**: [notes/03-execution-flow.md](notes/03-execution-flow.md)

---

### 第二阶段：源码精读（Day 8-14）

#### Day 8-9: AgentLoop 源码分析

**重点文件**: `pkg/agent/loop.go`

**分析要点**:
- [ ] 主循环结构
  ```go
  func (al *AgentLoop) Run(ctx context.Context) error
  ```
- [ ] 消息处理
  ```go
  func (al *AgentLoop) processMessage(ctx, msg) (string, error)
  ```
- [ ] 工具执行循环
  ```go
  func (al *AgentLoop) RunToolLoop(ctx, turnState, agent) (string, error)
  ```
- [ ] 并发控制机制

**产出**: [src-analysis/agent-loop.md](src-analysis/agent-loop.md)

#### Day 10-11: AgentRegistry 源码分析

**重点文件**: `pkg/agent/registry.go`

**分析要点**:
- [ ] 多 Agent 管理
  ```go
  type AgentRegistry struct {
      agents   map[string]*AgentInstance
      resolver *routing.RouteResolver
  }
  ```
- [ ] 路由解析机制
- [ ] SubAgent 权限控制

**产出**: [src-analysis/agent-registry.md](src-analysis/agent-registry.md)

#### Day 12-14: Gateway 源码分析

**重点文件**: `pkg/gateway/gateway.go`

**分析要点**:
- [ ] 服务启动流程
  ```go
  func Run(debug bool, homePath, configPath string, allowEmptyStartup) error
  ```
- [ ] 配置热更新
  ```go
  func handleConfigReload(ctx, agentLoop, newCfg, provider, ...) error
  ```
- [ ] 服务管理
  - Cron 服务
  - Heartbeat 服务
  - 通道管理

**产出**: [src-analysis/gateway.md](src-analysis/gateway.md)

---

### 第三阶段：实践应用（Day 15-21）

#### Day 15-17: 自定义工具开发

**示例**: 自定义天气工具

```go
type WeatherTool struct {
    apiKey string
}

func (w *WeatherTool) Name() string { 
    return "weather" 
}

func (w *WeatherTool) Definition() tools.ToolDefinition {
    return tools.ToolDefinition{
        Name:        "weather",
        Description: "查询天气信息",
        Parameters:  jsonschema.Schema{...},
    }
}

func (w *WeatherTool) Execute(ctx context.Context, params map[string]any) (*tools.ToolResult, error) {
    // 实现逻辑
    city := params["city"].(string)
    // 调用天气 API...
    return &tools.ToolResult{
        Content: fmt.Sprintf("%s 的天气：晴，25°C", city),
        ForLLM:  "weather_result",
        ForUser: "今天天气晴朗，气温 25°C",
    }, nil
}
```

**实践任务**:
- [ ] 实现 3 个自定义工具
- [ ] 编写单元测试
- [ ] 集成到 PicoClaw

**产出**: [examples/custom-tool.go](examples/custom-tool.go)

#### Day 18-21: 多 Agent 协作

- [ ] 理解 SubAgent 架构
- [ ] 配置多 Agent 示例
- [ ] 测试协作效果

**产出**: [examples/multi-agent.md](examples/multi-agent.md)

---

## ✅ 检查清单

### 基础理解阶段
- [ ] 能清晰解释 PicoClaw 的定位
- [ ] 能画出完整架构图
- [ ] 能说明核心组件的职责
- [ ] 能描述一次完整请求的处理流程

### 源码精读阶段
- [ ] 能解释 AgentLoop 的循环逻辑
- [ ] 能说明工具调用的实现细节
- [ ] 能理解 Gateway 的路由机制
- [ ] 能分析关键数据结构

### 实践应用阶段
- [ ] 能独立编写自定义工具
- [ ] 能配置多 LLM 提供商
- [ ] 能部署到实际环境
- [ ] 能调试常见问题

---

## 📚 推荐资源

### 官方资源
- [PicoClaw GitHub](https://github.com/sipeed/picoclaw)
- [官方文档](https://mintlify.com/sipeed/picoclaw)
- [ROADMAP.md](https://github.com/sipeed/picoclaw/blob/main/ROADMAP.md)

### 补充阅读
- [Go 最佳实践](https://golang.org/doc/effective_go)
- [LLM Agent 架构论文](https://arxiv.org/abs/2308.11432)

---

## 📋 学习笔记索引

| 笔记 | 内容 | 状态 |
|------|------|------|
| [01-架构解析](notes/01-architecture.md) | 整体架构、设计理念 | ✅ 完成 |
| [02-核心组件](notes/02-core-components.md) | 核心模块详解 | ✅ 完成 |
| [03-执行流程](notes/03-execution-flow.md) | 消息处理、工具调用 | ✅ 完成 |

---

**开始学习吧！** 🚀

最后更新：2026-04-08  
基于版本：PicoClaw v1.x (GitHub main branch)
