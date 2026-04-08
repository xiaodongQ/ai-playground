# PicoClaw 核心组件分析

> 📌 深入解析 PicoClaw 的核心模块实现

---

## 目录

1. [AgentLoop - 执行循环](#1-agentloop---执行循环)
2. [AgentInstance - Agent 实例](#2-agentinstance---agent 实例)
3. [ToolRegistry - 工具注册](#3-toolregistry---工具注册)
4. [Provider - LLM 适配](#4-provider---llm 适配)
5. [ContextManager - 上下文管理](#5-contextmanager---上下文管理)
6. [SessionStore - 会话存储](#6-sessionstore---会话存储)

---

## 1. AgentLoop - 执行循环

### 1.1 核心结构

```go
// pkg/agent/loop.go
type AgentLoop struct {
    // 核心依赖
    bus      *bus.MessageBus         // 消息总线
    cfg      *config.Config          // 配置
    registry *AgentRegistry          // Agent 注册表
    state    *state.Manager          // 状态管理

    // 事件系统
    eventBus *EventBus               // 事件总线
    hooks    *HookManager            // Hook 管理

    // 运行时状态
    running        atomic.Bool
    contextManager ContextManager
    fallback       *providers.FallbackChain  // 降级链
    channelManager *channels.Manager         // 通道管理
    mediaStore     media.MediaStore          // 媒体存储
    
    // 并发控制
    activeTurnStates sync.Map     // 活跃 Turn 状态
    subTurnCounter   atomic.Int64 // SubTurn 计数器
}
```

### 1.2 初始化流程

```go
func NewAgentLoop(
    cfg *config.Config,
    msgBus *bus.MessageBus,
    provider providers.LLMProvider,
) *AgentLoop {
    // 1. 创建 Agent Registry
    registry := NewAgentRegistry(cfg, provider)
    
    // 2. 设置降级链（带限流）
    cooldown := providers.NewCooldownTracker()
    rl := providers.NewRateLimiterRegistry()
    fallbackChain := providers.NewFallbackChain(cooldown, rl)
    
    // 3. 创建状态管理
    stateManager := state.NewManager(defaultAgent.Workspace)
    
    // 4. 创建事件总线
    eventBus := NewEventBus()
    
    // 5. 初始化 Loop
    al := &AgentLoop{
        bus:         msgBus,
        cfg:         cfg,
        registry:    registry,
        state:       stateManager,
        eventBus:    eventBus,
        fallback:    fallbackChain,
        steering:    newSteeringQueue(cfg.Agents.Defaults.SteeringMode),
    }
    
    // 6. 注册共享工具（web, message, spawn 等）
    registerSharedTools(al, cfg, msgBus, registry, provider)
    
    return al
}
```

### 1.3 主循环实现

```go
func (al *AgentLoop) Run(ctx context.Context) error {
    al.running.Store(true)
    
    // 初始化 Hook 和 MCP
    if err := al.ensureHooksInitialized(ctx); err != nil {
        return err
    }
    
    idleTicker := time.NewTicker(100 * time.Millisecond)
    defer idleTicker.Stop()
    
    for {
        select {
        case <-ctx.Done():
            return nil
        case <-idleTicker.C:
            if !al.running.Load() {
                return nil
            }
        case msg, ok := <-al.bus.InboundChan():
            if !ok {
                return nil
            }
            
            // 处理消息（在 goroutine 中）
            go func() {
                defer al.channelManager.InvokeTypingStop(msg.Channel, msg.ChatID)
                
                response, err := al.processMessage(ctx, msg)
                if err != nil {
                    response = fmt.Sprintf("Error: %v", err)
                }
                
                // 发布响应
                al.PublishResponseIfNeeded(ctx, msg.Channel, msg.ChatID, response)
            }()
        }
    }
}
```

### 1.4 消息处理流程

```go
func (al *AgentLoop) processMessage(ctx context.Context, msg bus.InboundMessage) (string, error) {
    // 1. 解析路由
    route, agentID, err := al.resolveMessageRoute(msg)
    if err != nil {
        return "", err
    }
    
    // 2. 获取 Agent
    agent, ok := al.registry.GetAgent(agentID)
    if !ok {
        return "", fmt.Errorf("agent not found")
    }
    
    // 3. 创建 Turn State
    turnState := al.createTurnState(ctx, agent, msg)
    
    // 4. 进入执行循环
    return al.RunToolLoop(ctx, turnState, agent)
}
```

### 1.5 工具执行循环

```go
// RunToolLoop 执行工具调用循环
func (al *AgentLoop) RunToolLoop(ctx context.Context, ts *turnState, agent *AgentInstance) (string, error) {
    var finalResponse string
    var lastErr error
    
    for iteration := 0; iteration < agent.MaxIterations; iteration++ {
        // 1. 构建上下文
        messages, err := agent.ContextBuilder.Build(ctx, ts.session)
        if err != nil {
            return "", err
        }
        
        // 2. 调用 LLM
        response, err := al.callLLM(ctx, agent, messages, agent.Tools)
        if err != nil {
            lastErr = err
            continue
        }
        
        // 3. 处理响应
        if response.Content != "" {
            finalResponse = response.Content
        }
        
        // 4. 执行工具调用
        if len(response.ToolCalls) > 0 {
            results := al.executeTools(ctx, ts, response.ToolCalls)
            
            // 将结果添加到上下文
            for _, result := range results {
                ts.session.AddToolResult(result)
            }
            continue
        }
        
        // 5. 有最终响应，退出循环
        if finalResponse != "" {
            break
        }
    }
    
    return finalResponse, lastErr
}
```

---

## 2. AgentInstance - Agent 实例

### 2.1 结构定义

```go
// pkg/agent/instance.go
type AgentInstance struct {
    // 基础配置
    ID            string
    Name          string
    Model         string
    Fallbacks     []string
    
    // 工作空间
    Workspace     string
    
    // 执行限制
    MaxIterations int
    MaxTokens     int
    Temperature   float64
    ThinkingLevel ThinkingLevel
    
    // 上下文管理
    ContextWindow             int
    SummarizeMessageThreshold int
    SummarizeTokenPercent     int
    
    // 核心组件
    Provider       providers.LLMProvider
    Sessions       session.SessionStore
    ContextBuilder *ContextBuilder
    Tools          *tools.ToolRegistry
    
    // 模型路由
    Router          *routing.Router
    LightCandidates []providers.FallbackCandidate
}
```

### 2.2 初始化

```go
func NewAgentInstance(
    agentCfg *config.AgentConfig,
    defaults *config.AgentDefaults,
    cfg *config.Config,
    provider providers.LLMProvider,
) *AgentInstance {
    // 1. 解析工作空间
    workspace := resolveAgentWorkspace(agentCfg, defaults)
    os.MkdirAll(workspace, 0o755)
    
    // 2. 解析模型配置
    model := resolveAgentModel(agentCfg, defaults)
    fallbacks := resolveAgentFallbacks(agentCfg, defaults)
    
    // 3. 创建工具注册表
    toolsRegistry := tools.NewToolRegistry()
    
    // 4. 注册文件操作工具
    if cfg.Tools.IsToolEnabled("read_file") {
        toolsRegistry.Register(tools.NewReadFileTool(...))
    }
    if cfg.Tools.IsToolEnabled("write_file") {
        toolsRegistry.Register(tools.NewWriteFileTool(...))
    }
    if cfg.Tools.IsToolEnabled("exec") {
        toolsRegistry.Register(tools.NewExecTool(...))
    }
    
    // 5. 创建会话存储
    sessionsDir := filepath.Join(workspace, "sessions")
    sessions := initSessionStore(sessionsDir)
    
    // 6. 创建上下文构建器
    contextBuilder := NewContextBuilder(workspace).
        WithToolDiscovery(...).
        WithSplitOnMarker(cfg.Agents.Defaults.SplitOnMarker)
    
    // 7. 模型路由设置
    var router *routing.Router
    var lightCandidates []providers.FallbackCandidate
    if rc := defaults.Routing; rc != nil && rc.Enabled {
        router = routing.New(routing.RouterConfig{
            LightModel: rc.LightModel,
            Threshold:  rc.Threshold,
        })
    }
    
    return &AgentInstance{
        ID:            agentID,
        Model:         model,
        Workspace:     workspace,
        MaxIterations: defaults.MaxToolIterations,
        MaxTokens:     defaults.MaxTokens,
        Provider:      provider,
        Sessions:      sessions,
        ContextBuilder: contextBuilder,
        Tools:         toolsRegistry,
        Router:        router,
    }
}
```

---

## 3. ToolRegistry - 工具注册

### 3.1 工具接口

```go
// pkg/tools/registry.go
type Tool interface {
    Name() string
    Definition() ToolDefinition
    Execute(ctx context.Context, params map[string]any) (*ToolResult, error)
}

type ToolDefinition struct {
    Name        string         `json:"name"`
    Description string         `json:"description"`
    Parameters  jsonschema.Schema `json:"parameters"`
}

type ToolResult struct {
    Content    string
    IsError    bool
    ForLLM     string  // 给 LLM 看的结果
    ForUser    string  // 给用户看的结果
}
```

### 3.2 注册表实现

```go
type ToolRegistry struct {
    tools map[string]Tool
    mu    sync.RWMutex
}

func (r *ToolRegistry) Register(tool Tool) {
    r.mu.Lock()
    defer r.mu.Unlock()
    r.tools[tool.Name()] = tool
}

func (r *ToolRegistry) Get(name string) (Tool, bool) {
    r.mu.RLock()
    defer r.mu.RUnlock()
    tool, ok := r.tools[name]
    return tool, ok
}

func (r *ToolRegistry) List() []string {
    r.mu.RLock()
    defer r.mu.RUnlock()
    names := make([]string, 0, len(r.tools))
    for name := range r.tools {
        names = append(names, name)
    }
    return names
}
```

### 3.3 内置工具

| 工具名 | 功能 | 文件 |
|--------|------|------|
| `read_file` | 读取文件内容 | `tools/file.go` |
| `write_file` | 写入文件 | `tools/file.go` |
| `edit_file` | 编辑文件（diff） | `tools/file.go` |
| `list_dir` | 列出目录 | `tools/file.go` |
| `exec` | 执行 shell 命令 | `tools/exec.go` |
| `web` | 网络搜索 | `tools/web.go` |
| `web_fetch` | 抓取网页内容 | `tools/web.go` |
| `message` | 发送消息 | `tools/message.go` |
| `send_file` | 发送文件 | `tools/media.go` |
| `spawn` | 生成子 Agent | `tools/spawn.go` |
| `skills` | 技能管理 | `tools/skills.go` |

---

## 4. Provider - LLM 适配

### 4.1 Provider 接口

```go
// pkg/providers/interface.go
type LLMProvider interface {
    Chat(
        ctx context.Context,
        messages []Message,
        tools []ToolDefinition,
        model string,
        options map[string]any,
    ) (*LLMResponse, error)
    
    GetDefaultModel() string
}

type LLMResponse struct {
    Content   string
    ToolCalls []ToolCall
    Usage     TokenUsage
}

type ToolCall struct {
    ID       string
    Name     string
    Arguments map[string]any
}
```

### 4.2 支持的 Provider

```
pkg/providers/
├── interface.go           # 接口定义
├── fallback.go            # 降级链
├── openai/                # OpenAI 兼容
│   ├── provider.go
│   └── chat.go
├── ollama/                # Ollama
│   └── provider.go
├── anthropic/             # Claude
│   └── provider.go
└── ...                    # 其他
```

### 4.3 降级链

```go
// pkg/providers/fallback.go
type FallbackChain struct {
    candidates []FallbackCandidate
    cooldown   *CooldownTracker
    rateLimiter *RateLimiterRegistry
}

type FallbackCandidate struct {
    Model     string
    Provider  string
    Priority  int
}

func (f *FallbackChain) Chat(ctx context.Context, messages, tools) (*LLMResponse, error) {
    var lastErr error
    
    for _, candidate := range f.candidates {
        // 检查限流
        if f.rateLimiter.IsRateLimited(candidate) {
            continue
        }
        
        // 尝试调用
        response, err := f.callCandidate(ctx, candidate, messages, tools)
        if err == nil {
            return response, nil
        }
        
        lastErr = err
        f.cooldown.MarkFailed(candidate)
    }
    
    return nil, lastErr
}
```

---

## 5. ContextManager - 上下文管理

### 5.1 上下文构建器

```go
// pkg/agent/context.go
type ContextBuilder struct {
    workspace string
    toolDiscovery bool
    splitOnMarker bool
}

func (b *ContextBuilder) Build(ctx context.Context, session Session) ([]Message, error) {
    var messages []Message
    
    // 1. 系统提示词
    systemPrompt := b.buildSystemPrompt()
    messages = append(messages, Message{Role: "system", Content: systemPrompt})
    
    // 2. 会话历史
    history, err := session.GetHistory()
    if err != nil {
        return nil, err
    }
    messages = append(messages, history...)
    
    // 3. 上下文压缩（如果超出限制）
    if len(messages) > b.maxContextLength {
        messages = b.compress(messages)
    }
    
    return messages, nil
}
```

### 5.2 上下文压缩策略

```go
func (b *ContextBuilder) compress(messages []Message) []Message {
    // 1. 保留系统提示词
    result := []Message{messages[0]}
    
    // 2. 保留最近的 N 条消息
    keepCount := b.calculateKeepCount()
    if len(messages) > keepCount {
        result = append(result, messages[len(messages)-keepCount:]...)
    } else {
        result = append(result, messages[1:]...)
    }
    
    return result
}
```

---

## 6. SessionStore - 会话存储

### 6.1 会话接口

```go
// pkg/session/store.go
type SessionStore interface {
    Get(sessionKey string) (*Session, error)
    Save(sessionKey string, session *Session) error
    Delete(sessionKey string) error
    List() ([]string, error)
    Close() error
}
```

### 6.2 JSONL 存储实现

```go
// pkg/memory/jsonl.go
type JSONLStore struct {
    dir      string
    sessions map[string]*Session
    mu       sync.Mutex
    file     *os.File
}

func (s *JSONLStore) Save(key string, session *Session) error {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    // 追加到 JSONL 文件
    data, _ := json.Marshal(session)
    s.file.Write(data)
    s.file.Write([]byte("\n"))
    
    s.sessions[key] = session
    return nil
}
```

---

## 🔗 组件关系图

```
┌─────────────────────────────────────────────────────────┐
│                    Gateway                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │                  AgentLoop                          │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  │ AgentRegistry│──│ AgentInstance│  │ Tools     │ │
│  │  │              │  │              │  │ Registry  │ │
│  │  └──────────────┘  └──────┬───────┘  └───────────┘ │
│  │                           │                         │
│  │  ┌──────────────┐  ┌──────▼───────┐  ┌───────────┐ │
│  │  │ EventBus     │  │ ContextBuilder│ │ Provider  │ │
│  │  └──────────────┘  └──────────────┘  └───────────┘ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│ MessageBus      │          │ LLM API         │
│ - Inbound       │          │ - OpenAI        │
│ - Outbound      │          │ - Claude        │
└────────┬────────┘          │ - Ollama        │
         │                   └─────────────────┘
         ▼
┌─────────────────┐
│ Channels        │
│ - Telegram      │
│ - Discord       │
│ - Feishu        │
│ - ...           │
└─────────────────┘
```

---

**最后更新**: 2026-04-08  
**基于版本**: PicoClaw v1.x