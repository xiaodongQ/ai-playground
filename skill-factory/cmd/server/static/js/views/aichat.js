// AI Chat Tab：xterm.js 终端 + WebSocket 接 /api/pty（macOS/Linux 真 PTY）
// 依赖 api.js（无 API 调用，纯前端 + WS）

let term;
let ws;
let termReady = false;

function initTerminal() {
  if (term) return;
  term = new Terminal({
    fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
    fontSize: 13,
    theme: { background: '#0f172a', foreground: '#e2e8f0', cursor: '#22d3ee' },
    cursorBlink: true,
    scrollback: 10000,
  });
  term.open(document.getElementById('terminal'));

  ws = new WebSocket('ws://' + window.location.host + '/api/pty');
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => {
    termReady = true;
    term.writeln('\x1b[32mSkill Factory AI Terminal\x1b[0m\r\nType your request in natural language, e.g. "帮我添加一条 redis-cluster 经验"\r\n');
  };
  ws.onmessage = (e) => {
    if (termReady) term.write(new Uint8Array(e.data));
  };
  ws.onclose = () => { term.writeln('\r\n\x1b[33mConnection closed. Refresh to reconnect.\x1b[0m'); termReady = false; };
  ws.onerror = () => { term.writeln('\r\n\x1b[31mWebSocket error\x1b[0m'); };
  term.onData(data => { if (ws && ws.readyState === 1) ws.send(data); });
  term.onResize(() => {
    if (ws && ws.readyState === 1) {
      ws.send('resize,' + term.cols + ',' + term.rows);
    }
  });
}
