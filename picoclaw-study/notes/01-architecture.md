# PicoClaw 架构解析

> 📌 基于实际源码的架构分析（2026 年版本）

---

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Telegram │ │Discord  │ │ Feishu  │ │ Slack   │ │ 更多... │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
└───────┼──────────┼──────────┼──────────┼──────────┼────────────┘
        │          │          │          │          │
        └──────────┴────┬─────┴──────────┴──────────┘
                        │
        ┌───────────────▼───────────────┐
        │      channels.Manager         │  ← 通道管理
        │   (统一消息抽象层)             │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼───────────────┐
        │         bus.MessageBus        │  ← 消息总线
        │    ( inbound / outbound )     │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼───────────────┐
        │        agent.AgentLoop        │  ← 核心执行循环
        │  ┌─────────────────────────┐  │
        │  │   AgentRegistry         │  │  ← 多 Agent 管理
        │  │  ┌───────────────────┐  │  │
        │  │  │ AgentInstance     │  │  │  ← 单个 Agent 实例
        │  │  │ - Tools           │  │  │
        │  │  │ - Sessions        │  │  │
        │  │  │ - ContextBuilder  │  │  │
        │  │  └───────────────────┘  │  │
        │  └─────────────────────────┘  │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼───────────────┐
        │      providers.LLMProvider    │  ← LLM 提供商适配
        │   (OpenAI / Claude / Ollama)  │
        └───────────────────────────────┘
```

---

## 📦 核心组件

### 1. Gateway (`pkg/gateway/gateway.go`)

Gateway 是 PicoClaw 的入口服务，负责：
- 配置加载与热更新
- 服务启动与关闭
- Agent 生命周期管理

**关键函数：**
```go
// 启动 Gateway
func Run(debug bool, homePath, configPath string, allowEmptyStartup bool) error

// 设置服务
func setupAndStartServices(cfg, agentLoop, msgBus, authToken) (*services, error)

// 配置热更新
func handleConfigReload(ctx, agentLoop, newCfg, provider, runningServices, msgBus) error
```

**启动流程：**
1. 加载配置文件
2. 创建 LLM Provider
3. 初始化 AgentLoop
4. 启动通道服务（Telegram、Discord 等）
5. 启动辅助服务（Cron、Heartbeat、Device）
6. 进入事件循环等待信号

---

### 2. MessageBus (`pkg/bus/`)

消息总线是内部通信的核心：

```go
type MessageBus interface {
    InboundChan() <-chan InboundMessage   // 接收外部消息
    OutboundChan() <-chan OutboundMessage // 发送响应消息
    PublishInbound(ctx, InboundMessage)   // 发布入站消息
    PublishOutbound(ctx, OutboundMessage) // 发布出站消息
}
```

**消息流向：**
```
外部平台 → Channel → MessageBus.Inbound → AgentLoop → LLM
                                                    ↓
外部平台 ← Channel ← MessageBus.Outbound ← AgentLoop ← Tool
```

---

### 3. Channels (`pkg/channels/`)

通道管理器统一处理不同平台的接入：

**支持的通道：**
- 即时通讯：Telegram、Discord、Slack、WhatsApp
- 国内平台：飞书、钉钉、企业微信、QQ
- 其他：IRC、Matrix、Line、VK

**通道接口：**
```go
type Channel interface {
    Start(ctx context.Context) error
    Stop(ctx context.Context) error
    Send(ctx, chatID, content string) error
}

// 可选能力
type ReactionCapable interface {
    ReactToMessage(ctx, chatID, messageID string) (string, error)
}
```

**管理器：**
```go
// pkg/channels/manager.go
type Manager struct {
    channels map[string]Channel
    msgBus   *bus.MessageBus
}

func (m *Manager) StartAll(ctx) error
func (m *Manager) StopAll(ctx) error
func (m *Manager) GetChannel(name string) (Channel, bool)
```

---

### 4. AgentLoop (`pkg/agent/loop.go`)

核心执行循环，处理 AI 对话的完整流程：

**数据结构：**
```go
type AgentLoop struct {
    // 核心依赖
    bus      *bus.MessageBus
    cfg      *config.Config
    registry *AgentRegistry
    state    *state.Manager
    
    // 事件系统
    eventBus *EventBus
    hooks    *HookManager
    
    // 运行时状态
    running        atomic.Bool
    contextManager ContextManager
    fallback       *providers.FallbackChain
    channelManager *channels.Manager
    mediaStore     media.MediaStore
}
```

**主循环：**
```go
func (al *AgentLoop) Run(ctx context.Context) error {
    al.running.Store(true)
    
    for {
        select {
        case <-ctx.Done():
            return nil
        case msg, ok := <-al.bus.InboundChan():
            // 处理入站消息
            response, err := al.processMessage(ctx, msg)
            // 发布响应
            al.PublishResponseIfNeeded(ctx, channel, chatID, response)
        }
    }
}
```

**消息处理流程：**
1. 接收消息 → 2. 解析会话 → 3. 构建上下文 → 4. 调用 LLM → 5. 执行工具 → 6. 返回结果

---

### 5. AgentRegistry (`pkg/agent/registry.go`)

多 Agent 管理器：

```go
type AgentRegistry struct {
    agents   map[string]*AgentInstance  // Agent 实例映射
    resolver *routing.RouteResolver    // 路由解析器
    mu       sync.RWMutex
}

func (r *AgentRegistry) GetAgent(agentID string) (*AgentInstance, bool)
func (r *AgentRegistry) ListAgentIDs() []string
func (r *AgentRegistry) CanSpawnSubagent(parent, target string) bool
```

**功能：**
- 从配置创建多个 Agent 实例
- 消息路由到正确的 Agent
- 管理 SubAgent 生成权限

---

### 6. AgentInstance (`pkg/agent/instance.go`)

单个 Agent 的完整配置：

```go
type AgentInstance struct {
    ID            string
    Model         string
    Workspace     string
    MaxIterations int
    MaxTokens     int
    Temperature   float64
    
    Provider      providers.LLMProvider
    Sessions      session.SessionStore
    ContextBuilder *ContextBuilder
    Tools         *tools.ToolRegistry
    
    // 模型路由
    Router          *routing.Router
    LightCandidates []providers.FallbackCandidate
}
```

**工具注册：**
- 文件操作：`read_file`, `write_file`, `edit_file`, `list_dir`
- 系统操作：`exec`
- 网络操作：`web`, `web_fetch`
- 通讯操作：`message`, `send_file`, `reaction`
- 扩展功能：`spawn`, `skills`, `cron`

---

## 🔄 数据流

### 完整请求处理流程

```
1. 用户发送消息 (Telegram)
       ↓
2. Telegram Channel 接收
       ↓
3. 转换为统一格式 (providers.Message)
       ↓
4. 发布到 MessageBus.Inbound
       ↓
5. AgentLoop 接收消息
       ↓
6. 解析路由 (哪个 Agent 处理)
       ↓
7. 加载会话历史 (SessionStore)
       ↓
8. 构建上下文 (ContextBuilder)
       ↓
9. 调用 LLM Provider
       ↓
10. 解析响应（文本 or 工具调用）
       ↓
    ┌──────────────┴──────────────┐
    │                             │
    ↓                             ↓
11a. 文本响应                  11b. 工具调用
    │                             │
    │                    ┌────────┴────────┐
    │                    │                 │
    │                    ↓                 ↓
    │             执行工具           并行执行多工具
    │                    │                 │
    │                    └────────┬────────┘
    │                             │
    │                    ┌────────▼────────┐
    │                    │   结果收集      │
    │                    └────────┬────────┘
    │                             │
    └──────────────┬──────────────┘
                   │
12. 合成最终响应 ←─┘
       ↓
13. 发布到 MessageBus.Outbound
       ↓
14. Channel 发送回用户
```

---

## 📁 目录结构

```
picoclaw/
├── cmd/
│   ├── picoclaw/                    # 主程序入口
│   │   └── internal/
│   │       ├── agent/               # Agent 命令
│   │       ├── gateway/             # Gateway 命令
│   │       ├── auth/                # 认证命令
│   │       ├── skills/              # 技能管理
│   │       └── cron/                # 定时任务
│   └── picoclaw-launcher-tui/       # TUI 启动器
│
├── pkg/
│   ├── agent/                       # 核心 Agent 逻辑
│   │   ├── loop.go                  # 主循环
│   │   ├── instance.go              # Agent 实例
│   │   ├── registry.go              # Agent 注册表
│   │   ├── context.go               # 上下文管理
│   │   ├── tools.go                 # 工具执行
│   │   └── events.go                # 事件系统
│   │
│   ├── channels/                    # 通道实现
│   │   ├── manager.go               # 通道管理
│   │   ├── base.go                  # 基础通道
│   │   ├── telegram/                # Telegram
│   │   ├── discord/                 # Discord
│   │   ├── feishu/                  # 飞书
│   │   └── ...                      # 其他通道
│   │
│   ├── providers/                   # LLM 提供商
│   │   ├── interface.go             # Provider 接口
│   │   ├── openai/                  # OpenAI
│   │   ├── ollama/                  # Ollama
│   │   └── fallback.go              # 降级链
│   │
│   ├── tools/                       # 工具实现
│   │   ├── registry.go              # 工具注册
│   │   ├── file.go                  # 文件工具
│   │   ├── web.go                   # 网络工具
│   │   ├── exec.go                  # 执行工具
│   │   └── spawn.go                 # 子 Agent 工具
│   │
│   ├── gateway/                     # Gateway 服务
│   │   ├── gateway.go               # 主服务
│   │   └── channel_matrix.go        # 通道矩阵
│   │
│   ├── bus/                         # 消息总线
│   ├── config/                      # 配置管理
│   ├── session/                     # 会话存储
│   ├── memory/                      # 记忆管理
│   ├── state/                       # 状态管理
│   ├── media/                       # 媒体文件
│   └── logger/                      # 日志系统
│
├── docs/                            # 文档
├── examples/                        # 示例
└── web/                             # Web UI
```

---

## 🎯 设计特点

### 1. 超轻量设计
- 单一二进制文件
- 无外部依赖（除 LLM API）
- 内存占用低（适合边缘设备）

### 2. 模块化架构
- 通道插件化（import _ 自动注册）
- 工具可扩展
- 多 Agent 支持

### 3. 高可用性
- 配置热更新（无需重启）
- 优雅关闭
- 多 Provider 降级链

### 4. 安全性
- 工作空间限制
- 路径白名单
- 敏感信息加密

---

## 📊 与 OpenClaw 对比

| 特性 | PicoClaw | OpenClaw |
|------|----------|----------|
| 定位 | 嵌入式/边缘设备 | 企业级应用 |
| 语言 | Go | Python |
| 部署 | 单二进制 | Docker/源码 |
| 多 Agent | 支持（SubAgent） | 完整 Teams |
| 通道 | 20+ | 10+ |
| 内存占用 | ~50MB | ~200MB+ |

---

**最后更新**: 2026-04-08  
**基于版本**: PicoClaw v1.x (GitHub main branch)