// Widget 侧栏（左侧常驻）：链接（列表）/ 目录 / 待办
// 链接：每行一条；目录：打开失败弹错误；待办：支持增删
// 依赖 api.js (fetchJSON/esc)

// ===== 链接（列表样式：每行一条） =====
async function loadLinks() {
  const list = await fetchJSON('/api/web-links');
  const grid = document.getElementById('links-grid');
  if (!list || list.length === 0) {
    grid.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;text-align:center;padding:20px 0">点击 + 添加你的第一个链接</div>';
    return;
  }
  grid.innerHTML = list.map(l => {
    const initial = (l.name || '?')[0].toUpperCase();
    const icon = l.icon_url
      ? `<img src="${esc(l.icon_url)}" onerror="this.outerHTML='${initial}'">`
      : initial;
    return `<div class="link-row" onclick="window.open('${esc(l.url)}','_blank')" title="${esc(l.url)}">
      <div class="link-icon">${icon}</div>
      <div class="link-text">
        <div class="link-name">${esc(l.name)}</div>
        <div class="link-url">${esc(l.url)}</div>
      </div>
      <div class="link-del" onclick="event.stopPropagation();deleteLink('${l.id}')">×</div>
    </div>`;
  }).join('');
}

function showLinkModal() {
  document.getElementById('link-name').value = '';
  document.getElementById('link-url').value = '';
  document.getElementById('link-icon').value = '';
  document.getElementById('link-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('link-name').focus(), 50);
}
function closeLinkModal() { document.getElementById('link-modal').classList.add('hidden'); }
function submitLink() {
  const name = document.getElementById('link-name').value.trim();
  const url = document.getElementById('link-url').value.trim();
  const icon = document.getElementById('link-icon').value.trim();
  if (!name || !url) { alert('名称和 URL 必填'); return; }
  fetch('/api/web-links', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name,url,icon_url:icon})})
    .then(() => { closeLinkModal(); loadLinks(); });
}
function deleteLink(id) {
  if (!confirm('删除该链接？')) return;
  fetch('/api/web-links/' + id, {method:'DELETE'}).then(() => loadLinks());
}

// ===== 目录 =====
async function loadDirs() {
  const list = await fetchJSON('/api/dir-shortcuts');
  const el = document.getElementById('dir-list');
  if (!list || list.length === 0) {
    el.innerHTML = `<div class="dir-item" onclick="showDirModal()" style="font-style:italic;color:var(--text-secondary)">
      <span class="dir-icon">📂</span>
      <span class="dir-text">
        <span class="dir-name">+ 添加目录</span>
        <span class="dir-path">点击添加</span>
      </span>
    </div>`;
    return;
  }
  el.innerHTML = list.map(d =>
    `<div class="dir-item" onclick="openDir('${d.id}')" title="${esc(d.path)}">
      <span class="dir-icon">📁</span>
      <span class="dir-text">
        <span class="dir-name">${esc(d.name)}</span>
        <span class="dir-path">${esc(d.path)}</span>
      </span>
      <span class="dir-del" onclick="event.stopPropagation();deleteDir('${d.id}')">×</span>
    </div>`).join('');
}
function showDirModal() {
  document.getElementById('dir-name').value = '';
  document.getElementById('dir-path').value = '';
  document.getElementById('dir-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('dir-name').focus(), 50);
}
function closeDirModal() { document.getElementById('dir-modal').classList.add('hidden'); }
function submitDir() {
  const name = document.getElementById('dir-name').value.trim();
  const path = document.getElementById('dir-path').value.trim();
  if (!name || !path) { alert('名称和路径必填'); return; }
  fetch('/api/dir-shortcuts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name,path})})
    .then(r => r.json().then(d => ({ok: r.ok, body: d})))
    .then(({ok, body}) => {
      if (!ok) { alert('添加失败：' + (body.error || '未知错误')); return; }
      closeDirModal();
      loadDirs();
    });
}
async function openDir(id) {
  try {
    const r = await fetch('/api/dir-shortcuts/' + id + '/open', {method:'POST'});
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      alert('打开失败：' + (body.error || r.statusText || '目录可能不存在或无权限'));
      return;
    }
    // 成功（如果是 JSON 响应）— 不弹窗，静默成功
  } catch (e) {
    alert('打开失败：' + e.message);
  }
}
function deleteDir(id) {
  if (!confirm('删除该目录快捷？')) return;
  fetch('/api/dir-shortcuts/' + id, {method:'DELETE'}).then(() => loadDirs());
}

// ===== 待办（支持增删 + 勾选） =====
async function loadTodo() {
  const data = await fetchJSON('/api/todo');
  const el = document.getElementById('todo-list');
  if (!data.path) { el.innerHTML = '<div style="color:var(--text-secondary);font-size:12px">未配置 todo.md 路径，点击"设置"</div>'; return; }
  if (!data.items || data.items.length === 0) { el.innerHTML = '<div style="color:var(--text-secondary);font-size:12px">' + esc(data.path) + ' 无 todo 项</div>'; return; }
  el.innerHTML = data.items.map(i =>
    `<div class="todo-item ${i.done?'done':''}">
      <input type="checkbox" ${i.done?'checked':''} onchange="toggleTodo(${i.line_no}, this.checked)">
      <span class="todo-text">${esc(i.text)}</span>
      <span class="todo-del" onclick="deleteTodoItem(${i.line_no})" title="删除">×</span>
    </div>`).join('');
}
function toggleTodo(lineNo, done) {
  fetch('/api/todo/' + lineNo, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({done})})
    .then(() => loadTodo());
}
async function deleteTodoItem(lineNo) {
  if (!confirm('删除该待办？')) return;
  const r = await fetch('/api/todo/' + lineNo, {method:'DELETE'});
  if (!r.ok) { const b = await r.json().catch(() => ({})); alert('删除失败：' + (b.error || r.statusText)); return; }
  loadTodo();
}
function showTodoAddModal() {
  document.getElementById('todo-add-input').value = '';
  document.getElementById('todo-add-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('todo-add-input').focus(), 50);
}
function closeTodoAddModal() { document.getElementById('todo-add-modal').classList.add('hidden'); }
async function submitTodoAdd() {
  const text = document.getElementById('todo-add-input').value.trim();
  if (!text) { alert('内容必填'); return; }
  const r = await fetch('/api/todo', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text})});
  if (!r.ok) { const b = await r.json().catch(() => ({})); alert('添加失败：' + (b.error || r.statusText)); return; }
  closeTodoAddModal();
  loadTodo();
}
async function showTodoPathModal() {
  const d = await fetchJSON('/api/todo/path');
  document.getElementById('todo-path-input').value = d.path || '';
  document.getElementById('todo-path-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('todo-path-input').focus(), 50);
}
function closeTodoPathModal() { document.getElementById('todo-path-modal').classList.add('hidden'); }
function submitTodoPath() {
  const path = document.getElementById('todo-path-input').value.trim();
  if (!path) { alert('路径必填'); return; }
  fetch('/api/todo/path', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path})})
    .then(() => { closeTodoPathModal(); loadTodo(); });
}
