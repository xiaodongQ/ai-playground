// Automation Tab：scheduler 启停 + 定时任务列表 + scheduled modal + 最近 executions
// 依赖 api.js

async function loadAutomation() {
  loadScheduler();
  loadScheduled();
  loadRecentExecutions();
}

async function loadScheduledSummary() {
  const list = await fetchJSON('/api/scheduled');
  const el = document.getElementById('scheduled-summary');
  if (!list || list.length === 0) {
    el.innerHTML = '<div style="color:var(--text-secondary);font-size:12px">暂无定时任务</div>';
    return;
  }
  el.innerHTML = list.slice(0, 5).map(s => {
    const status = s.last_status || 'pending';
    return `<div class="scheduled-item" onclick="runScheduled('${s.id}')" title="点击立即触发">
      <span class="s-name">${esc(s.name)}</span>
      <span class="s-cron">${esc(s.cron_expr)}</span>
      <span class="s-status ${status}">${status}</span>
    </div>`;
  }).join('');
}

async function loadScheduled() {
  const list = await fetchJSON('/api/scheduled');
  const el = document.getElementById('scheduled-list');
  if (!list || list.length === 0) {
    el.innerHTML = '<div style="color:var(--text-secondary);font-size:13px;text-align:center;padding:40px 0">暂无定时任务<br><br><span style="font-size:12px">点击右上"+ 新建定时任务"创建<br>支持标准 cron 5 字段 或 @every 30s</span></div>';
    return;
  }
  el.innerHTML = `<table><thead><tr><th>名称</th><th>Cron</th><th>类型</th><th>状态</th><th>最近执行</th><th>操作</th></tr></thead><tbody>` + list.map(s => {
    const lastRun = s.last_run_at ? new Date(s.last_run_at).toLocaleString() : '-';
    const status = s.last_status || 'pending';
    return `<tr>
      <td><strong>${esc(s.name)}</strong>${s.enabled ? '' : ' <span style="color:var(--text-secondary);font-size:11px">(已禁用)</span>'}</td>
      <td><code>${esc(s.cron_expr)}</code></td>
      <td>${esc(s.command_type)}${s.model?' / '+esc(s.model):''}</td>
      <td><span class="s-status ${status}">${status}</span></td>
      <td style="font-size:11px;color:var(--text-secondary)">${lastRun}</td>
      <td>
        <button class="btn btn-small" onclick="runScheduled('${s.id}')">▶ 跑</button>
        <button class="btn btn-small" onclick="deleteScheduled('${s.id}')">删除</button>
      </td>
    </tr>`;
  }).join('') + '</tbody></table>';
}

function showScheduledModal() {
  document.getElementById('sched-name').value = '';
  document.getElementById('sched-cron').value = '@every 30s';
  document.getElementById('sched-type').value = 'shell';
  document.getElementById('sched-model').value = '';
  document.getElementById('sched-prompt').value = '';
  document.getElementById('sched-enabled').checked = true;
  document.getElementById('scheduled-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('sched-name').focus(), 50);
}
function closeScheduledModal() { document.getElementById('scheduled-modal').classList.add('hidden'); }
function submitScheduled() {
  const name = document.getElementById('sched-name').value.trim();
  const cron = document.getElementById('sched-cron').value.trim();
  const type = document.getElementById('sched-type').value;
  const model = document.getElementById('sched-model').value.trim();
  const promptText = document.getElementById('sched-prompt').value.trim();
  const enabled = document.getElementById('sched-enabled').checked;
  if (!name || !cron || !promptText) { alert('名称、Cron、Prompt 必填'); return; }
  fetch('/api/scheduled', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name, cron_expr:cron, command_type:type, prompt:promptText, model, enabled})})
    .then(() => { closeScheduledModal(); loadScheduled(); loadScheduledSummary(); });
}
function runScheduled(id) {
  fetch('/api/scheduled/' + id + '/run-now', {method:'POST'})
    .then(() => { setTimeout(() => { loadScheduled(); loadRecentExecutions(); }, 500); });
}
function deleteScheduled(id) {
  if (!confirm('删除该定时任务？')) return;
  fetch('/api/scheduled/' + id, {method:'DELETE'}).then(() => { loadScheduled(); loadScheduledSummary(); });
}

let recentExecLimit = 10;
async function loadRecentExecutions() {
  const render = (target, list, errMsg) => {
    if (errMsg) {
      target.innerHTML = `<div style="padding:8px;color:var(--exception);font-size:12px">⚠ ${errMsg} <button class="btn btn-small" style="margin-left:8px" onclick="loadRecentExecutions()">重试</button></div>`;
      return;
    }
    if (!list || list.length === 0) {
      target.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;padding:8px">暂无执行</div>'
        + `<div style="padding:8px;text-align:center"><button class="btn btn-small" onclick="loadMoreExecutions()">📥 加载更多 (尝试加载 ${recentExecLimit} 条)</button></div>`;
      return;
    }
    const atEnd = list.length < recentExecLimit;
    target.innerHTML = list.map(e => {
      const dt = new Date(e.started_at).toLocaleTimeString();
      const src = e.source === 'scheduled' ? '⏰' : '▶';
      const ok = e.exit_code === 0;
      return `<div style="display:flex;gap:8px;padding:6px 8px;border-bottom:1px solid var(--border);font-size:12px;align-items:center">
        <span title="${e.source}">${src}</span>
        <span style="color:var(--text-secondary);font-family:monospace">${dt}</span>
        <span style="flex:1;font-family:monospace;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;text-decoration:underline dotted" onclick="viewExecutionDetail('${e.id}')" title="点击查看详情">${esc(e.command)}</span>
        <span style="font-size:11px;color:${ok?'var(--archived)':'var(--exception)'}" title="exit_code=${e.exit_code}">${ok?'✓':('✗ '+e.exit_code)}</span>
        <button class="btn btn-small" onclick="viewExecutionDetail('${e.id}')" title="查看详情">📋</button>
        <button class="btn btn-small" onclick="runEvaluation('${e.id}')" title="AI 评估 (调 claude 打分 0-10)">📊</button>
      </div>`;
    }).join('') + `<div style="padding:8px;text-align:center;color:var(--text-secondary);font-size:11px">
        当前显示 ${list.length} 条（请求 ${recentExecLimit} 条）
        ${atEnd ? ' · 已到末尾' : `<button class="btn btn-small" data-exec-loadmore style="margin-left:8px" onclick="loadMoreExecutions()">📥 加载更多 (+50)</button>`}
      </div>`;
  };
  const el = document.getElementById('recent-execs');
  const el2 = document.getElementById('exec-list');
  let list, errMsg;
  try {
    list = await fetchJSON('/api/executions?limit=' + recentExecLimit);
  } catch (e) {
    console.error('[loadRecentExecutions]', e);
    errMsg = '加载失败：' + (e.message || e);
  }
  if (el) render(el, list, errMsg);
  if (el2) render(el2, list, errMsg);
}

function loadMoreExecutions() {
  recentExecLimit += 50;
  // 给所有"加载更多"按钮加 loading 反馈（innerHTML 重渲染前）
  document.querySelectorAll('[data-exec-loadmore]').forEach(b => {
    b.disabled = true; b.textContent = '⏳ 加载中...';
  });
  loadRecentExecutions();
}

// ===== Execution 详情 + 评估 =====
let currentExecId = null;

async function viewExecutionDetail(id) {
  currentExecId = id;
  try {
    const exec = await fetchJSON('/api/executions/' + id);
    document.getElementById('exec-detail-cmd').value = exec.command || '';
    document.getElementById('exec-detail-output').value = exec.output || '(无输出)';
    document.getElementById('exec-detail-error').value = exec.error || '';
    const ok = exec.exit_code === 0;
    const dur = exec.completed_at && exec.started_at
      ? Math.round((new Date(exec.completed_at) - new Date(exec.started_at)) / 100) / 10 + 's'
      : '-';
    document.getElementById('exec-detail-meta').innerHTML =
      `<b>${esc(exec.source)}</b> · exit_code=<b style="color:${ok?'var(--archived)':'var(--exception)'}">${exec.exit_code}</b> · ${esc(new Date(exec.started_at).toLocaleString())} · 耗时 ${dur}`;
    document.getElementById('exec-detail-eval').innerHTML = '<span style="color:var(--text-secondary);font-size:12px">评估中？点下方"📊 AI 评估"按钮调 LLM 给这次执行打分</span>';
    // 拉已有评估
    try {
      const evals = await fetchJSON('/api/executions/' + id + '/evaluations');
      if (evals && evals.length > 0) renderEvalCard(evals[0]);
    } catch (e) { /* 忽略 */ }
    document.getElementById('exec-detail-modal').classList.remove('hidden');
  } catch (e) {
    alert('加载执行详情失败：' + e.message);
  }
}

function closeExecDetailModal() {
  document.getElementById('exec-detail-modal').classList.add('hidden');
  currentExecId = null;
}

function renderEvalCard(ev) {
  const score = ev.score;
  const color = score >= 8 ? 'var(--archived)' : score >= 5 ? 'var(--warning)' : 'var(--exception)';
  document.getElementById('exec-detail-eval').innerHTML = `
    <div style="font-size:13px">
      📊 AI 评估: <b style="color:${color};font-size:18px">${score}/10</b>
      <span style="color:var(--text-secondary);font-size:11px;margin-left:8px">${esc(ev.evaluator_model || '')} · ${esc(new Date(ev.created_at).toLocaleString())}</span>
    </div>
    ${ev.comments ? `<div style="margin-top:6px;color:var(--text-secondary);font-size:12px">${esc(ev.comments)}</div>` : ''}
  `;
}

async function runEvaluation(id) {
  const execId = id || currentExecId;
  if (!execId) { alert('请先打开一条执行'); return; }
  const btn = event && event.target;
  const oldText = btn && btn.textContent;
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    await fetchJSON('/api/executions/' + execId + '/evaluate', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{"model":"haiku"}'});
    // 轮询拿结果（评估异步执行，最长 3 分钟）
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000));
      const evals = await fetchJSON('/api/executions/' + execId + '/evaluations');
      if (evals && evals.length > 0) {
        if (currentExecId === execId) renderEvalCard(evals[0]);
        // 刷新列表（评分可能影响渲染）
        loadRecentExecutions();
        return;
      }
    }
    alert('评估超时（>2 分钟），请检查 claude CLI 是否可用');
  } catch (e) {
    alert('评估失败：' + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = oldText; }
  }
}
