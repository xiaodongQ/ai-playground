# PicoClaw 执行流程详解

> 🔄 深入分析一次完整请求的处理链路

**学习时间**: 2026-03-29  
**核心文件**: `pkg/agent/loop.go`, `pkg/agent/instance.go`

---

## 📊 整体流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        用户发送消息 (Telegram/Discord)                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. Gateway 接收消息                                                     │
│     - HTTP/WebSocket 接收                                                │
│     - 平台格式 → 统一 Message 格式                                        │
│     - 提取 ChannelID、UserID                                             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. 会话路由                                                             │
│     - 生成 InstanceKey: "channelId:userId"                               │
│     - 查找现有 AgentInstance                                             │
│     - 不存在则创建新实例                                                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. AgentInstance.ProcessMessage()                                      │
│     - 加锁 (sync.RWMutex)                                               │
│     - 添加用户消息到 Messages[]                                          │
│     - 更新 lastActive 时间                                               │
│     - 裁剪消息历史 (trimMessages)                                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. AgentLoop.Run() - 执行循环                                          │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Iteration 1                                                    │   │
│  │  ┌───────────────────────────────────────────────────────────┐ │   │
│  │  │  4.1 调用 LLM                                             │ │   │
│  │  │      - 构建请求：messages + tool definitions              │ │   │
│  │  │      - HTTP POST 到 LLM API                                │ │   │
│  │  │      - 解析响应：content + tool_calls                     │ │   │
│  │  │      - 返回 Response                                      │ │   │
│  │  └───────────────────────────────────────────────────────────┘ │   │
│  │                            │                                     │   │
│  │                            ▼                                     │   │
│  │  ┌───────────────────────────────────────────────────────────┐ │   │
│  │  │  4.2 检查工具调用                                          │ │   │
│  │  │      - tool_calls 是否为空？                               │ │   │
│  │  │      - 空 → 返回最终答案，结束循环                         │ │   │
│  │  │      - 非空 → 继续执行工具                                 │ │   │
│  │  └───────────────────────────────────────────────────────────┘ │   │
│  │                            │                                     │   │
│  │                            ▼                                     │   │
│  │  ┌───────────────────────────────────────────────────────────┐ │   │
│  │  │  4.3 执行工具调用                                          │ │   │
│  │  │      for each toolCall:                                   │ │   │
│  │  │        - ToolRegistry.Get(toolCall.Name)                  │ │   │
│  │  │        - tool.Execute(ctx, params)                        │ │   │
│  │  │        - 获取 Result                                      │ │   │
│  │  │        - Result → Message 添加到 workingMessages[]         │ │   │
│  │  └───────────────────────────────────────────────────────────┘ │   │
│  │                            │                                     │   │
│  │                            ▼                                     │   │
│  │  ┌───────────────────────────────────────────────────────────┐ │   │
│  │  │  4.4 检查迭代次数                                          │ │   │
│  │  │      - iteration < maxIterations?                         │ │   │
│  │  │      - 是 → 回到 4.1 继续循环                              │ │   │
│  │  │      - 否 → 返回错误：max iterations reached              │ │   │
│  │  └───────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. 返回响应                                                             │
│     - AgentInstance 添加助手消息到 Messages[]                            │
│     - 释放锁                                                            │
│     - Gateway 返回 HTTP 响应                                             │
│     - 通过原通道发送给用户                                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        用户收到回复                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 详细步骤分析

### 步骤 1: Gateway 接收消息

```go
// cmd/gateway/main.go
func (g *Gateway) handleMessage(w http.ResponseWriter, r *http.Request) {
    // 1.1 解析 JSON 请求
    var req MessageRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }
    
    // 请求结构
    type MessageRequest struct {
        ChannelID string  `json:"channel_id"`  // "telegram" / "discord"
        UserID    string  `json:"user_id"`     // 用户唯一标识
        Message   Message `json:"message"`     // 消息内容
    }
    
    // 1.2 验证必填字段
    if req.ChannelID == "" || req.UserID == "" {
        http.Error(w, "channel_id and user_id required", http.StatusBadRequest)
        return
    }
    
    // 1.3 消息格式转换（如果是平台特定格式）
    // 例如：Telegram 的 update.message.text → Message.Content
    msg := g.convertToInternalMessage(req.Message)
    
    log.Printf("Received message from %s:%s", req.ChannelID, req.UserID)
}
```

**关键点**:
- 统一消息格式（屏蔽平台差异）
- 必填字段验证
- 错误处理

---

### 步骤 2: 会话路由

```go
func (g *Gateway) handleMessage(...) {
    // 2.1 生成会话唯一键
    instanceKey := fmt.Sprintf("%s:%s", req.ChannelID, req.UserID)
    
    // 2.2 查找或创建实例
    instance := g.getOrCreateInstance(instanceKey)
    
    // 2.3 实例复用逻辑
    // - 同一用户在同一通道的消息使用同一实例
    // - 不同通道或不同用户使用不同实例
    // - 空闲超时的实例会被清理
}

func (g *Gateway) getOrCreateInstance(key string) *AgentInstance {
    // 2.4 读锁查找（高并发友好）
    g.mu.RLock()
    instance, exists := g.instances[key]
    g.mu.RUnlock()
    
    if exists {
        return instance
    }
    
    // 2.5 写锁创建
    g.mu.Lock()
    defer g.mu.Unlock()
    
    // 双重检查（防止并发创建）
    if instance, exists = g.instances[key]; exists {
        return instance
    }
    
    // 2.6 检查实例数量限制
    if len(g.instances) >= g.config.MaxInstances {
        g.evictOldestInstance()
    }
    
    // 2.7 创建新实例
    instance = NewAgentInstance(g.config.InstanceConfig)
    instance.SetupDefaultTools()
    g.instances[key] = instance
    
    log.Printf("New instance created: %s", key)
    return instance
}
```

**关键点**:
- 读写锁优化（读多写少场景）
- 双重检查锁定（DCL 模式）
- 实例数量限制和驱逐策略

---

### 步骤 3: AgentInstance 处理消息

```go
// pkg/agent/instance.go
func (a *AgentInstance) ProcessMessage(input Message) (Response, error) {
    // 3.1 加锁（防止并发修改）
    a.mu.Lock()
    defer a.mu.Unlock()
    
    // 3.2 添加用户消息到历史
    a.Messages = append(a.Messages, input)
    a.lastActive = time.Now()
    
    // 3.3 裁剪消息历史
    a.trimMessages()
    
    // 3.4 调用 AgentLoop 执行
    response, err := a.Loop.Run(a.Context, a.Messages)
    if err != nil {
        return Response{}, err
    }
    
    // 3.5 添加助手响应到历史
    a.Messages = append(a.Messages, response.ToMessage())
    
    return response, nil
}

// 消息裁剪策略
func (a *AgentInstance) trimMessages() {
    // 策略 1: 保留固定数量
    // if len(a.Messages) > a.MaxMessages {
    //     a.Messages = a.Messages[len(a.Messages)-a.MaxMessages:]
    // }
    
    // 策略 2: 基于 token 估算（更精确）
    for len(a.Messages) > 2 && a.estimateTokens() > a.MaxTokens {
        // 移除最早的非系统消息
        // Messages[0] 通常是系统提示词，保留
        a.Messages = a.Messages[1:]
    }
}

func (a *AgentInstance) estimateTokens() int {
    total := 0
    for _, msg := range a.Messages {
        // 简单估算：每 4 个字符 ≈ 1 token
        // 实际应该用 tokenizer，但这样更轻量
        total += len(msg.Content) / 4
    }
    return total
}
```

**关键点**:
- 并发安全（sync.RWMutex）
- 消息历史管理
- Token 限制控制

---

### 步骤 4: AgentLoop 执行循环

#### 4.1 调用 LLM

```go
// pkg/agent/loop.go
func (a *AgentLoop) Run(ctx Context, messages []Message) (Response, error) {
    a.currentIteration = 0
    
    // 4.1.1 创建消息副本（避免修改原始数据）
    workingMessages := make([]Message, len(messages))
    copy(workingMessages, messages)
    
    for a.currentIteration < a.MaxIterations {
        a.currentIteration++
        
        // 4.1.2 调用 LLM
        response, err := a.LLM.Call(ctx, workingMessages, a.Tools.Definitions())
        if err != nil {
            return Response{}, fmt.Errorf("LLM call failed: %w", err)
        }
        
        // ... 继续处理
    }
}

// LLM 调用实现示例（Anthropic）
func (p *AnthropicProvider) Call(ctx Context, messages []Message, tools []ToolDef) (Response, error) {
    // 4.1.3 构建请求体
    reqBody := map[string]any{
        "model":         p.model,
        "max_tokens":    p.maxTokens,
        "messages":      p.formatMessages(messages),
        "tools":         tools,
        "tool_choice":   "auto",
    }
    
    // 4.1.4 发送 HTTP 请求
    req, _ := json.Marshal(reqBody)
    httpReq, _ := http.NewRequest("POST", p.baseURL+"/v1/messages", bytes.NewReader(req))
    httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
    httpReq.Header.Set("Content-Type", "application/json")
    
    resp, err := p.httpClient.Do(httpReq)
    if err != nil {
        return Response{}, err
    }
    defer resp.Body.Close()
    
    // 4.1.5 解析响应
    var apiResp AnthropicResponse
    json.NewDecoder(resp.Body).Decode(&apiResp)
    
    // 4.1.6 转换为内部 Response 格式
    return p.convertResponse(apiResp), nil
}
```

**关键点**:
- 消息格式转换
- HTTP 客户端复用
- 错误处理

---

#### 4.2 检查工具调用

```go
func (a *AgentLoop) Run(...) (Response, error) {
    for a.currentIteration < a.MaxIterations {
        // ... 调用 LLM ...
        
        // 4.2.1 检查是否有工具调用
        if len(response.ToolCalls) == 0 {
            // 没有工具调用，返回最终答案
            log.Printf("Iteration %d: No tool calls, returning final answer", a.currentIteration)
            return response, nil
        }
        
        log.Printf("Iteration %d: Found %d tool calls", a.currentIteration, len(response.ToolCalls))
        
        // ... 继续执行工具 ...
    }
}
```

**关键点**:
- 工具调用检测
- 循环终止条件

---

#### 4.3 执行工具调用

```go
func (a *AgentLoop) Run(...) (Response, error) {
    for a.currentIteration < a.MaxIterations {
        // ... 调用 LLM 和检查工具 ...
        
        // 4.3.1 遍历所有工具调用
        for _, toolCall := range response.ToolCalls {
            log.Printf("Executing tool: %s", toolCall.Name)
            
            // 4.3.2 查找工具
            tool := a.Tools.Get(toolCall.Name)
            if tool == nil {
                return Response{}, fmt.Errorf("tool not found: %s", toolCall.Name)
            }
            
            // 4.3.3 执行工具
            result, err := tool.Execute(ctx, toolCall.Parameters)
            if err != nil {
                log.Printf("Tool execution error: %v", err)
                // 注意：工具错误不中断流程，继续执行其他工具
            }
            
            // 4.3.4 添加结果到消息历史
            // 工具结果作为 "tool" 角色的消息添加
            toolResultMsg := Message{
                Role:       "tool",
                Content:    result.Content,
                ToolCallID: result.ToolCallID,
                Metadata:   result.Metadata,
            }
            workingMessages = append(workingMessages, toolResultMsg)
        }
        
        // 4.3.5 继续下一次迭代
        // LLM 将看到工具执行结果，可能继续调用工具或返回最终答案
    }
}
```

**关键点**:
- 工具查找和执行
- 错误不中断流程
- 结果添加到消息历史

---

#### 4.4 检查迭代次数

```go
func (a *AgentLoop) Run(...) (Response, error) {
    for a.currentIteration < a.MaxIterations {
        // ... 执行循环体 ...
    }
    
    // 4.4.1 达到最大迭代次数
    return Response{
        Content: "I reached the maximum number of iterations without completing the task.",
        Error:   ErrMaxIterations,
        Metadata: map[string]any{
            "iterations": a.currentIteration,
            "max_iterations": a.MaxIterations,
        },
    }, nil
}
```

**关键点**:
- 防止无限循环
- 返回有意义的错误信息

---

### 步骤 5: 返回响应

```go
// pkg/agent/instance.go
func (a *AgentInstance) ProcessMessage(input Message) (Response, error) {
    // ... 执行循环 ...
    
    // 5.1 添加助手响应到历史
    a.Messages = append(a.Messages, response.ToMessage())
    
    // 5.2 释放锁（defer 自动执行）
    // a.mu.Unlock() - defer 执行
    
    // 5.3 返回响应
    return response, nil
}

// cmd/gateway/main.go
func (g *Gateway) handleMessage(w http.ResponseWriter, r *http.Request) {
    // ... 处理消息 ...
    
    // 5.4 返回 HTTP 响应
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response)
    
    // 5.5 如果是 WebSocket，推送到客户端
    if wsConn, ok := g.getWebSocket(req.UserID); ok {
        wsConn.WriteJSON(response)
    }
}
```

**关键点**:
- 消息历史更新
- HTTP/WebSocket 响应

---

## 📈 性能优化点

### 1. 并发控制

```go
// 使用 RWMutex 优化读多写少场景
type AgentInstance struct {
    mu sync.RWMutex  // 读写锁
}

// 读操作使用读锁（可并发）
func (a *AgentInstance) GetStatus() Status {
    a.mu.RLock()
    defer a.mu.RUnlock()
    // ...
}

// 写操作使用写锁（互斥）
func (a *AgentInstance) ProcessMessage(msg Message) {
    a.mu.Lock()
    defer a.mu.Unlock()
    // ...
}
```

### 2. 消息历史裁剪

```go
// 避免频繁裁剪（惰性策略）
func (a *AgentInstance) trimMessages() {
    // 只在超出阈值时裁剪
    if a.estimateTokens() > a.MaxTokens * 1.2 {
        // 裁剪到 80%
        targetTokens := a.MaxTokens * 80 / 100
        a.trimToTokens(targetTokens)
    }
}
```

### 3. HTTP 客户端复用

```go
// 使用连接池
type LLMProvider struct {
    httpClient *http.Client  // 复用连接
}

func NewLLMProvider(config Config) *LLMProvider {
    return &LLMProvider{
        httpClient: &http.Client{
            Transport: &http.Transport{
                MaxIdleConns:        100,
                MaxIdleConnsPerHost: 10,
                IdleConnTimeout:     90 * time.Second,
            },
            Timeout: 60 * time.Second,
        },
    }
}
```

### 4. 工具执行并发（可选）

```go
// 并发执行独立的工具调用
func (a *AgentLoop) executeToolsParallel(toolCalls []ToolCall) []Result {
    results := make([]Result, len(toolCalls))
    var wg sync.WaitGroup
    
    for i, call := range toolCalls {
        wg.Add(1)
        go func(idx int, call ToolCall) {
            defer wg.Done()
            tool := a.Tools.Get(call.Name)
            results[idx], _ = tool.Execute(a.Context, call.Parameters)
        }(i, call)
    }
    
    wg.Wait()
    return results
}
```

---

## 🐛 常见错误处理

### 1. LLM API 超时

```go
func (p *LLMProvider) Call(...) (Response, error) {
    ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
    defer cancel()
    
    req, _ := http.NewRequestWithContext(ctx, "POST", ...)
    resp, err := p.httpClient.Do(req)
    
    if err != nil {
        if ctx.Err() == context.DeadlineExceeded {
            return Response{}, ErrLLMTimeout
        }
        return Response{}, err
    }
}
```

### 2. 工具执行 Panic

```go
func (t *ToolRegistry) Execute(call ToolCall) Result {
    defer func() {
        if r := recover(); r != nil {
            result = Result{
                Error: fmt.Errorf("tool panic: %v", r),
            }
        }
    }()
    
    tool := t.tools[call.Name]
    return tool.Execute(...)
}
```

### 3. 消息历史过大

```go
func (a *AgentInstance) trimMessages() {
    // 保护：至少保留系统消息和最近一条用户消息
    if len(a.Messages) <= 2 {
        return
    }
    
    // 裁剪逻辑...
}
```

---

## 📊 执行时序图

```
用户     Gateway    AgentInstance    AgentLoop    LLM    ToolRegistry
 │          │            │              │          │          │
 │──消息──→│            │              │          │          │
 │          │──路由────→│              │          │          │
 │          │            │──加锁───────→│          │          │
 │          │            │              │          │          │
 │          │            │──执行───────→│          │          │
 │          │            │              │          │          │
 │          │            │              │──调用───→│          │
 │          │            │              │          │          │
 │          │            │              │←─响应───│          │
 │          │            │              │          │          │
 │          │            │              │──执行───→│          │
 │          │            │              │          │──执行───→│
 │          │            │              │          │          │
 │          │            │              │←─结果───│          │
 │          │            │              │          │          │
 │          │            │←─响应───────│          │          │
 │          │            │←─解锁───────│          │          │
 │          │←─响应─────│              │          │          │
 │←─回复───│            │              │          │          │
 │          │            │              │          │          │
```

---

## 📝 学习要点总结

### 核心流程
1. Gateway 接收和路由消息
2. AgentInstance 管理会话状态
3. AgentLoop 执行 LLM 调用循环
4. 工具调用和结果处理
5. 响应返回给用户

### 关键设计
- 读写锁优化并发
- 消息历史裁剪控制成本
- 迭代次数限制防止死循环
- 工具执行错误不中断流程

### 调试技巧
- 启用 debug 日志查看执行细节
- 使用 pprof 分析性能瓶颈
- 监控迭代次数和工具调用频率

---

**下一篇**: [04-design-patterns.md](04-design-patterns.md)

最后更新：2026-03-29
