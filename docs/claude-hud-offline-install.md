# claude-hud 安装指南

本文档描述 claude-hud 插件的安装方式，包含**在线制作**和**离线安装**两种方法。

## 方式一：在线制作安装包（推荐）

在有网络的环境中，执行以下命令即可生成可拷贝的完整包：

```bash
# 1. 添加市场源（首次需要，已配置可跳过）
/plugin marketplace add jarrodwatts/claude-hud

# 2. 安装插件
/plugin install claude-hud

# 3. 安装完成后，插件文件位于：
~/.claude/plugins/cache/claude-hud/claude-hud/<版本号>/

# 4. 将此目录完整打包，即可带到离线环境使用
tar -czvf claude-hud-plugin.tar.gz -C ~/.claude/plugins/cache/claude-hud/ claude-hud/
```

**优势**：自动完成所有配置（settings.json、插件注册表），无需手动编辑。打包后直接复制到离线环境相同路径即可。

**注意**：如果是全新环境，需要先执行步骤 1 添加市场源。如果 `extraKnownMarketplaces` 中已有 claude-hud 配置，可直接从步骤 2 开始。

---

## 方式二：离线安装

适用于无网络环境，需要手动拷贝文件和编辑配置。

---

## 环境信息（本示例）

## 环境信息（本示例）

| 项目 | 值 |
|------|------|
| 操作系统 | Linux |
| Claude 配置目录 | `/root/.claude` |
| Node.js 路径 | `/home/workspace/local/node-v24.13.0-linux-x64/bin/node` |
| 插件版本 | 0.0.11 |
| 插件目录 | `/root/.claude/plugins/cache/claude-hud/claude-hud/0.0.11/` |

---

## 步骤 1：在有网络环境下载插件

```bash
# 克隆 claude-hud 仓库
git clone https://github.com/jarrodwatts/claude-hud.git

# 或者下载指定版本
cd claude-hud
git checkout v0.0.11  # 或对应版本标签
```

---

## 步骤 2：拷贝插件文件到目标环境

将以下目录结构完整拷贝到目标机器的对应位置：

```
# 源目录（联网机器）
claude-hud/  ← 整个仓库内容

# 目标目录（离线机器）
~/.claude/plugins/cache/claude-hud/claude-hud/0.0.11/
```

**拷贝命令示例：**
```bash
# 创建目标目录
mkdir -p ~/.claude/plugins/cache/claude-hud/claude-hud/0.0.11

# 拷贝全部文件
cp -r /path/to/claude-hud-repo/* ~/.claude/plugins/cache/claude-hud/claude-hud/0.0.11/
```

---

## 步骤 3：配置 settings.json

编辑 `~/.claude/settings.json`，确保包含以下内容：

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash -c 'exec /home/workspace/local/node-v24.13.0-linux-x64/bin/node /root/.claude/plugins/cache/claude-hud/claude-hud/0.0.11/dist/index.js'"
  },
  "enabledPlugins": {
    "claude-hud@claude-hud": true
  }
}
```

**注意：** 需要根据实际环境修改：
- Node.js 路径
- 插件安装路径（如果版本号不同）

---

## 步骤 4：配置插件注册表（可选）

编辑 `~/.claude/plugins/installed_plugins.json`：

```json
{
  "version": 2,
  "plugins": {
    "claude-hud@claude-hud": [
      {
        "scope": "user",
        "installPath": "/root/.claude/plugins/cache/claude-hud/claude-hud/0.0.11",
        "version": "0.0.11",
        "installedAt": "2026-03-29T14:31:04.457Z",
        "lastUpdated": "2026-03-29T14:31:04.457Z"
      }
    ]
  }
}
```

---

## 步骤 5：配置 HUD 显示选项（可选）

创建 `~/.claude/plugins/claude-hud/config.json`：

```json
{
  "display": {
    "showTools": true,
    "showAgents": true,
    "showTodos": true,
    "showDuration": true,
    "showConfigCounts": true,
    "showSessionName": true
  }
}
```

**配置项说明：**

| 配置项 | 说明 | 默认 |
|--------|------|------|
| `showTools` | 显示工具活动（Read ×3, Edit: file.ts） | false |
| `showAgents` | 显示子 Agent 状态 | false |
| `showTodos` | 显示 Todo 进度 | false |
| `showDuration` | 显示会话时长 | false |
| `showConfigCounts` | 显示配置文件数量（CLAUDE.md, MCPs 等） | false |
| `showSessionName` | 显示会话名称 | false |

---

## 步骤 6：重启 Claude Code

```bash
# 退出当前会话
/exit

# 重新启动
claude
```

---

## 验证安装

重启后，HUD 应该显示在输入框下方，类似：

```
◐ 2 tools | ✓ 3 agents | ⏱ 15m | 📄 3 configs
```

运行以下命令测试：
```bash
/root/.claude/plugins/cache/claude-hud/claude-hud/0.0.11/dist/index.js
```

应输出 HUD 内容。

---

## 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 无 HUD 显示 | 未重启 Claude Code | 完全退出后重新启动 |
| command not found | Node.js 路径错误 | `command -v node` 确认正确路径 |
| 权限拒绝 | 文件不可执行 | `chmod +x <node 路径>` |
| 插件不加载 | enabledPlugins 未配置 | 检查 settings.json |

---

## 更新插件

离线环境更新插件需要重复上述步骤：

1. 在联网机器 `git pull` 获取最新版本
2. 拷贝到新版本号目录（如 `0.0.12/`）
3. 更新 `settings.json` 中的路径（如使用固定路径）
4. 重启 Claude Code

动态路径命令会自动使用最新版本：
```bash
bash -c 'plugin_dir=$(ls -d "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/plugins/cache/claude-hud/claude-hud/*/ 2>/dev/null | sort -V | tail -1); exec <node 路径> "${plugin_dir}/dist/index.js"'
```
