# AgentLoop 源码分析

> 🔍 深入解析 PicoClaw 的核心执行引擎

**分析日期**: 2026-03-29  
**源文件**: `pkg/agent/loop.go`  
**代码行数**: ~200 行

---

## 📋 文件结构

```go
// pkg/agent/loop.go 结构概览

// 1. 类型定义
type AgentLoop struct { ... }
type AgentLoopConfig struct { ... }

// 2. 构造函数
func NewAgentLoop(config AgentLoopConfig) *AgentLoop

// 3. 核心方法
func (a *AgentLoop) Run(ctx Context, messages []Message) (Response, error)
func (a *AgentLoop) RunStream(...) (<-chan StreamEvent, error)

// 4. 辅助方法
func (a *AgentLoop) callLLM(...) (Response, error)
func (a *AgentLoop) executeTools(...) []Result
func (a *AgentLoop) shouldContinue() bool

// 5. 错误定义
var ErrMaxIterations = errors.New("max iterations reached")
```

---

## 🔬 核心结构

```go
// AgentLoop 结构体
type AgentLoop struct {
    // === 依赖注入 ===
    llm           LLMProvider      // LLM 提供商接口
    tools         *ToolRegistry    // 工具注册表
    
    // === 配置 ===
    model         string           // 模型名称
    temperature   float64          // 温度参数 (0-2)
    maxTokens     int              // 最大输出 token
    maxIterations int              // 最大迭代次数
    
    // === 运行时状态 ===
    currentIteration int           // 当前迭代次数
    startTime       time.Time      // 开始时间
}

// 配置结构
type AgentLoopConfig struct {
    LLM           LLMProvider
    Tools         *ToolRegistry
    Model         string
    Temperature   float64
    MaxTokens     int
    MaxIterations int  // 默认值：10
}
```

**设计要点**:
- 依赖注入（LLM/Tools 通过接口）
- 配置与运行时状态分离
- 无状态设计（每次 Run 都是独立的）

---

## 🚀 核心方法详解

### 1. 构造函数

```go
// NewAgentLoop 创建 AgentLoop 实例
func NewAgentLoop(config AgentLoopConfig) *AgentLoop {
    // 1. 默认值处理
    maxIterations := config.MaxIterations
    if maxIterations <= 0 {
        maxIterations = 10  // 默认最大迭代次数
    }
    
    maxTokens := config.MaxTokens
    if maxTokens <= 0 {
        maxTokens = 4096  // 默认最大输出 token
    }
    
    temperature := config.Temperature
    if temperature < 0 || temperature > 2 {
        temperature = 0.7  // 默认温度
    }
    
    // 2. 创建实例
    return &AgentLoop{
        llm:           config.LLM,
        tools:         config.Tools,
        model:         config.Model,
        temperature:   temperature,
        maxTokens:     maxTokens,
        maxIterations: maxIterations,
        currentIteration: 0,
    }
}
```

**关键点**:
- 防御性编程（默认值处理）
- 参数验证（temperature 范围检查）
- 不可变配置（创建后不再修改）

---

### 2. Run 方法（核心循环）

```go
// Run 执行完整的 Agent 循环
func (a *AgentLoop) Run(ctx Context, messages []Message) (Response, error) {
    // 2.1 初始化运行时状态
    a.currentIteration = 0
    a.startTime = time.Now()
    
    // 2.2 创建消息副本（避免修改原始数据）
    // 这是重要的防御性编程
    workingMessages := make([]Message, len(messages))
    copy(workingMessages, messages)
    
    // 2.3 主循环
    for a.currentIteration < a.maxIterations {
        a.currentIteration++
        
        // 记录迭代开始
        log.Printf("[AgentLoop] Iteration %d/%d", a.currentIteration, a.maxIterations)
        
        // === 步骤 1: 调用 LLM ===
        response, err := a.callLLM(ctx, workingMessages)
        if err != nil {
            return Response{}, fmt.Errorf("iteration %d: LLM call failed: %w", a.currentIteration, err)
        }
        
        // === 步骤 2: 检查是否有工具调用 ===
        if len(response.ToolCalls) == 0 {
            // 没有工具调用，任务完成
            log.Printf("[AgentLoop] No tool calls, returning final answer")
            return response, nil
        }
        
        log.Printf("[AgentLoop] Found %d tool calls", len(response.ToolCalls))
        
        // === 步骤 3: 执行工具调用 ===
        results := a.executeTools(ctx, response.ToolCalls)
        
        // === 步骤 4: 将工具结果添加到消息历史 ===
        for i, result := range results {
            if result.Error != nil {
                log.Printf("[AgentLoop] Tool %s error: %v", response.ToolCalls[i].Name, result.Error)
            }
            
            // 转换为消息格式
            toolMsg := Message{
                Role:       "tool",
                Content:    result.Content,
                ToolCallID: result.ToolCallID,
                Metadata: map[string]any{
                    "success": result.Error == nil,
                },
            }
            workingMessages = append(workingMessages, toolMsg)
        }
        
        // 循环继续，LLM 将看到工具执行结果
    }
    
    // 2.4 达到最大迭代次数
    log.Printf("[AgentLoop] Max iterations (%d) reached", a.maxIterations)
    
    return Response{
        Content: "I reached the maximum number of iterations without completing the task. " +
                  "This might mean the task is too complex or I'm stuck in a loop.",
        Error:   ErrMaxIterations,
        Metadata: map[string]any{
            "iterations":        a.currentIteration,
            "max_iterations":    a.maxIterations,
            "duration_seconds":  time.Since(a.startTime).Seconds(),
        },
    }, nil
}
```

**流程图解**:
```
┌─────────────────────────────────────────────┐
│              AgentLoop.Run()                │
└─────────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  currentIteration = 0 │
        │  workingMessages = [] │
        └───────────┬───────────┘
                    │
          ┌─────────▼─────────┐
          │ currentIteration  │
          │ < maxIterations?  │
          └─────────┬─────────┘
               No  │   Yes
          ┌────────┘   └────────┐
          │                     │
          ▼                     ▼
    ┌──────────┐      ┌─────────────────┐
    │ 返回错误  │      │ currentIteration++│
    └──────────┘      └────────┬────────┘
                               │
                    ┌──────────▼──────────┐
                    │  callLLM(messages)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ ToolCalls 是否为空？ │
                    └──────────┬──────────┘
                         No  │   Yes
                    ┌────────┘   └────────┐
                    │                     │
                    ▼                     ▼
              ┌──────────┐         ┌──────────┐
              │executeTools│        │ 返回响应 │
              └─────┬────┘         └──────────┘
                    │
              ┌─────▼─────┐
              │添加结果到  │
              │messages[] │
              └─────┬─────┘
                    │
                    └──────→ 继续循环
```

**关键设计**:
1. **消息副本**: 避免修改传入的消息切片
2. **迭代计数**: 防止无限循环
3. **错误包装**: 包含迭代次数等上下文信息
4. **日志记录**: 便于调试和监控

---

### 3. callLLM 方法

```go
// callLLM 调用 LLM API
func (a *AgentLoop) callLLM(ctx Context, messages []Message) (Response, error) {
    // 3.1 获取工具定义
    toolDefinitions := a.tools.Definitions()
    
    // 3.2 调用 LLM 提供商
    response, err := a.llm.Call(ctx, LLMRequest{
        Model:       a.model,
        Messages:    messages,
        Tools:       toolDefinitions,
        Temperature: a.temperature,
        MaxTokens:   a.maxTokens,
    })
    
    if err != nil {
        return Response{}, err
    }
    
    // 3.3 验证响应
    if err := a.validateResponse(response); err != nil {
        return Response{}, err
    }
    
    return response, nil
}

// validateResponse 验证 LLM 响应
func (a *AgentLoop) validateResponse(response Response) error {
    // 检查是否有内容或工具调用
    if response.Content == "" && len(response.ToolCalls) == 0 {
        return errors.New("empty response from LLM")
    }
    
    // 验证工具调用
    for _, call := range response.ToolCalls {
        if call.Name == "" {
            return errors.New("tool call missing name")
        }
        
        // 检查工具是否存在
        if a.tools.Get(call.Name) == nil {
            return fmt.Errorf("unknown tool: %s", call.Name)
        }
    }
    
    return nil
}
```

**关键点**:
- 工具定义注入
- 响应验证（防御性编程）
- 错误处理

---

### 4. executeTools 方法

```go
// executeTools 执行所有工具调用
func (a *AgentLoop) executeTools(ctx Context, toolCalls []ToolCall) []Result {
    results := make([]Result, len(toolCalls))
    
    // 4.1 顺序执行（默认）
    // 优点：可预测，易于调试
    // 缺点：工具间无法并行
    for i, call := range toolCalls {
        results[i] = a.executeSingleTool(ctx, call)
    }
    
    return results
}

// executeSingleTool 执行单个工具调用
func (a *AgentLoop) executeSingleTool(ctx Context, call ToolCall) Result {
    startTime := time.Now()
    
    // 4.2 查找工具
    tool := a.tools.Get(call.Name)
    if tool == nil {
        return Result{
            ToolCallID: call.ID,
            Error:      fmt.Errorf("tool not found: %s", call.Name),
        }
    }
    
    // 4.3 执行工具（带 panic 恢复）
    var result Result
    func() {
        defer func() {
            if r := recover(); r != nil {
                result = Result{
                    ToolCallID: call.ID,
                    Error:      fmt.Errorf("tool panic: %v", r),
                    Metadata: map[string]any{
                        "panic": true,
                    },
                }
            }
        }()
        
        result = tool.Execute(ctx, call.Parameters)
        result.ToolCallID = call.ID
    }()
    
    // 4.4 记录执行时间
    duration := time.Since(startTime)
    if result.Metadata == nil {
        result.Metadata = make(map[string]any)
    }
    result.Metadata["execution_time_ms"] = duration.Milliseconds()
    
    log.Printf("[AgentLoop] Tool %s executed in %dms", call.Name, duration.Milliseconds())
    
    return result
}
```

**关键点**:
- Panic 恢复（防止工具崩溃影响主流程）
- 执行时间监控
- 错误不中断流程

---

## 🎯 设计模式分析

### 1. 命令模式 (Command Pattern)

```go
// 工具调用作为命令
type ToolCall struct {
    ID         string
    Name       string
    Parameters map[string]any
}

// 工具作为命令执行者
type Tool interface {
    Execute(ctx Context, params map[string]any) Result
}
```

**优点**:
- 解耦调用者和接收者
- 支持撤销/重做（扩展）
- 易于日志记录和审计

---

### 2. 策略模式 (Strategy Pattern)

```go
// LLM 提供商作为策略
type LLMProvider interface {
    Call(ctx Context, req LLMRequest) (Response, error)
}

// 不同实现
type AnthropicProvider struct{ ... }
type OpenAIProvider struct{ ... }
type QwenProvider struct{ ... }

// 运行时切换
loop.llm = NewAnthropicProvider(config)  // 或
loop.llm = NewOpenAIProvider(config)
```

**优点**:
- 运行时切换算法
- 易于添加新提供商
- 便于测试（Mock）

---

### 3. 模板方法模式 (Template Method Pattern)

```go
// Run 方法定义了算法骨架
func (a *AgentLoop) Run(...) (Response, error) {
    for iteration < max {
        callLLM()           // 步骤 1
        checkToolCalls()    // 步骤 2
        executeTools()      // 步骤 3
        addResults()        // 步骤 4
    }
}
```

**优点**:
- 固定流程结构
- 子类可重写特定步骤
- 代码复用

---

## 📊 性能分析

### 时间复杂度

| 操作 | 复杂度 | 说明 |
|------|--------|------|
| Run | O(n*m) | n=迭代次数，m=工具调用数 |
| callLLM | O(1) | 单次 HTTP 请求 |
| executeTools | O(m) | m=工具调用数 |
| executeSingleTool | O(1) | 单次工具执行 |

### 空间复杂度

| 操作 | 复杂度 | 说明 |
|------|--------|------|
| Run | O(k) | k=消息历史长度 |
| workingMessages | O(k+n*m) | 原始消息 + 工具结果 |

### 优化建议

1. **工具并行执行**
```go
// 当前：顺序执行
for i, call := range toolCalls {
    results[i] = a.executeSingleTool(ctx, call)
}

// 优化：并行执行（工具间无依赖时）
var wg sync.WaitGroup
for i, call := range toolCalls {
    wg.Add(1)
    go func(idx int, call ToolCall) {
        defer wg.Done()
        results[idx] = a.executeSingleTool(ctx, call)
    }(i, call)
}
wg.Wait()
```

2. **消息历史压缩**
```go
// 当前：完整消息历史
workingMessages = append(workingMessages, toolMsg)

// 优化：只保留必要信息
if len(workingMessages) > maxHistory {
    workingMessages = compressHistory(workingMessages)
}
```

---

## 🐛 错误处理

### 错误类型

```go
var (
    ErrMaxIterations  = errors.New("max iterations reached")
    ErrLLMTimeout     = errors.New("LLM call timeout")
    ErrToolNotFound   = errors.New("tool not found")
    ErrInvalidRequest = errors.New("invalid request")
)
```

### 错误包装

```go
// 好的错误处理：包含上下文
response, err := a.callLLM(ctx, workingMessages)
if err != nil {
    return Response{}, fmt.Errorf(
        "iteration %d: LLM call failed: %w",
        a.currentIteration,
        err,
    )
}
```

### Panic 恢复

```go
// 工具执行中的 panic 不会崩溃整个 Agent
func() {
    defer func() {
        if r := recover(); r != nil {
            result = Result{Error: fmt.Errorf("tool panic: %v", r)}
        }
    }()
    result = tool.Execute(...)
}()
```

---

## 🧪 测试要点

### 单元测试

```go
func TestAgentLoop_Run_NoToolCalls(t *testing.T) {
    // 测试 LLM 直接返回答案的场景
    mockLLM := &MockLLM{
        Response: Response{Content: "Hello!"},
    }
    loop := NewAgentLoop(Config{LLM: mockLLM})
    
    response, err := loop.Run(ctx, []Message{userMsg})
    
    assert.NoError(t, err)
    assert.Equal(t, "Hello!", response.Content)
    assert.Equal(t, 1, mockLLM.CallCount)
}

func TestAgentLoop_Run_MaxIterations(t *testing.T) {
    // 测试达到最大迭代次数的场景
    mockLLM := &MockLLM{
        Response: Response{
            ToolCalls: []ToolCall{{Name: "search"}},  // 总是返回工具调用
        },
    }
    loop := NewAgentLoop(Config{
        LLM: mockLLM,
        MaxIterations: 3,
    })
    
    response, err := loop.Run(ctx, []Message{userMsg})
    
    assert.ErrorIs(t, err, ErrMaxIterations)
    assert.Equal(t, 3, mockLLM.CallCount)
}
```

### 集成测试

```go
func TestAgentLoop_Integration(t *testing.T) {
    // 使用真实 LLM API（测试环境）
    llm := NewAnthropicProvider(Config{
        APIKey: os.Getenv("TEST_ANTHROPIC_KEY"),
    })
    tools := NewToolRegistry()
    tools.Register(&SearchTool{})
    
    loop := NewAgentLoop(Config{
        LLM: llm,
        Tools: tools,
        MaxIterations: 5,
    })
    
    response, err := loop.Run(ctx, []Message{
        {Role: "user", Content: "What's the weather in Tokyo?"},
    })
    
    assert.NoError(t, err)
    assert.NotEmpty(t, response.Content)
}
```

---

## 📝 学习总结

### 核心职责
- 执行 LLM 调用循环
- 解析和调度工具调用
- 控制迭代次数防止死循环

### 关键设计
- 命令模式（工具调用）
- 策略模式（LLM 提供商）
- 防御性编程（panic 恢复、参数验证）

### 性能要点
- 消息副本避免副作用
- 工具执行可并行化
- 执行时间监控

### 扩展方向
- 流式响应支持
- 工具并行执行
- 消息历史压缩

---

**相关文档**:
- [AgentInstance 分析](agent-instance.md)
- [ToolRegistry 分析](tool-registry.md)
- [执行流程](../notes/03-execution-flow.md)

最后更新：2026-03-29
