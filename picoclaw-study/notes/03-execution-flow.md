# PicoClaw 执行流程分析

> 📌 深入解析 PicoClaw 的消息处理和工具调用机制

---

## 目录

1. [消息处理流程](#1-消息处理流程)
2. [工具调用机制](#2-工具调用机制)
3. [会话状态管理](#3-会话状态管理)
4. [并发控制](#4-并发控制)
5. [错误处理](#5-错误处理)

---

## 1. 消息处理流程

### 1.1 完整消息流

```
┌─────────────────────────────────────────────────────────────────┐
│                     外部平台消息                                  │
│              (Telegram / Discord / Feishu / ...)                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Channel 接收                                                 │
│     - 解析原始消息                                               │
│     - 转换为统一格式 (providers.Message)                         │
│     - 处理媒体文件 (图片/语音)                                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 发布到 MessageBus.Inbound                                    │
│     bus.PublishInbound(ctx, InboundMessage)                     │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. AgentLoop.Run 接收                                           │
│     case msg := <-al.bus.InboundChan()                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. 路由解析                                                     │
│     - 确定哪个 Agent 处理                                          │
│     - 支持基于内容的路由 (Router)                                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. processMessage 处理                                          │
│     - 创建 Turn State                                            │
│     - 加载会话历史                                               │
│     - 进入工具执行循环                                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. RunToolLoop 执行                                             │
│     - 构建上下文                                                 │
│     - 调用 LLM                                                    │
│     - 执行工具调用                                               │
│     - 合成响应                                                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. 发布到 MessageBus.Outbound                                   │
│     bus.PublishOutbound(ctx, OutboundMessage)                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  8. Channel 发送响应                                             │
│     - 格式化消息                                                 │
│     - 处理媒体附件                                               │
│     - 发送回用户                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 消息路由

```go
// pkg/agent/loop.go
func (al *AgentLoop) resolveMessageRoute(msg bus.InboundMessage) (*routing.Route, string, error) {
    // 1. 构建路由输入
    input := routing.RouteInput{
        Channel:  msg.Channel,
        ChatID:   msg.ChatID,
        Content:  msg.Content,
        SenderID: msg.SenderID,
    }
    
    // 2. 使用 Resolver 解析
    route := al.registry.ResolveRoute(input)
    
    // 3. 确定 Agent ID
    agentID := route.AgentID
    if agentID == "" {
        agentID = "main" // 默认 Agent
    }
    
    return route, agentID, nil
}
```

### 1.3 模型路由（可选）

```go
// pkg/routing/router.go
type Router struct {
    lightModel string
    threshold  float64
}

func (r *Router) Score(input string) float64 {
    // 基于输入复杂度评分
    // - 简单问题：使用轻量模型
    // - 复杂任务：使用主模型
}

func (r *Router) ShouldUseLight(input string) bool {
    score := r.Score(input)
    return score < r.threshold
}
```

---

## 2. 工具调用机制

### 2.1 工具调用循环

```go
// pkg/agent/loop.go - RunToolLoop
func (al *AgentLoop) RunToolLoop(ctx context.Context, ts *turnState, agent *AgentInstance) (string, error) {
    var finalResponse string
    var lastErr error
    
    for iteration := 0; iteration < agent.MaxIterations; iteration++ {
        // === 步骤 1: 构建上下文 ===
        messages, err := agent.ContextBuilder.Build(ctx, ts.session)
        if err != nil {
            logger.Error("Failed to build context", err)
            lastErr = err
            continue
        }
        
        // === 步骤 2: 调用 LLM ===
        response, err := al.callLLM(ctx, agent, messages, agent.Tools)
        if err != nil {
            logger.Error("LLM call failed", err)
            lastErr = err
            continue
        }
        
        // === 步骤 3: 处理响应 ===
        if response.Content != "" {
            finalResponse = response.Content
            // 添加到会话
            ts.session.AddMessage(providers.Message{
                Role:    "assistant",
                Content: response.Content,
            })
        }
        
        // === 步骤 4: 检查工具调用 ===
        if len(response.ToolCalls) > 0 {
            logger.Info("Executing tools", map[string]any{
                "count": len(response.ToolCalls),
            })
            
            // 执行所有工具调用
            results := al.executeTools(ctx, ts, response.ToolCalls)
            
            // 将结果添加到会话
            for i, result := range results {
                ts.session.AddToolResult(providers.ToolResult{
                    ToolCallID: response.ToolCalls[i].ID,
                    Content:    result.ForLLM,
                })
            }
            
            // 继续循环，将结果发送给 LLM
            continue
        }
        
        // === 步骤 5: 有最终响应，退出循环 ===
        if finalResponse != "" {
            break
        }
    }
    
    return finalResponse, lastErr
}
```

### 2.2 LLM 调用

```go
// pkg/agent/loop.go
func (al *AgentLoop) callLLM(
    ctx context.Context,
    agent *AgentInstance,
    messages []providers.Message,
    tools *tools.ToolRegistry,
) (*providers.LLMResponse, error) {
    // 1. 获取工具定义
    toolDefs := al.buildToolDefinitions(tools)
    
    // 2. 选择模型
    model := agent.Model
    
    // 3. 调用 Provider
    response, err := agent.Provider.Chat(ctx, messages, toolDefs, model, map[string]any{
        "max_tokens":  agent.MaxTokens,
        "temperature": agent.Temperature,
    })
    
    // 4. 事件记录
    al.emitEvent(EventKindLLMResponse, EventMeta{...}, LLMResponsePayload{
        ContentLen: len(response.Content),
        ToolCalls:  len(response.ToolCalls),
    })
    
    return response, err
}
```

### 2.3 工具执行

```go
// pkg/agent/loop.go
func (al *AgentLoop) executeTools(
    ctx context.Context,
    ts *turnState,
    toolCalls []providers.ToolCall,
) []*tools.ToolResult {
    var results []*tools.ToolResult
    var wg sync.WaitGroup
    resultChan := make(chan *tools.ToolResult, len(toolCalls))
    
    for _, call := range toolCalls {
        wg.Add(1)
        go func(tc providers.ToolCall) {
            defer wg.Done()
            
            // 1. 获取工具
            tool, ok := ts.agent.Tools.Get(tc.Name)
            if !ok {
                resultChan <- &tools.ToolResult{
                    Content: fmt.Sprintf("Tool %s not found", tc.Name),
                    IsError: true,
                }
                return
            }
            
            // 2. 执行工具
            result, err := tool.Execute(ctx, tc.Arguments)
            if err != nil {
                resultChan <- &tools.ToolResult{
                    Content: err.Error(),
                    IsError: true,
                }
                return
            }
            
            resultChan <- result
        }(call)
    }
    
    // 等待所有工具执行完成
    go func() {
        wg.Wait()
        close(resultChan)
    }()
    
    // 收集结果
    for result := range resultChan {
        results = append(results, result)
    }
    
    return results
}
```

### 2.4 工具定义构建

```go
// pkg/agent/loop.go
func (al *AgentLoop) buildToolDefinitions(registry *tools.ToolRegistry) []providers.ToolDefinition {
    var defs []providers.ToolDefinition
    
    for _, name := range registry.List() {
        tool, _ := registry.Get(name)
        defs = append(defs, tool.Definition())
    }
    
    return defs
}
```

---

## 3. 会话状态管理

### 3.1 Turn State

```go
// pkg/agent/turn.go
type turnState struct {
    ctx            context.Context
    turnID         string              // 当前 Turn ID
    depth          int                 // 嵌套深度（用于 SubTurn）
    session        session.Session     // 会话对象
    pendingResults chan *tools.ToolResult // 等待的工具结果
    concurrencySem chan struct{}       // 并发信号量
}

func (al *AgentLoop) createTurnState(
    ctx context.Context,
    agent *AgentInstance,
    msg bus.InboundMessage,
) *turnState {
    // 1. 生成 Turn ID
    turnID := fmt.Sprintf("%s-turn-%d", agent.ID, al.turnSeq.Add(1))
    
    // 2. 获取或创建会话
    sessionKey := al.resolveSessionKey(msg)
    sess, err := agent.Sessions.Get(sessionKey)
    if err != nil {
        sess = session.New()
    }
    
    // 3. 创建 Turn State
    return &turnState{
        ctx:            ctx,
        turnID:         turnID,
        depth:          0,
        session:        sess,
        pendingResults: make(chan *tools.ToolResult, 16),
        concurrencySem: make(chan struct{}, 5), // 最多 5 个并发工具
    }
}
```

### 3.2 会话存储

```go
// pkg/session/jsonl.go
type Session struct {
    Messages  []providers.Message  `json:"messages"`
    CreatedAt time.Time            `json:"created_at"`
    UpdatedAt time.Time            `json:"updated_at"`
    Metadata  map[string]string    `json:"metadata,omitempty"`
}

func (s *Session) AddMessage(msg providers.Message) {
    s.Messages = append(s.Messages, msg)
    s.UpdatedAt = time.Now()
}

func (s *Session) AddToolResult(result providers.ToolResult) {
    s.Messages = append(s.Messages, providers.Message{
        Role:       "tool",
        Content:    result.Content,
        ToolCallID: result.ToolCallID,
    })
    s.UpdatedAt = time.Now()
}

func (s *Session) GetHistory() []providers.Message {
    return s.Messages
}
```

### 3.3 会话持久化

```go
// pkg/memory/jsonl.go
type JSONLStore struct {
    dir      string
    file     *os.File
    sessions map[string]*Session
    mu       sync.Mutex
}

func (s *JSONLStore) Save(key string, session *Session) error {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    // 序列化
    data, err := json.Marshal(session)
    if err != nil {
        return err
    }
    
    // 追加到 JSONL 文件
    _, err = s.file.Write(data)
    if err != nil {
        return err
    }
    _, err = s.file.Write([]byte("\n"))
    return err
}

func (s *JSONLStore) Get(key string) (*Session, error) {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    // 从内存缓存获取
    if sess, ok := s.sessions[key]; ok {
        return sess, nil
    }
    
    // 从文件读取
    return s.loadFromFile(key)
}
```

---

## 4. 并发控制

### 4.1 Turn 并发

```go
// pkg/agent/loop.go
type AgentLoop struct {
    // 活跃 Turn 状态（按 sessionKey 索引）
    activeTurnStates sync.Map     // map[string]*turnState
    
    // Turn 序列号
    turnSeq atomic.Uint64
}

func (al *AgentLoop) getOrCreateTurnState(sessionKey string) *turnState {
    if ts, ok := al.activeTurnStates.Load(sessionKey); ok {
        return ts.(*turnState)
    }
    
    // 创建新的 Turn State
    ts := al.createTurnState(...)
    al.activeTurnStates.Store(sessionKey, ts)
    return ts
}
```

### 4.2 SubTurn（子 Agent）

```go
// pkg/agent/subturn.go
type SubTurnConfig struct {
    Model        string
    Tools        []tools.Tool
    SystemPrompt string
    MaxTokens    int
}

func spawnSubTurn(
    ctx context.Context,
    al *AgentLoop,
    parentTS *turnState,
    config SubTurnConfig,
) (*tools.ToolResult, error) {
    // 1. 创建子 Turn State
    childTS := &turnState{
        ctx:            ctx,
        turnID:         fmt.Sprintf("%s-sub-%d", parentTS.turnID, al.subTurnCounter.Add(1)),
        depth:          parentTS.depth + 1,
        session:        session.New(),
        pendingResults: make(chan *tools.ToolResult, 16),
    }
    
    // 2. 创建临时 Agent
    childAgent := al.createTempAgent(config)
    
    // 3. 执行子 Turn
    response, err := al.RunToolLoop(ctx, childTS, childAgent)
    
    // 4. 返回结果给父 Turn
    return &tools.ToolResult{
        Content: response,
        ForLLM:  fmt.Sprintf("[SubAgent completed: %s]", response),
    }, err
}
```

### 4.3 并发信号量

```go
// 工具执行时的并发控制
func (al *AgentLoop) executeTools(ctx context.Context, ts *turnState, toolCalls []providers.ToolCall) []*tools.ToolResult {
    var results []*tools.ToolResult
    var wg sync.WaitGroup
    
    for _, call := range toolCalls {
        // 获取信号量
        ts.concurrencySem <- struct{}{}
        
        wg.Add(1)
        go func(tc providers.ToolCall) {
            defer func() {
                <-ts.concurrencySem // 释放信号量
                wg.Done()
            }()
            
            // 执行工具...
        }(call)
    }
    
    wg.Wait()
    return results
}
```

---

## 5. 错误处理

### 5.1 错误类型

```go
// pkg/agent/errors.go
type AgentError struct {
    Stage   string // 错误发生的阶段
    Message string
    Cause   error
}

func (e *AgentError) Error() string {
    return fmt.Sprintf("[%s] %s: %v", e.Stage, e.Message, e.Cause)
}

// 常见错误
var (
    ErrAgentNotFound    = &AgentError{Stage: "route", Message: "agent not found"}
    ErrToolNotFound     = &AgentError{Stage: "execute", Message: "tool not found"}
    ErrContextTooLong   = &AgentError{Stage: "context", Message: "context exceeds limit"}
    ErrMaxIterations    = &AgentError{Stage: "loop", Message: "max iterations reached"}
)
```

### 5.2 错误恢复

```go
// pkg/agent/loop.go
func (al *AgentLoop) RunToolLoop(...) (string, error) {
    for iteration := 0; iteration < agent.MaxIterations; iteration++ {
        // 尝试执行
        response, err := al.callLLM(...)
        
        if err != nil {
            // 1. 记录错误
            al.emitEvent(EventKindError, ..., ErrorPayload{
                Stage:   "llm_call",
                Message: err.Error(),
            })
            
            // 2. 尝试降级
            if fallbackErr := al.tryFallback(ctx, messages, tools); fallbackErr == nil {
                continue // 降级成功，继续
            }
            
            // 3. 返回错误
            lastErr = err
            continue
        }
        
        // 正常处理...
    }
    
    return "", fmt.Errorf("failed after %d iterations: %w", agent.MaxIterations, lastErr)
}
```

### 5.3 降级链

```go
// pkg/providers/fallback.go
func (f *FallbackChain) Chat(ctx context.Context, messages, tools) (*LLMResponse, error) {
    var lastErr error
    
    for i, candidate := range f.candidates {
        // 检查是否在冷却期
        if f.cooldown.IsInCooldown(candidate) {
            logger.Debug("Skipping candidate (cooldown)", candidate.Model)
            continue
        }
        
        // 检查限流
        if f.rateLimiter.IsRateLimited(candidate) {
            logger.Debug("Skipping candidate (rate limited)", candidate.Model)
            continue
        }
        
        // 尝试调用
        response, err := f.callCandidate(ctx, candidate, messages, tools)
        if err == nil {
            // 成功，重置冷却
            f.cooldown.MarkSuccess(candidate)
            return response, nil
        }
        
        // 失败，标记冷却
        logger.Warn("Candidate failed", map[string]any{
            "model": candidate.Model,
            "error": err.Error(),
            "attempt": i + 1,
        })
        f.cooldown.MarkFailed(candidate)
        lastErr = err
    }
    
    return nil, fmt.Errorf("all candidates failed: %w", lastErr)
}
```

---

## 6. 事件系统

### 6.1 事件类型

```go
// pkg/agent/events.go
type EventKind int

const (
    EventKindTurnStart EventKind = iota
    EventKindTurnEnd
    EventKindLLMRequest
    EventKindLLMResponse
    EventKindToolExecStart
    EventKindToolExecEnd
    EventKindError
)

type Event struct {
    Kind    EventKind
    Meta    EventMeta
    Payload any
}

type EventMeta struct {
    AgentID    string
    TurnID     string
    SessionKey string
    Iteration  int
    Source     string
}
```

### 6.2 事件总线

```go
// pkg/agent/eventbus.go
type EventBus struct {
    subscribers map[uint64]chan Event
    mu          sync.RWMutex
    nextID      atomic.Uint64
}

func (eb *EventBus) Subscribe(buffer int) EventSubscription {
    eb.mu.Lock()
    defer eb.mu.Unlock()
    
    id := eb.nextID.Add(1)
    ch := make(chan Event, buffer)
    eb.subscribers[id] = ch
    
    return EventSubscription{ID: id, C: ch}
}

func (eb *EventBus) Emit(event Event) {
    eb.mu.RLock()
    defer eb.mu.RUnlock()
    
    for _, ch := range eb.subscribers {
        select {
        case ch <- event:
        default:
            // 频道已满，丢弃
        }
    }
}
```

---

## 7. Hook 系统

### 7.1 Hook 类型

```go
// pkg/agent/hooks.go
type HookStage string

const (
    HookStageBeforeLLM   HookStage = "before_llm"
    HookStageAfterLLM    HookStage = "after_llm"
    HookStageBeforeTool  HookStage = "before_tool"
    HookStageAfterTool   HookStage = "after_tool"
)

type Hook interface {
    Name() string
    Stages() []HookStage
    Execute(ctx context.Context, payload HookPayload) (HookDecision, error)
}
```

### 7.2 Hook 注册

```go
// pkg/agent/hook_manager.go
type HookManager struct {
    hooks map[string]Hook
    mu    sync.RWMutex
}

func (hm *HookManager) Mount(reg HookRegistration) error {
    hm.mu.Lock()
    defer hm.mu.Unlock()
    
    if _, ok := hm.hooks[reg.Name]; ok {
        return fmt.Errorf("hook %s already exists", reg.Name)
    }
    
    hm.hooks[reg.Name] = reg.Hook
    return nil
}

func (hm *HookManager) ExecuteStage(
    ctx context.Context,
    stage HookStage,
    payload HookPayload,
) (HookDecision, error) {
    hm.mu.RLock()
    defer hm.mu.RUnlock()
    
    for _, hook := range hm.hooks {
        for _, s := range hook.Stages() {
            if s == stage {
                decision, err := hook.Execute(ctx, payload)
                if err != nil {
                    return decision, err
                }
                if decision.Stop {
                    return decision, nil
                }
            }
        }
    }
    
    return HookDecision{Stop: false}, nil
}
```

---

**最后更新**: 2026-04-08  
**基于版本**: PicoClaw v1.x