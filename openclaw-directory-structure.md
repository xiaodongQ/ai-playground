# 📂 OpenClaw 安装目录结构详解

**路径：** `/home/workspace/local/node-v24.13.0-linux-x64/lib/node_modules/openclaw/`

---

## 📋 目录概览

| 目录/文件 | 说明 |
|-----------|------|
| `openclaw.mjs` | ⚙️ CLI 入口脚本（可执行） |
| `package.json` | 📦 包配置、依赖、脚本 |
| `README.md` | 📖 项目说明文档（122KB） |
| `CHANGELOG.md` | 📝 版本更新日志（561KB） |
| `LICENSE` | 📜 MIT 许可证 |
| `dist/` | 🏗️ 编译后的 JavaScript 代码 |
| `docs/` | 📚 官方文档（28 个子目录） |
| `extensions/` | 🔌 渠道/平台集成插件（43 个） |
| `skills/` | 🛠️ 技能模块（54 个） |
| `node_modules/` | 📦 依赖包（438 个） |
| `assets/` | 🎨 静态资源文件 |

---

## 🔍 核心组件详解

### 1️⃣ CLI 入口 — `openclaw.mjs`

这是你运行 `openclaw` 命令时执行的脚本，支持所有 CLI 子命令：
- `openclaw gateway` - 启动网关服务
- `openclaw message` - 发送消息
- `openclaw agent` - 调用 AI 代理
- `openclaw onboard` - 初始化向导

---

### 2️⃣ 文档目录 — `docs/` (28 项)

```
docs/
├── automation/          # 自动化配置
├── channels/            # 渠道集成文档
├── cli/                 # CLI 命令参考
├── concepts/            # 核心概念
├── diagnostics/         # 诊断工具
├── gateway/             # Gateway 配置
├── install/             # 安装指南
├── nodes/               # 节点管理
├── plugins/             # 插件开发
├── providers/           # AI 提供商配置
├── reference/           # API 参考
├── security/            # 安全配置
├── tools/               # 工具使用
└── zh-CN/               # 中文文档
```

---

### 3️⃣ 扩展插件 — `extensions/` (43 个)

#### 消息渠道集成

| 插件 | 用途 |
|------|------|
| `discord` | Discord 机器人 |
| `telegram` | Telegram Bot |
| `whatsapp` | WhatsApp 集成 |
| `feishu` | 飞书集成 |
| `slack` | Slack Bot |
| `signal` | Signal 消息 |
| `imessage` | macOS iMessage |
| `googlechat` | Google Chat |
| `matrix` | Matrix 协议 |
| `irc` | IRC 聊天 |
| `zalo` | Zalo (越南) |
| `line` | LINE (日本) |

#### 功能扩展

- `acpx` - ACP 协议扩展
- `device-pair` - 设备配对
- `voice-call` - 语音通话
- `tts` - 语音合成

---

### 4️⃣ 技能模块 — `skills/` (54 个)

#### 笔记/知识管理

| 技能 | 用途 |
|------|------|
| `bear-notes` | Bear 笔记 |
| `notion` | Notion 集成 |
| `obsidian` | Obsidian 知识库 |
| `apple-notes` | macOS 备忘录 |
| `apple-reminders` | macOS 提醒事项 |

#### 开发工具

| 技能 | 用途 |
|------|------|
| `coding-agent` | 代码开发代理 |
| `github` | GitHub 集成 |
| `gh-issues` | GitHub Issues |
| `tmux` | Tmux 终端管理 |

#### 媒体/娱乐

| 技能 | 用途 |
|------|------|
| `spotify-player` | Spotify 播放 |
| `sonoscli` | Sonos 音响 |
| `gog` | GOG 游戏 |
| `video-frames` | 视频帧处理 |

#### 工具类

| 技能 | 用途 |
|------|------|
| `weather` | 天气查询 ⛅ |
| `healthcheck` | 系统健康检查 |
| `clawhub` | 技能市场 |
| `skill-creator` | 技能创建工具 |
| `1password` | 密码管理 |

---

## 📊 版本信息

从 `package.json` 获取：

| 项目 | 值 |
|------|-----|
| **名称** | openclaw |
| **版本** | 2026.3.2 |
| **类型** | ES Module |
| **许可证** | MIT |
| **入口** | `dist/index.js` |
| **CLI** | `openclaw.mjs` |

---

## 🎯 关键特性

1. **多通道支持** - 20+ 消息平台集成
2. **可扩展技能** - 54+ 预置技能模块
3. **本地运行** - 完全私有化部署
4. **网关架构** - Gateway 作为控制平面
5. **Node.js 驱动** - 需要 Node ≥22

---

## 🔗 相关链接

- **官网：** https://openclaw.ai
- **文档：** https://docs.openclaw.ai
- **源码：** https://github.com/openclaw/openclaw
- **社区：** https://discord.gg/clawd

---

*文档生成时间：2026-03-07 21:38 GMT+8*
