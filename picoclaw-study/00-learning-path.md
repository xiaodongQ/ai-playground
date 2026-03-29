# PicoClaw 学习路径规划

> 🗺️ 从零到精通的系统化学习路线

---

## 📊 学习地图

```
Week 1: 基础理解                    Week 2: 源码精读
┌─────────────────────┐           ┌─────────────────────┐
│ Day 1-2: 架构概览    │           │ Day 8-9: AgentLoop  │
│ - 定位与特点         │           │ - 执行循环详解      │
│ - 核心组件           │           │ - 迭代控制          │
│ - 与 OpenClaw 对比   │           │ - 工具调用处理      │
├─────────────────────┤           ├─────────────────────┤
│ Day 3-4: 组件深入    │           │ Day 10-11: Gateway  │
│ - AgentInstance     │           │ - 多通道集成        │
│ - ToolRegistry      │           │ - 消息路由          │
│ - Provider 适配      │           │ - 认证与限流        │
├─────────────────────┤           ├─────────────────────┤
│ Day 5-7: 执行流程    │           │ Day 12-14: 扩展开发 │
│ - 消息处理链路       │           │ - 自定义工具        │
│ - 工具调用机制       │           │ - 新通道适配        │
│ - 状态管理          │           │ - 性能优化          │
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

**产出**: [notes/01-architecture.md](notes/01-architecture.md)

#### Day 2: 架构解析
- [ ] 绘制整体架构图
- [ ] 理解四大核心组件
- [ ] 分析组件间依赖关系
- [ ] 了解数据流向

**产出**: 架构图（diagrams/architecture.png）

#### Day 3-4: 核心组件深入
- [ ] **AgentInstance**: 会话生命周期管理
  - 初始化流程
  - 上下文维护
  - 资源清理
  
- [ ] **ToolRegistry**: 工具注册与发现
  - 接口定义
  - 注册机制
  - 执行调度

- [ ] **Provider**: LLM 提供商适配
  - 接口抽象
  - 多提供商支持
  - 配置管理

**产出**: [notes/02-core-components.md](notes/02-core-components.md)

#### Day 5-7: 执行流程
- [ ] **AgentLoop 执行循环**
  - 消息处理流程
  - LLM 调用逻辑
  - 工具调用解析
  - 结果合成

- [ ] **状态管理**
  - 会话状态持久化
  - 上下文窗口管理
  - 迭代次数控制

**产出**: [notes/03-execution-flow.md](notes/03-execution-flow.md)

---

### 第二阶段：源码精读（Day 8-14）

#### Day 8-9: AgentLoop 源码分析
```go
// 重点文件：pkg/agent/loop.go

// 1. 主循环结构
func (a *AgentLoop) Run(input Message) Response

// 2. LLM 调用逻辑
func (a *AgentLoop) callLLM(messages []Message) Response

// 3. 工具执行
func (a *AgentLoop) executeTools(toolCalls []ToolCall) []Result

// 4. 迭代控制
func (a *AgentLoop) shouldContinue() bool
```

**分析要点**:
- [ ] 循环终止条件
- [ ] 错误处理机制
- [ ] 性能优化点

**产出**: [src-analysis/agent-loop.md](src-analysis/agent-loop.md)

#### Day 10-11: AgentInstance 源码分析
```go
// 重点文件：pkg/agent/instance.go

// 1. 实例初始化
func NewAgentInstance(config Config) *AgentInstance

// 2. 上下文管理
func (a *AgentInstance) GetContext() Context

// 3. 生命周期
func (a *AgentInstance) Start()
func (a *AgentInstance) Stop()
```

**分析要点**:
- [ ] 资源管理
- [ ] 并发控制
- [ ] 状态机设计

**产出**: [src-analysis/agent-instance.md](src-analysis/agent-instance.md)

#### Day 12-14: Gateway 源码分析
```go
// 重点文件：cmd/gateway/main.go
//            pkg/gateway/server.go

// 1. 服务器启动
func StartGateway(config GatewayConfig)

// 2. 通道注册
func (g *Gateway) RegisterChannel(name string, handler ChannelHandler)

// 3. 消息路由
func (g *Gateway) routeMessage(msg Message)
```

**分析要点**:
- [ ] HTTP 服务器实现
- [ ] WebSocket 处理
- [ ] 认证与限流

**产出**: [src-analysis/gateway.md](src-analysis/gateway.md)

---

### 第三阶段：实践应用（Day 15-21）

#### Day 15-17: 自定义工具开发
```go
// 示例：自定义天气工具
type WeatherTool struct {
    apiKey string
}

func (w *WeatherTool) Name() string { return "weather" }

func (w *WeatherTool) Execute(ctx Context, params map[string]any) (Result, error) {
    // 实现逻辑
}
```

**实践任务**:
- [ ] 实现 3 个自定义工具
- [ ] 编写单元测试
- [ ] 集成到 PicoClaw

**产出**: [examples/custom-tool.go](examples/custom-tool.go)

#### Day 18-21: 多 Agent 协作
- [ ] 理解 Agent Teams 架构
- [ ] 实现简单多 Agent 示例
- [ ] 测试协作效果

**产出**: [examples/multi-agent.md](examples/multi-agent.md)

---

### 第四阶段：扩展开发（可选）

#### 新通道适配
- [ ] 学习现有通道实现（Telegram/Discord）
- [ ] 适配新通道（如飞书）
- [ ] 提交 PR

#### 性能优化
- [ ] 性能分析（pprof）
- [ ] 识别瓶颈
- [ ] 优化实现

#### 文档贡献
- [ ] 补充中文文档
- [ ] 添加示例代码
- [ ] 修复文档错误

---

## 📝 学习方法建议

### 1. 代码阅读技巧
```bash
# 使用工具辅助
go doc pkg/agent/loop.go        # 查看文档
go test -v ./pkg/agent/...      # 运行测试
go build -o picoclaw .          # 编译验证
```

### 2. 调试技巧
```bash
# 启用详细日志
export PICOCLAW_LOG_LEVEL=debug
picoclaw gateway --debug

# 使用 delve 调试
dlv debug ./cmd/gateway
```

### 3. 笔记记录
- 每个模块创建一个笔记文件
- 记录关键代码片段
- 绘制流程图辅助理解
- 记录疑问和发现

---

## ✅ 检查清单

### 基础理解阶段
- [ ] 能清晰解释 PicoClaw 的定位
- [ ] 能画出完整架构图
- [ ] 能说明四大组件的职责
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
- [OpenClaw 架构对比](references/comparisons.md)

---

**开始学习吧！** 🚀

最后更新：2026-03-29
