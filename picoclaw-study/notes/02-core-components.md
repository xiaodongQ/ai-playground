# PicoClaw 核心组件详解

> 🔧 深入分析四大核心模块的实现细节

**学习时间**: 2026-03-29  
**参考源码**: `pkg/agent/`, `pkg/tools/`, `cmd/gateway/`

---

## 1. AgentInstance - 会话管理

### 职责
- 维护单个用户会话的完整生命周期
- 管理消息历史和上下文
- 协调 AgentLoop 执行

### 核心结构

```go
// pkg/agent/instance.go
type AgentInstance struct {
    // 基础信息
    ID        string            // 唯一会话 ID
    ChannelID string            // 通道 ID (telegram/discord/slack)
    UserID    string            // 用户 ID
    
    // 核心组件
    Config    AgentConfig       // 配置
    Loop      *AgentLoop        // 执行引擎
    Tools     *ToolRegistry     // 工具注册表
    
    // 状态管理
    Context   Context           // 执行上下文
    State     InstanceState     // 实例状态 (active/paused/closed)
    
    // 消息历史
    Messages  []Message         // 对话历史
    MaxTokens int               // 最大 token 数
    
    // 资源
    mu        sync.RWMutex      // 并发锁
    createdAt time.Time         // 创建时间
    lastActive time.Time        // 最后活跃时间
}

// 配置结构
type AgentConfig struct {
    Model            string            // LLM 模型
    Temperature      float64           // 温度参数
    MaxIterations    int               // 最大迭代次数
    MaxTokens        int               // 最大输出 token
    SystemPrompt     string            // 系统提示词
    ToolContext      map[string]any    // 工具上下文 (channel/chatID 等)
}
```

### 关键方法

#### 1.1 创建实例

```go
func NewAgentInstance(config AgentConfig) *AgentInstance {
    return &AgentInstance{
        ID:        generateID(),
        Config:    config,
        Loop:      NewAgentLoop(config),
        Tools:     NewToolRegistry(),
        Context:   NewContext(),
        State:     StateActive,
        Messages:  make([]Message, 0),
        createdAt: time.Now(),
        lastActive: time.Now(),
    }
}

// 注册内置工具
func (a *AgentInstance) SetupDefaultTools() {
    a.Tools.Register(&SearchTool{})
    a.Tools.Register(&FileReadTool{})
    a.Tools.Register(&FileWriteTool{})
    a.Tools.Register(&ShellTool{})
    a.Tools.Register(&HTTPRequestTool{})
}
```

#### 1.2 处理消息

```go
func (a *AgentInstance) ProcessMessage(input Message) (Response, error) {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    // 1. 添加用户消息到历史
    a.Messages = append(a.Messages, input)
    a.lastActive = time.Now()
    
    // 2. 裁剪消息历史（防止超出 token 限制）
    a.trimMessages()
    
    // 3. 调用 AgentLoop 执行
    response, err := a.Loop.Run(a.Context, a.Messages)
    if err != nil {
        return Response{}, err
    }
    
    // 4. 添加助手响应到历史
    a.Messages = append(a.Messages, response.ToMessage())
    
    return response, nil
}
```

#### 1.3 消息裁剪

```go
func (a *AgentInstance) trimMessages() {
    // 策略：保留最近的 N 条消息，确保不超过 token 限制
    for len(a.Messages) > 2 && a.estimateTokens() > a.MaxTokens {
        // 移除最早的非系统消息
        a.Messages = a.Messages[1:]
    }
}

func (a *AgentInstance) estimateTokens() int {
    // 简单估算：每 4 个字符 ≈ 1 token
    total := 0
    for _, msg := range a.Messages {
        total += len(msg.Content) / 4
    }
    return total
}
```

#### 1.4 资源清理

```go
func (a *AgentInstance) Close() error {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    a.State = StateClosed
    
    // 清理工具资源
    for _, tool := range a.Tools.All() {
        if closer, ok := tool.(io.Closer); ok {
            closer.Close()
        }
    }
    
    // 清空消息历史
    a.Messages = nil
    a.Context = nil
    
    return nil
}
```

### 状态机

```
┌─────────────┐
│   Created   │
└──────┬──────┘
       │ Start()
       ▼
┌─────────────┐
│   Active    │◄────┐
└──────┬──────┘     │
       │            │ ProcessMessage()
       │ Pause()    │
       ▼            │
┌─────────────┐     │
│   Paused    │─────┘
└──────┬──────┘   Resume()
       │
       │ Close()
       ▼
┌─────────────┐
│   Closed    │ (终态)
└─────────────┘
```

---

## 2. AgentLoop - 执行引擎

### 职责
- 执行 LLM 调用循环
- 解析和调度工具调用
- 控制迭代次数

### 核心结构

```go
// pkg/agent/loop.go
type AgentLoop struct {
    // 依赖
    LLM           LLMProvider      // LLM 提供商接口
    Tools         *ToolRegistry    // 工具注册表
    
    // 配置
    MaxIterations int              // 最大迭代次数
    MaxTokens     int              // 最大输出 token
    Model         string           // 模型名称
    
    // 运行时
    currentIteration int           // 当前迭代次数
}

// LLM 提供商接口
type LLMProvider interface {
    Call(ctx Context, messages []Message, tools []ToolDef) (Response, error)
    Name() string
}
```

### 核心方法

#### 2.1 主循环

```go
func (a *AgentLoop) Run(ctx Context, messages []Message) (Response, error) {
    a.currentIteration = 0
    
    // 创建消息副本（避免修改原始数据）
    workingMessages := make([]Message, len(messages))
    copy(workingMessages, messages)
    
    for a.currentIteration < a.MaxIterations {
        a.currentIteration++
        
        // 1. 调用 LLM
        response, err := a.LLM.Call(ctx, workingMessages, a.Tools.Definitions())
        if err != nil {
            return Response{}, fmt.Errorf("LLM call failed: %w", err)
        }
        
        // 2. 检查是否有工具调用
        if len(response.ToolCalls) == 0 {
            // 没有工具调用，返回最终答案
            return response, nil
        }
        
        // 3. 执行所有工具调用
        for _, toolCall := range response.ToolCalls {
            // 3.1 查找工具
            tool := a.Tools.Get(toolCall.Name)
            if tool == nil {
                return Response{}, fmt.Errorf("tool not found: %s", toolCall.Name)
            }
            
            // 3.2 执行工具
            result, err := tool.Execute(ctx, toolCall.Parameters)
            if err != nil {
                return Response{}, fmt.Errorf("tool execution failed: %w", err)
            }
            
            // 3.3 添加结果到消息历史
            workingMessages = append(workingMessages, result.ToMessage())
        }
    }
    
    // 达到最大迭代次数
    return Response{
        Content: "I reached the maximum number of iterations.",
        Error:   ErrMaxIterations,
    }, nil
}
```

#### 2.2 流式处理（可选）

```go
func (a *AgentLoop) RunStream(ctx Context, messages []Message) (<-chan StreamEvent, error) {
    eventChan := make(chan StreamEvent, 10)
    
    go func() {
        defer close(eventChan)
        
        // 发送开始事件
        eventChan <- StreamEvent{Type: EventStart}
        
        for a.currentIteration < a.MaxIterations {
            // 发送迭代开始事件
            eventChan <- StreamEvent{
                Type: EventIterationStart,
                Iteration: a.currentIteration,
            }
            
            // ... 执行逻辑 ...
            
            // 发送工具执行事件
            eventChan <- StreamEvent{
                Type: EventToolCall,
                ToolName: toolCall.Name,
                Parameters: toolCall.Parameters,
            }
        }
        
        // 发送结束事件
        eventChan <- StreamEvent{Type: EventEnd}
    }()
    
    return eventChan, nil
}

// 流式事件类型
type StreamEventType int

const (
    EventStart StreamEventType = iota
    EventIterationStart
    EventLLMCall
    EventToolCall
    EventToolResult
    EventEnd
)

type StreamEvent struct {
    Type     StreamEventType
    Iteration int
    ToolName string
    Content  string
}
```

---

## 3. ToolRegistry - 工具管理

### 职责
- 工具的注册和发现
- 生成 LLM 工具定义
- 执行工具调用

### 核心结构

```go
// pkg/tools/registry.go
type ToolRegistry struct {
    mu    sync.RWMutex          // 并发控制
    tools map[string]Tool       // 工具映射：name -> Tool
}

// 工具接口
type Tool interface {
    Name() string                                    // 工具名称
    Description() string                             // 工具描述
    Parameters() map[string]ParameterSchema          // 参数定义
    Execute(ctx Context, params map[string]any) (Result, error)
}

// 参数 schema
type ParameterSchema struct {
    Type        string   // string/number/boolean/array/object
    Description string   // 参数描述
    Required    bool     // 是否必填
    Enum        []string // 枚举值（可选）
    Default     any      // 默认值（可选）
}

// 工具定义（发送给 LLM 的格式）
type ToolDef struct {
    Name        string                 `json:"name"`
    Description string                 `json:"description"`
    Parameters  map[string]ParameterSchema `json:"parameters"`
}

// 工具调用（LLM 返回的格式）
type ToolCall struct {
    ID         string                 `json:"id"`
    Name       string                 `json:"name"`
    Parameters map[string]any         `json:"parameters"`
}

// 执行结果
type Result struct {
    ToolCallID string  `json:"tool_call_id"`
    Content    string  `json:"content"`
    Error      error   `json:"error,omitempty"`
    Metadata   map[string]any `json:"metadata,omitempty"`
}
```

### 关键方法

#### 3.1 注册工具

```go
func (t *ToolRegistry) Register(tool Tool) {
    t.mu.Lock()
    defer t.mu.Unlock()
    
    name := tool.Name()
    if _, exists := t.tools[name]; exists {
        log.Printf("Warning: tool %s already registered, overwriting", name)
    }
    
    t.tools[name] = tool
    log.Printf("Tool registered: %s", name)
}
```

#### 3.2 生成工具定义

```go
func (t *ToolRegistry) Definitions() []ToolDef {
    t.mu.RLock()
    defer t.mu.RUnlock()
    
    defs := make([]ToolDef, 0, len(t.tools))
    for _, tool := range t.tools {
        defs = append(defs, ToolDef{
            Name:        tool.Name(),
            Description: tool.Description(),
            Parameters:  tool.Parameters(),
        })
    }
    
    return defs
}
```

#### 3.3 执行工具

```go
func (t *ToolRegistry) Execute(call ToolCall) Result {
    t.mu.RLock()
    tool, exists := t.tools[call.Name]
    t.mu.RUnlock()
    
    if !exists {
        return Result{
            ToolCallID: call.ID,
            Error:      fmt.Errorf("tool not found: %s", call.Name),
        }
    }
    
    // 执行工具（带 recover 防止 panic）
    var result Result
    func() {
        defer func() {
            if r := recover(); r != nil {
                result = Result{
                    ToolCallID: call.ID,
                    Error:      fmt.Errorf("tool panic: %v", r),
                }
            }
        }()
        
        result, _ = tool.Execute(NewContext(), call.Parameters)
        result.ToolCallID = call.ID
    }()
    
    return result
}
```

### 内置工具示例

```go
// 示例：Shell 工具
type ShellTool struct{}

func (s *ShellTool) Name() string { return "shell" }

func (s *ShellTool) Description() string {
    return "Execute a shell command and return the output"
}

func (s *ShellTool) Parameters() map[string]ParameterSchema {
    return map[string]ParameterSchema{
        "command": {
            Type:        "string",
            Description: "The shell command to execute",
            Required:    true,
        },
        "timeout": {
            Type:        "number",
            Description: "Timeout in seconds (default: 30)",
            Required:    false,
            Default:     30,
        },
    }
}

func (s *ShellTool) Execute(ctx Context, params map[string]any) (Result, error) {
    command, ok := params["command"].(string)
    if !ok {
        return Result{}, fmt.Errorf("invalid command parameter")
    }
    
    timeout := 30 * time.Second
    if t, ok := params["timeout"].(float64); ok {
        timeout = time.Duration(t) * time.Second
    }
    
    // 执行命令
    cmdCtx, cancel := context.WithTimeout(context.Background(), timeout)
    defer cancel()
    
    cmd := exec.CommandContext(cmdCtx, "sh", "-c", command)
    output, err := cmd.CombinedOutput()
    
    if err != nil {
        return Result{
            Content: string(output),
            Error:   err,
        }, nil // 返回错误但不中断流程
    }
    
    return Result{
        Content: string(output),
        Metadata: map[string]any{
            "exit_code": cmd.ProcessState.ExitCode(),
        },
    }, nil
}
```

---

## 4. Gateway - 多通道网关

### 职责
- HTTP 服务器管理
- 通道适配器注册
- 消息路由和分发
- 健康检查和监控

### 核心结构

```go
// cmd/gateway/main.go
type Gateway struct {
    // 服务器
    server     *http.Server
    port       int
    
    // 组件
    channels   map[string]Channel       // 通道适配器
    instances  map[string]*AgentInstance // 会话实例
    tools      *ToolRegistry            // 全局工具注册表
    
    // 配置
    config     GatewayConfig
    
    // 资源
    mu         sync.RWMutex
    shutdownCh chan struct{}
}

// 通道接口
type Channel interface {
    Name() string                                    // 通道名称
    Connect(config ChannelConfig) error              // 连接
    Disconnect() error                               // 断开
    SendMessage(target string, msg Message) error    // 发送消息
}

// 网关配置
type GatewayConfig struct {
    Port           int               // HTTP 端口
    Channels       []ChannelConfig   // 通道配置
    InstanceConfig AgentConfig       // 默认 Agent 配置
    MaxInstances   int               // 最大会话数
    IdleTimeout    time.Duration     // 空闲超时
}
```

### 关键方法

#### 4.1 启动服务器

```go
func (g *Gateway) Start() error {
    // 1. 注册 HTTP 路由
    http.HandleFunc("/health", g.handleHealth)
    http.HandleFunc("/api/message", g.handleMessage)
    http.HandleFunc("/api/instances", g.handleInstances)
    
    // 2. 初始化通道
    for _, chConfig := range g.config.Channels {
        channel := g.createChannel(chConfig.Type)
        if err := channel.Connect(chConfig); err != nil {
            return fmt.Errorf("failed to connect channel %s: %w", chConfig.Type, err)
        }
        g.channels[chConfig.Type] = channel
        log.Printf("Channel connected: %s", chConfig.Type)
    }
    
    // 3. 启动 HTTP 服务器
    addr := fmt.Sprintf(":%d", g.port)
    log.Printf("Gateway starting on %s", addr)
    
    return g.server.ListenAndServe()
}
```

#### 4.2 消息处理

```go
func (g *Gateway) handleMessage(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
        return
    }
    
    // 1. 解析请求
    var req MessageRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }
    
    // 2. 获取或创建会话实例
    instanceKey := fmt.Sprintf("%s:%s", req.ChannelID, req.UserID)
    instance := g.getOrCreateInstance(instanceKey)
    
    // 3. 处理消息
    response, err := instance.ProcessMessage(req.Message)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    
    // 4. 返回响应
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response)
}
```

#### 4.3 会话管理

```go
func (g *Gateway) getOrCreateInstance(key string) *AgentInstance {
    g.mu.RLock()
    instance, exists := g.instances[key]
    g.mu.RUnlock()
    
    if exists {
        return instance
    }
    
    // 创建新实例
    g.mu.Lock()
    defer g.mu.Unlock()
    
    // 检查实例数量限制
    if len(g.instances) >= g.config.MaxInstances {
        // 清理最久未使用的实例
        g.evictOldestInstance()
    }
    
    instance = NewAgentInstance(g.config.InstanceConfig)
    instance.SetupDefaultTools()
    g.instances[key] = instance
    
    log.Printf("New instance created: %s", key)
    return instance
}

func (g *Gateway) evictOldestInstance() {
    var oldestKey string
    var oldestTime time.Time
    
    for key, instance := range g.instances {
        if oldestKey == "" || instance.lastActive.Before(oldestTime) {
            oldestKey = key
            oldestTime = instance.lastActive
        }
    }
    
    if oldestKey != "" {
        g.instances[oldestKey].Close()
        delete(g.instances, oldestKey)
        log.Printf("Instance evicted: %s", oldestKey)
    }
}
```

---

## 📊 组件交互图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Gateway                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  HTTP Server                                              │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │ │
│  │  │ /health     │  │ /api/message│  │ /api/...    │       │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │ │
│  └─────────┼────────────────┼────────────────┼───────────────┘ │
│            │                │                │                 │
│            └────────────────┼────────────────┘                 │
│                             │                                  │
│              ┌──────────────▼──────────────┐                  │
│              │    InstanceManager          │                  │
│              │  (getOrCreateInstance)      │                  │
│              └──────────────┬──────────────┘                  │
│                             │                                  │
│              ┌──────────────▼──────────────┐                  │
│              │    AgentInstance #1         │                  │
│              │  ┌───────────────────────┐  │                  │
│              │  │    AgentLoop          │  │                  │
│              │  │  ┌─────────────────┐  │  │                  │
│              │  │  │   LLM Provider  │  │  │                  │
│              │  │  └────────┬────────┘  │  │                  │
│              │  │           │           │  │                  │
│              │  │  ┌────────▼────────┐  │  │                  │
│              │  │  │  ToolRegistry   │  │  │                  │
│              │  │  │ ┌────┐ ┌────┐  │  │  │                  │
│              │  │  │ │Srch│ │File│  │  │  │                  │
│              │  │  │ └────┘ └────┘  │  │  │                  │
│              │  │  └─────────────────┘  │  │                  │
│              │  └───────────────────────┘  │                  │
│              └─────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 源码阅读建议

### 阅读顺序
1. `pkg/tools/registry.go` - 最简单，理解工具接口
2. `pkg/agent/loop.go` - 核心执行逻辑
3. `pkg/agent/instance.go` - 会话管理
4. `cmd/gateway/main.go` - 集成和启动

### 重点关注
- 接口定义（理解抽象层次）
- 错误处理（理解容错机制）
- 并发控制（理解锁的使用）
- 配置管理（理解灵活性设计）

---

**下一篇**: [03-execution-flow.md](03-execution-flow.md)

最后更新：2026-03-29
