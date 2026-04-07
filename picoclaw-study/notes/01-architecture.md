# PicoClaw 架构解析

> 🏗️ 深入理解 PicoClaw 的整体架构和设计哲学

**学习时间**: 2026-03-29  
**参考版本**: PicoClaw v1.x (Go 实现)

---

## 🎯 定位与特点

### 什么是 PicoClaw？

PicoClaw 是 OpenClaw 生态中的**超轻量级 AI Agent 框架**，用 Go 从头重写，专为资源受限环境设计。

### 核心特点

| 特点 | 说明 | 优势 |
|------|------|------|
| **极简** | 代码量仅为 OpenClaw 的 1% | 易于理解和维护 |
| **轻量** | 内存占用 < 10MB | 可运行在边缘设备 |
| **快速** | 启动时间 < 1 秒 | 即时响应 |
| **独立** | 单二进制部署 | 无需运行时依赖 |
| **灵活** | 支持多 LLM 提供商 | 适配不同需求 |

### 与 OpenClaw 对比

```
┌─────────────────────────────────────────────────────────────┐
│                     OpenClaw                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Gateway    │  │   Skills    │  │   Memory    │         │
│  │ (TypeScript)│  │  (Plugin)   │  │  (Vector)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  内存：1.5GB+  |  启动：~9 分钟  |  部署：npm + node        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     PicoClaw                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Single Go Binary (~5MB)                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │  Agent   │ │  Tools   │ │ Gateway  │            │   │
│  │  │  Loop    │ │ Registry │ │ (HTTP)   │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  └─────────────────────────────────────────────────────┘   │
│  内存：<10MB  |  启动：<1 秒  |  部署：单二进制             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 整体架构

### 架构图

```
┌────────────────────────────────────────────────────────────────┐
│                        Client Channels                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │ Telegram  │  │  Discord  │  │   Slack   │  │   HTTP    │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        │              │              │              │          │
│        └──────────────┴──────────────┴──────────────┘          │
│                              │                                 │
│                              ▼                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    PicoClaw Gateway                       │ │
│  │  ┌─────────────────────────────────────────────────────┐  │ │
│  │  │              Channel Adapter Layer                  │  │ │
│  │  │   (统一消息格式转换：Platform Message → Internal)      │  │ │
│  │  └─────────────────────────────────────────────────────┘  │ │
│  │                            │                              │ │
│  │                            ▼                              │ │
│  │  ┌─────────────────────────────────────────────────────┐  │ │
│  │  │              AgentInstance Manager                  │  │ │
│  │  │   (会话管理：创建/销毁/状态维护)                        │  │ │
│  │  └─────────────────────────────────────────────────────┘  │ │
│  │                            │                              │ │
│  │          ┌─────────────────┼─────────────────┐            │ │
│  │          ▼                 ▼                 ▼            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │ │
│  │  │ AgentInstance│  │ AgentInstance│  │ AgentInstance│     │ │
│  │  │    #1        │  │    #2        │  │    #3        │     │ │
│  │  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │     │ │
│  │  │  │AgentLoop│ │  │  │AgentLoop│ │  │  │AgentLoop│ │     │ │
│  │  │  └────┬───┘  │  │  └────┬───┘  │  │  └────┬───┘  │     │ │
│  │  └───────┼──────┘  └───────┼──────┘  └───────┼──────┘     │ │
│  │          │                 │                 │            │ │
│  └──────────┼─────────────────┼─────────────────┼────────────┘ │
│             │                 │                 │              │
│             └─────────────────┼─────────────────┘              │
│                               │                                │
│                               ▼                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    Tool Registry                          │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │ │
│  │  │ Search  │ │  File   │ │  Shell  │ │ Custom  │ ...      │ │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                               │                                │
│                               ▼                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                   LLM Providers                           │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│  │  │  Anthropic  │  │   OpenAI    │  │   Qwen      │        │ │
│  │  │  (Claude)   │  │   (GPT)     │  │ (Aliyun)    │        │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔧 核心组件

### 1. Gateway（网关）

**职责**: 多通道集成服务器

```go
// 核心功能
type Gateway struct {
    server      *http.Server      // HTTP 服务器
    channels    map[string]Channel // 已注册的通道
    instances   map[string]*AgentInstance // 会话实例
}

// 主要方法
func (g *Gateway) Start()                    // 启动服务器
func (g *Gateway) RegisterChannel(c Channel) // 注册通道
func (g *Gateway) routeMessage(msg Message)  // 消息路由
```

**关键特性**:
- 支持 WebSocket 和 HTTP 长轮询
- 消息格式统一转换
- 会话路由和负载均衡
- 健康检查端点 (`/health`)

---

### 2. AgentInstance（代理实例）

**职责**: 单个会话的生命周期管理

```go
type AgentInstance struct {
    id          string           // 会话 ID
    config      AgentConfig      // 配置
    loop        *AgentLoop       // 执行引擎
    context     Context          // 上下文
    state       State            // 状态
    messageHistory []Message     // 消息历史
}

// 主要方法
func NewAgentInstance(config Config) *AgentInstance  // 创建实例
func (a *AgentInstance) ProcessMessage(msg Message)  // 处理消息
func (a *AgentInstance) GetContext() Context         // 获取上下文
func (a *AgentInstance) Close()                       // 关闭实例
```

**关键特性**:
- 独立的上下文维护
- 消息历史管理
- 资源清理

---

### 3. AgentLoop（代理循环）

**职责**: LLM 调用和工具执行的核心循环

```go
type AgentLoop struct {
    llm           LLMProvider      // LLM 提供商
    tools         *ToolRegistry    // 工具注册表
    maxIterations int              // 最大迭代次数
}

// 核心方法
func (a *AgentLoop) Run(input Message) Response {
    messages := []Message{input}
    
    for iteration := 0; iteration < a.maxIterations; iteration++ {
        // 1. 调用 LLM
        response := a.llm.Call(messages, a.tools.Definitions())
        
        // 2. 检查是否有工具调用
        if len(response.ToolCalls) == 0 {
            return response // 返回最终答案
        }
        
        // 3. 执行工具
        for _, toolCall := range response.ToolCalls {
            result := a.tools.Execute(toolCall)
            messages = append(messages, result.ToMessage())
        }
    }
    
    return Response{Error: "max iterations reached"}
}
```

**执行流程**:
```
输入消息
    │
    ▼
┌─────────────┐
│  调用 LLM   │
│ (消息 + 工具)│
└──────┬──────┘
       │
       ▼
  有工具调用？
   ╱     ╲
  否      是
  │       │
  │       ▼
  │  ┌─────────────┐
  │  │  执行工具   │
  │  └──────┬──────┘
  │         │
  │         ▼
  │    添加结果到消息
  │         │
  └────────┘
       │
       ▼
  达到最大迭代？
   ╱     ╲
  是      否
  │       │
  ▼       └──→ 继续循环
返回结果
```

---

### 4. ToolRegistry（工具注册表）

**职责**: 工具的注册、发现和執行

```go
// 工具接口
type Tool interface {
    Name() string
    Description() string
    Parameters() map[string]ParameterSchema
    Execute(ctx Context, params map[string]any) (Result, error)
}

// 注册表
type ToolRegistry struct {
    mu    sync.RWMutex          // 并发控制
    tools map[string]Tool       // 工具映射
}

// 主要方法
func (t *ToolRegistry) Register(tool Tool)           // 注册工具
func (t *ToolRegistry) Get(name string) Tool         // 获取工具
func (t *ToolRegistry) Definitions() []ToolDef       // 获取 LLM 工具定义
func (t *ToolRegistry) Execute(call ToolCall) Result // 执行工具
```

**内置工具**:
- `search` - 网络搜索
- `file_read` - 文件读取
- `file_write` - 文件写入
- `shell` - 命令执行
- `http_request` - HTTP 请求

---

## 🔄 数据流

### 一次完整请求的处理流程

```
1. 用户发送消息 (Telegram/Discord/HTTP)
         │
         ▼
2. Gateway 接收并转换格式
         │
         ▼
3. 查找/创建 AgentInstance
         │
         ▼
4. AgentInstance 调用 AgentLoop.Run()
         │
         ▼
5. AgentLoop 执行循环:
   ┌──────────────────────────────┐
   │ 5.1 调用 LLM (消息 + 工具定义) │
   │         │                    │
   │         ▼                    │
   │ 5.2 解析响应                 │
   │         │                    │
   │    有工具调用？───否──→ 返回结果
   │         │ 是                 │
   │         ▼                    │
   │ 5.3 执行工具                 │
   │         │                    │
   │         ▼                    │
   │ 5.4 添加结果到消息历史        │
   │         │                    │
   │         └──────→ 继续循环    │
   └──────────────────────────────┘
         │
         ▼
6. 返回最终响应给用户
```

---

## 🎨 设计哲学

### 1. 极简主义 (Minimalism)

> "代码量控制在 OpenClaw 的 1%"

- 去掉所有不必要的抽象层
- 直接使用标准库（`net/http`, `encoding/json`）
- 避免过度工程化

### 2. 本地优先 (Local-First)

> "可在无网络环境下运行（配合本地 LLM）"

- 支持本地 LLM（Ollama、LM Studio）
- 本地状态持久化
- 离线可用

### 3. 实用主义 (Pragmatism)

> "去掉 LangChain 等抽象层，直接调用 API"

- 直接 HTTP 调用 LLM API
- 简单的接口定义
- 易于调试和理解

### 4. 嵌入式友好 (Embedded-Friendly)

> "运行在 $10 的 RISC-V 开发板上"

- 低内存占用 (< 10MB)
- 快速启动 (< 1 秒)
- 交叉编译支持

---

## 📊 性能指标

| 指标 | PicoClaw | OpenClaw | 提升 |
|------|----------|----------|------|
| 启动时间 | < 1s | ~540s | 540x |
| 内存占用 | < 10MB | ~1500MB | 150x |
| 二进制大小 | ~5MB | ~200MB (node_modules) | 40x |
| CPU 需求 | 0.6GHz | 2.0GHz+ | 3x |

---

## 🔍 关键代码位置

| 组件 | 文件路径 | 行数 |
|------|---------|------|
| AgentLoop | `pkg/agent/loop.go` | ~200 |
| AgentInstance | `pkg/agent/instance.go` | ~150 |
| ToolRegistry | `pkg/tools/registry.go` | ~100 |
| Gateway | `cmd/gateway/main.go` | ~300 |
| **总计** | | **~750** |

---

## 📝 学习要点

### 重点理解
1. AgentLoop 的循环逻辑
2. 工具调用的解析和执行
3. 消息格式的统一转换
4. 并发控制和资源管理

### 难点突破
1. 多通道消息格式差异处理
2. 流式响应的实现
3. 会话状态的持久化
4. 错误处理和恢复

---

**下一篇**: [02-核心组件.md](02-core-components.md)

最后更新：2026-03-29
