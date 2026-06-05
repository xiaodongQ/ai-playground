# Skill Factory UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `cmd/server/index.html` 重写为极简科技风界面，包含 Dashboard / 任务 / 经验库 / 自动化四页，以及模态框交互。

**Architecture:** 单文件 HTML + 内联 CSS + 内联 JS，无构建步骤。后端 API (main.go) 无需改动，前端通过同源 fetch 调用已有 REST API。

**Tech Stack:** 原生 HTML/CSS/JS，无外部依赖，无图表库（柱状图用 CSS flex 实现）

---

## 文件结构

- **修改:** `skill-factory/cmd/server/index.html` — 完整重写，替换原有粗糙实现

---

## Task 1: 编写完整的 index.html（极简科技风）

**文件:**
- Modify: `skill-factory/cmd/server/index.html`

- [ ] **Step 1: 备份并重写整个 index.html**

完整重写文件，包含以下全部内容：

### CSS 变量与全局样式
```css
:root {
  --bg: #f8fafc;
  --card: #ffffff;
  --border: #e2e8f0;
  --primary: #2563eb;
  --success: #16a34a;
  --warning: #ca8a04;
  --danger: #dc2626;
  --text: #1e293b;
  --muted: #94a3b8;
  --hover: #f1f5f9;
  --radius: 4px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  min-height: 100vh;
}
```

### 整体布局
```html
<div class="app">
  <!-- 左侧边栏 160px -->
  <aside class="sidebar">
    <div class="logo">⚙️ <span>Skill Factory</span></div>
    <div class="logo-sub">自动化开发工厂</div>
    <nav>
      <div class="nav-item active" data-tab="dashboard">📊 总览</div>
      <div class="nav-item" data-tab="tasks">📋 任务</div>
      <div class="nav-item" data-tab="experiences">📚 经验库</div>
      <div class="nav-item" data-tab="automation">⚡ 自动化</div>
    </nav>
    <div class="sidebar-footer">⚙️ 设置</div>
  </aside>
  <!-- 主内容区 -->
  <main class="main"></main>
</div>
```

### 侧边栏样式
```css
.sidebar {
  width: 160px;
  background: var(--card);
  border-right: 1px solid var(--border);
  position: fixed;
  top: 0; left: 0; bottom: 0;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
}
.logo { padding: 0 16px 4px; font-size: 14px; font-weight: 600; }
.logo-sub { padding: 0 16px 20px; font-size: 11px; color: var(--muted); }
.nav-item {
  padding: 10px 16px;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: color .15s;
}
.nav-item:hover { color: var(--text); }
.nav-item.active {
  color: var(--primary);
  border-left-color: var(--primary);
  font-weight: 500;
}
.sidebar-footer {
  margin-top: auto;
  padding: 10px 16px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}
```

### 主内容区样式
```css
.main {
  margin-left: 160px;
  padding: 28px;
  min-height: 100vh;
}
```

### Dashboard 页面（统计卡片 + 柱状图 + 任务列表）
- 4 个 StatCard 网格布局（pending/in_progress/archived/exception）
- StatCard 样式：白色卡片 + 1px border + 4px radius + 20px padding，数字用对应状态色
- 柱状图：6 根柱子用 CSS flex 实现，橙色渐变
- 最新任务列表：状态色圆点 + 标题 + 模块 + 时间 + StatusPill

### 任务页（工具栏 + 表格）
- 工具栏：状态下拉筛选 + 新建按钮
- 表格列：标题 / 状态 / 版本 / 创建时间 / 操作（查看/认领/归档）
- 操作按钮小尺寸样式

### 经验库页（搜索 + 表格）
- 工具栏：模块搜索框 + 添加按钮
- 表格列：模块 / 关键词 / 适用场景 / 操作（查看/删除）

### 自动化页（占位）
- 简单居中文字「自动化执行面板开发中」

###模态框（任务 + 经验）
- 覆盖层 `position:fixed;inset:0;background:rgba(0,0,0,0.5)`
- 弹窗 `background:#fff;border-radius:16px;padding:28px;max-width:600px`
- fade-in 动画
- 任务模态框字段：标题* / 描述 / 关联经验ID / 模块 / 资源链接 / 验收标准
- 经验模态框字段：模块* / 关键词 / 日志路径 / 工具命令 / 适用场景 / 日志样例 / 代码片段

### StatusPill 样式
```css
.status-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 500;
}
.status-pending { background: rgba(202,138,4,0.1); color: var(--warning); }
.status-in_progress { background: rgba(37,99,235,0.1); color: var(--primary); }
.status-archived { background: rgba(22,163,74,0.1); color: var(--success); }
.status-exception { background: rgba(220,38,38,0.1); color: var(--danger); }
```

### JavaScript 逻辑
- `switchTab(tab)` — 切换页面显示
- `loadDashboard()` — 加载统计数据 + 最近任务
- `loadTasks()` — 按状态筛选加载任务列表
- `loadExps()` —搜索加载经验列表
- `renderTaskTable(list)` — 渲染任务表格
- `renderExpTable(list)` — 渲染经验表格
- `showTaskModal(task?)` — 打开任务模态框（新建或详情）
- `showExpModal(exp?)` — 打开经验模态框（添加或详情）
- `submitTask()` — POST /api/tasks
- `submitExp()` — POST /api/experiences
- `claimTask(id)` — PUT /api/tasks/:id/status → in_progress
- `archiveTask(id)` — PUT /api/tasks/:id/status → archived
- `deleteExp(id)` — DELETE /api/experiences/:id
- 工具函数：`fetchJSON()`, `esc()`, `fmt()`, `debounce()`, `statusTag()`

### API 基础路径
```js
const API = ''; // 同源，生产环境通过 reverse proxy 代理
```

- [ ] **Step 2: 编译并启动服务**

```bash
cd /Users/xd/Documents/workspace/repo/ai-playground/skill-factory
go build -o /tmp/skill-factory ./cmd/server/
/tmp/skill-factory &
sleep 1
```

- [ ] **Step 3: 验证页面加载正常**

```bash
curl -s http://localhost:8080/ | head -5
# 期望输出: <!DOCTYPE html>...
curl -s http://localhost:8080/api/stats
# 期望输出: {"total_tasks":...,...}
```

- [ ] **Step 4: 提交**

```bash
git add skill-factory/cmd/server/index.html
git commit -m "feat(skill-factory): redesign UI with 极简科技风

- 侧边栏 160px 固定，纯白 + 细线边框
- Dashboard: 统计卡片 + 趋势柱状图 + 最新任务列表
- 任务页: 筛选工具栏 + 任务表格 + 模态框
- 经验库页: 搜索 + 表格 + 模态框
- 自动化页: 占位页面
- 单文件 HTML，无外部依赖

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 自检清单

- [ ] spec 2.1 背景色 #f8fafc ✓
- [ ] spec 2.1 侧边栏纯白 + 右边框分隔 ✓
- [ ] spec 2.1 主色调 #2563eb ✓
- [ ] spec 2.1 圆角 4px ✓
- [ ] spec 3.2 侧边栏宽度 160px ✓
- [ ] spec 4.1 Dashboard 统计卡片 + 柱状图 + 任务列表 ✓
- [ ] spec 4.2 任务表格 + 筛选 +模态框 ✓
- [ ] spec 4.3 经验库表格 + 搜索 + 模态框 ✓
- [ ] spec 4.4 自动化占位页 ✓
- [ ] spec 5 StatusPill 四色 ✓
- [ ] spec 5 Modal fade-in 动画 ✓
- [ ] spec 6 无 Google Fonts ✓
- [ ] spec 6 柱状图用 CSS flex 实现 ✓