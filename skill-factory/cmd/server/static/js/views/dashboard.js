// Dashboard Tab：stats + 7 天柱图 + 最近任务 + 调度器 + 最近 executions
// 链接/目录/todo widget 已搬到左侧 widget-sidebar (widgets.js)
// 依赖 api.js (fetchJSON/esc/statusTag/fmt)

async function loadDashboard() {
  try {
    const [stats, recent] = await Promise.all([
      fetchJSON(API + '/api/stats'),
      fetchJSON(API + '/api/tasks?limit=5')
    ]);
    document.getElementById('stat-pending').textContent = stats.pending_tasks;
    document.getElementById('stat-in_progress').textContent = stats.in_progress_tasks;
    document.getElementById('stat-archived').textContent = stats.archived_tasks;
    document.getElementById('stat-exception').textContent = stats.exception_tasks;
    renderChart(stats.daily_stats || []);
    renderRecentTasks(recent);
  } catch(e) { console.error(e); }
  // 调度器 + 最近执行（链接/目录/todo 由 widgets.js 独立加载）
  loadScheduler();
  loadScheduledSummary();
  loadRecentExecutions();
}

function renderChart(daily) {
  const el = document.getElementById('chart-bars');
  if (!daily || daily.length === 0) {
    el.innerHTML = '<div class="empty" style="padding:20px">暂无数据</div>';
    return;
  }
  const max = Math.max(...daily.map(d => d.count), 1);
  el.innerHTML = daily.map(d => `
    <div class="bar-wrap">
      <div class="bar" style="height:${(d.count / max) * 80}px"></div>
      <div class="bar-label">${d.date ? d.date.slice(5) : ''}</div>
    </div>
  `).join('');
}

function renderRecentTasks(list) {
  const el = document.getElementById('recent-list');
  if (!list || list.length === 0) {
    el.innerHTML = '<div class="empty">暂无任务</div>';
    return;
  }
  el.innerHTML = `<table>
    <thead><tr><th>标题</th><th>模块</th><th>状态</th><th>时间</th></tr></thead>
    <tbody>${list.map(t => `
      <tr onclick="viewTask('${t.id}')" style="cursor:pointer">
        <td><div class="task-title-cell"><div class="title">${esc(t.title)}</div></div></td>
        <td style="color:var(--text-secondary);font-size:12px">${esc(t.module || '-')}</td>
        <td>${statusTag(t.status)}</td>
        <td style="color:var(--text-secondary);font-size:12px">${fmt(t.created_at)}</td>
      </tr>`).join('')}</tbody>
  </table>`;
}

// ===== 调度器徽章 + 按钮联动（dashboard 顶部） =====
async function loadScheduler() {
  const data = await fetchJSON('/api/scheduler/status');
  const running = !!data.running;
  document.querySelectorAll('#scheduler-badge, #scheduler-badge-2').forEach(el => {
    el.outerHTML = running
      ? '<span id="' + el.id + '" class="scheduler-badge running"><span class="dot green"></span>运行中</span>'
      : '<span id="' + el.id + '" class="scheduler-badge stopped"><span class="dot gray"></span>已停止</span>';
  });
  // 同步 3 个按钮状态
  document.querySelectorAll('[data-sched-action]').forEach(btn => {
    const act = btn.dataset.schedAction;
    if (act === 'start') {
      btn.disabled = running;
      btn.textContent = running ? '✓ 已运行' : '启动';
    } else if (act === 'stop') {
      btn.disabled = !running;
      btn.textContent = running ? '停止' : '已停止';
    }
  });
}
function schedulerStart() { fetch('/api/scheduler/start', {method:'POST'}).then(() => { loadScheduler(); loadScheduledSummary(); }); }
function schedulerStop() { fetch('/api/scheduler/stop', {method:'POST'}).then(() => { loadScheduler(); }); }
function schedulerReload() { fetch('/api/scheduler/reload', {method:'POST'}).then(() => { loadScheduledSummary(); loadScheduled(); }); }
