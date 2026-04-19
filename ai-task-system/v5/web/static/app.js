/**
 * AI Task System Web UI - 前端逻辑
 */

// API 配置
const API_BASE = '';  // 直接使用根路径，如 /tasks, /health 等
const WS_BASE = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;

// API 封装
const api = {
  // 获取任务列表
  async getTasks(status = null) {
    const url = status ? `${API_BASE}/tasks?status=${status}` : `${API_BASE}/tasks`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // 获取单个任务
  async getTask(id) {
    const res = await fetch(`${API_BASE}/tasks/${id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // 创建任务
  async createTask(data) {
    const res = await fetch(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // 路由决策
  async route(prompt) {
    const res = await fetch(`${API_BASE}/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // 获取队列统计
  async getQueueMetrics() {
    const res = await fetch(`${API_BASE}/queue/metrics`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // 健康检查
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }
};

// WebSocket 连接管理
class WebSocketClient {
  constructor() {
    this.ws = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${WS_BASE}/api/v1/ws`);
      
      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onerror = (e) => {
        console.error('WebSocket error:', e);
        reject(e);
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        this.attemptReconnect();
      };

      this.ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          this.emit(msg.type, msg);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };
    });
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnect attempts reached');
      return;
    }
    
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => this.connect(), delay);
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (!this.listeners.has(event)) return;
    const callbacks = this.listeners.get(event);
    const index = callbacks.indexOf(callback);
    if (index > -1) callbacks.splice(index, 1);
  }

  emit(event, data) {
    if (!this.listeners.has(event)) return;
    this.listeners.get(event).forEach(cb => cb(data));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// 全局 WebSocket 实例
let wsClient = null;

// 初始化 WebSocket
async function initWebSocket() {
  wsClient = new WebSocketClient();
  try {
    await wsClient.connect();
    return wsClient;
  } catch (e) {
    console.error('Failed to connect WebSocket:', e);
    return null;
  }
}

// 工具函数
function formatTime(timestamp) {
  if (!timestamp) return '-';
  const date = new Date(timestamp * 1000);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function formatDuration(start, end) {
  if (!start) return '-';
  const endTime = end || Date.now() / 1000;
  const duration = endTime - start;
  if (duration < 60) return `${duration.toFixed(1)}s`;
  if (duration < 3600) return `${Math.floor(duration / 60)}m ${(duration % 60).toFixed(0)}s`;
  return `${Math.floor(duration / 3600)}h ${Math.floor((duration % 3600) / 60)}m`;
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 任务状态格式化
function formatStatus(status) {
  const statusMap = {
    'pending': { text: '等待中', class: 'pending' },
    'running': { text: '执行中', class: 'running' },
    'done': { text: '已完成', class: 'done' },
    'failed': { text: '失败', class: 'failed' },
    'dequeued': { text: '已出队', class: 'running' },
    'dead': { text: '死信', class: 'failed' }
  };
  return statusMap[status] || { text: status, class: 'pending' };
}

// 渲染任务列表
function renderTaskList(tasks, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!tasks || tasks.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="icon">📋</div>
        <h3>暂无任务</h3>
        <p>创建第一个任务开始体验</p>
      </div>
    `;
    return;
  }

  container.innerHTML = tasks.map(task => {
    const status = formatStatus(task.status);
    return `
      <div class="task-card" onclick="location.href='/task/${task.task_id || task.id}'">
        <div class="task-status ${status.class}"></div>
        <div class="task-info">
          <div class="task-prompt">${escapeHtml(task.prompt || task.payload?.prompt || '-')}</div>
          <div class="task-meta">
            <span class="task-agent">${escapeHtml(task.agent || 'unknown')}</span>
            <span>${status.text}</span>
          </div>
        </div>
        <div class="task-time">${formatTime(task.created_at || task.createdAt)}</div>
      </div>
    `;
  }).join('');
}

// 渲染统计卡片
function renderStats(metrics, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const stats = {
    pending: 0,
    running: 0,
    done: 0,
    failed: 0
  };

  if (metrics) {
    metrics.forEach(m => {
      const status = m.status?.toLowerCase();
      if (stats.hasOwnProperty(status)) {
        stats[status] = m.count;
      }
    });
  }

  container.innerHTML = `
    <div class="stat-card">
      <div class="label">等待中</div>
      <div class="value pending">${stats.pending}</div>
    </div>
    <div class="stat-card">
      <div class="label">执行中</div>
      <div class="value running">${stats.running}</div>
    </div>
    <div class="stat-card">
      <div class="label">已完成</div>
      <div class="value done">${stats.done}</div>
    </div>
    <div class="stat-card">
      <div class="label">失败</div>
      <div class="value failed">${stats.failed}</div>
    </div>
  `;
}

// 输出格式化
function formatOutput(text) {
  if (!text) return '';
  return escapeHtml(text);
}

// 滚动到底部
function scrollToBottom(element) {
  element.scrollTop = element.scrollHeight;
}
