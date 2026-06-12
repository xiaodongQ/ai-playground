// Experiences Tab：经验库列表 + 模块搜索 + exp modal（查看/添加/删除）
// 依赖 api.js

let exps = [];

async function loadExps() {
  const module = document.getElementById('exp-search').value;
  const url = API + '/api/experiences' + (module ? '?module=' + encodeURIComponent(module) : '');
  try {
    exps = await fetchJSON(url);
    renderExpTable(exps);
  } catch(e) { console.error(e); }
}

function renderExpTable(list) {
  const el = document.getElementById('exp-list');
  if (!list || list.length === 0) {
    el.innerHTML = '<div class="empty">暂无经验</div>';
    document.getElementById('exp-count').textContent = '0 条经验';
    return;
  }
  document.getElementById('exp-count').textContent = list.length + ' 条经验';
  el.innerHTML = `<table>
    <thead><tr><th>模块</th><th>关键词</th><th>适用场景</th><th>操作</th></tr></thead>
    <tbody>${list.map(e => `
      <tr>
        <td style="font-weight:500">${esc(e.module)}</td>
        <td style="font-size:12px;color:var(--text-secondary)">${esc(e.keywords || '-')}</td>
        <td style="font-size:12px;color:var(--text-secondary)">${esc(e.scene || '-')}</td>
        <td>
          <button class="btn btn-secondary btn-small" onclick="viewExp('${e.id}')">查看</button>
          <button class="btn btn-danger btn-small" onclick="deleteExp('${e.id}')">删除</button>
        </td>
      </tr>`).join('')}</tbody>
  </table>`;
}

function viewExp(id) {
  const e = exps.find(e => e.id === id);
  if (!e) { loadExps().then(() => viewExp(id)); return; }
  document.getElementById('exp-modal-title').textContent = '经验详情: ' + e.module;
  document.getElementById('exp-id').value = e.id;
  document.getElementById('exp-module').value = e.module;
  document.getElementById('exp-module').readOnly = true;
  document.getElementById('exp-keywords').value = e.keywords || '';
  document.getElementById('exp-log-paths').value = e.log_paths || '';
  document.getElementById('exp-tool-usage').value = e.tool_usage || '';
  document.getElementById('exp-scene').value = e.scene || '';
  document.getElementById('exp-log-samples').value = e.log_samples || '';
  document.getElementById('exp-code-snippets').value = e.code_snippets || '';
  document.getElementById('exp-submit-btn').classList.add('hidden');
  document.getElementById('exp-modal').classList.remove('hidden');
}

function showExpModal(exp) {
  document.getElementById('exp-modal-title').textContent = exp ? '编辑经验' : '添加经验';
  document.getElementById('exp-id').value = '';
  document.getElementById('exp-module').value = '';
  document.getElementById('exp-module').readOnly = false;
  document.getElementById('exp-keywords').value = '';
  document.getElementById('exp-log-paths').value = '';
  document.getElementById('exp-tool-usage').value = '';
  document.getElementById('exp-scene').value = '';
  document.getElementById('exp-log-samples').value = '';
  document.getElementById('exp-code-snippets').value = '';
  document.getElementById('exp-submit-btn').classList.remove('hidden');
  document.getElementById('exp-modal').classList.remove('hidden');
}

function closeExpModal() {
  document.getElementById('exp-modal').classList.add('hidden');
}

async function submitExp() {
  const module = document.getElementById('exp-module').value.trim();
  if (!module) { alert('请输入模块名'); return; }
  await fetch(API + '/api/experiences', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      module,
      keywords: document.getElementById('exp-keywords').value,
      log_paths: document.getElementById('exp-log-paths').value,
      tool_usage: document.getElementById('exp-tool-usage').value,
      scene: document.getElementById('exp-scene').value,
      log_samples: document.getElementById('exp-log-samples').value,
      code_snippets: document.getElementById('exp-code-snippets').value
    })
  });
  closeExpModal();
  loadExps();
}

async function deleteExp(id) {
  if (!confirm('确认删除这条经验？')) return;
  await fetch(API + '/api/experiences/' + id, {method: 'DELETE'});
  loadExps();
}
