# Multi-Agent 架构稳定性讨论

**来源**: 飞书群聊 `oc_7808579b7b1f6eeb5936f7828e2aaf23`  
**日期**: 2026-03-09 10:15-10:31  
**提问者**: boss（飞书用户 7170NK）  
**整理者**: 小黑 - 管家  
**状态**: ⏳ 待确认  
**标签**: `#architecture` `#best-practice`

---

## 问题描述

用户询问：主 Agent 调用子 Agent（通过 `sessions_spawn` 创建）是否稳定？

**原始对话**:
> "第三排是你自己创建的子 agent，主智能体调用子 agent 是不是不稳定"

---

## 上下文

一人团队 Multi-Agent 系统架构：
- 小黑 - 管家（主 Agent）负责意图识别和路由
- 4 个专业 Agent（Dev/Edu/Wri/Fin）作为子 Agent
- 子 Agent 通过 `sessions_spawn` 动态创建

---

## 问题分析

### 当前架构（一次性会话）

```
小黑 (主 Agent)
  │
  ├─ spawn 子 Agent → 执行 → 销毁 ❌ 状态不保留
  ├─ 长任务可能超时中断
  └─ 错误无自动重试
```

### 潜在不稳定因素

| 问题 | 现状 | 风险等级 |
|------|------|---------|
| **子 Agent 会话超时** | `sessions_spawn` 创建的子会话有超时限制 | ⚠️ 中 |
| **任务执行中断** | 长任务可能被系统回收 | ⚠️ 中 |
| **状态丢失** | 子 Agent 之间不直接通信，依赖小黑中转 | ⚠️ 低 |
| **Gateway 重启** | 配置更新需要重启，会丢失临时状态 | ⚠️ 低 |
| **消息队列堆积** | 多用户并发时可能延迟 | ⚠️ 低 |

### 当前容错机制

1. ✅ **独立 Workspace** - 每个 Agent 有独立配置和记忆，互不影响
2. ✅ **消息去重** - `feishu/dedup/*.json` 防止重复响应
3. ✅ **允许列表** - 每个 Agent 有独立的 `allowFrom` 配置
4. ✅ **工作流记录** - 协作过程记录到 `memory/workflow-*.md`，可追溯

---

## 解决方案对比

### 方案 A：改用持久会话（推荐）

将子 Agent 改为 `mode: "session"` + `thread: true`：

```javascript
sessions_spawn({
  runtime: "subagent",
  mode: "session",  // 持久会话
  thread: true,     // 线程绑定
  label: "dev-agent-session"
})
```

**优点**：
- ✅ 会话持久化，可多次复用
- ✅ 上下文不丢失
- ✅ 支持长期任务

**缺点**：
- ⚠️ 需要管理会话生命周期
- ⚠️ 资源占用更高

---

### 方案 B：增加状态持久化

每次子 Agent 执行后，将关键状态写入文件：

```
memory/agent-states/
├── dev-agent-state.json
├── edu-agent-state.json
├── workflow-current.json
└── workflow-history/
```

**优点**：
- ✅ 重启后可恢复
- ✅ 可追溯历史
- ✅ 实现简单

**缺点**：
- ⚠️ 需要额外的读写逻辑
- ⚠️ 实时性稍差

---

### 方案 C：改用 ACP 运行时

对于需要长期运行的 Agent（如 Dev），使用 `runtime: "acp"`：

```javascript
sessions_spawn({
  runtime: "acp",
  agentId: "claude-code",
  mode: "session",
  thread: true
})
```

**优点**：
- ✅ 更稳定的会话管理
- ✅ 适合代码任务
- ✅ 原生支持文件操作

**缺点**：
- ⚠️ 需要配置 ACP 允许列表
- ⚠️ 依赖外部服务

---

## 推荐实施计划

### 短期（现在）
- ✅ 保持当前架构，先验证功能
- ✅ 增加错误处理和重试机制
- ✅ 添加工作流状态持久化

### 中期（1-2 周）
- ⏳ 核心 Agent（Dev/Edu）改为持久会话
- ⏳ 实现会话管理和复用逻辑
- ⏳ 添加超时告警和自动重试

### 长期（1 个月+）
- ⏳ 评估是否需要消息队列（如 Redis）
- ⏳ 考虑分布式部署（多实例）
- ⏳ 添加监控和日志系统

---

## 代码示例

### 错误处理与重试机制

```javascript
async function callAgent(agentId, task) {
  const maxRetries = 3;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      const result = await sessions_spawn({
        runtime: "subagent",
        mode: "session",
        label: `${agentId}-session`,
        task: task,
        timeoutSeconds: 300
      });
      return result;
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await wait(1000 * (i + 1)); // 指数退避
      logError(agentId, error, i);
    }
  }
}
```

### 会话复用策略

```javascript
// 检查是否有活跃会话
const existingSession = await sessions_list({
  label: "dev-agent-session"
});

if (existingSession.length > 0) {
  // 复用现有会话
  await sessions_send({
    sessionKey: existingSession[0].sessionKey,
    message: task
  });
} else {
  // 创建新会话
  await sessions_spawn({
    runtime: "subagent",
    mode: "session",
    label: "dev-agent-session",
    task: task
  });
}
```

---

## 决策记录

**2026-03-09 决策**: 
- 先保持当前架构，继续测试功能
- 等问题实际出现再针对性优化
- 避免过早优化增加复杂度

---

## 相关问题

- [一人团队 Multi-Agent 系统设计](../design/一人团队-Multi-Agent-系统设计.md)
- [ROUTING.md - 路由规则](../../.openclaw/workspace/ROUTING.md)

---

## 确认事项

- [ ] 问题分析是否准确
- [ ] 解决方案是否完整
- [ ] 是否需要补充代码示例
- [ ] 是否发布到 docs/架构设计/

---

**小黑备注**: 
这是架构设计的重要讨论，建议发布到 docs/ 目录作为设计决策记录。后续实施持久会话改造时可以参考此文档。
