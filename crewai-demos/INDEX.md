# CrewAI Demos - 智能体示例

本目录包含 CrewAI 框架的智能体示例代码和文档。

---

## 📁 文件结构

```
crewai-demos/
├── study-abroad-consultant.py    # 日本留学咨询顾问智能体（主程序）
├── README.md                      # 使用指南
├── CODE-ANALYSIS.md               # 代码解析文档（教学用）
├── INDEX.md                       # 目录索引
├── .env.example                   # 环境变量配置模板
└── .gitignore                     # Git 忽略文件配置
```

---

## 🎯 示例列表

### 1. 日本留学咨询顾问 (`study-abroad-consultant.py`)

**功能**：专业解答日本研究生/修士申请相关问题

**核心能力**：
- 院校定位与推荐
- 申请路径规划
- 材料清单指导
- 时间轴规划
- 文书指导

**技术要点**：
- CrewAI 基础用法（Agent + Task + Crew）
- sqlite3 补丁（解决 ChromaDB 依赖问题）
- 阿里云百炼 API 集成（环境变量方式）
- 命令行参数处理

**运行方式**：
```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 编辑 .env 文件，填入真实的 API Key
vim .env

# 3. 运行示例
python3 study-abroad-consultant.py

# 或直接传入 API Key
OPENAI_API_KEY=sk-your-key python3 study-abroad-consultant.py
```

**学习资源**：
- `README.md` - 使用指南
- `CODE-ANALYSIS.md` - 代码解析（适合学习 Agent 开发）

---

## 🚀 快速开始

### 环境准备

```bash
# 1. 安装依赖
pip install crewai crewai-tools pysqlite3-binary

# 2. 确认安装成功
python3 -c "import crewai; print(crewai.__version__)"
```

### 配置 API Key

**方式一：使用 .env 文件（推荐）**
```bash
# 复制模板
cp .env.example .env

# 编辑 .env 文件，填入真实的 API Key
vim .env
```

**.env 文件内容**：
```bash
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_API_BASE=https://coding.dashscope.aliyuncs.com/v1
OPENAI_MODEL_NAME=qwen3.5-plus
```

**方式二：命令行临时设置**
```bash
export OPENAI_API_KEY=sk-your-actual-api-key-here
python3 study-abroad-consultant.py
```

**方式三：直接传入**
```bash
OPENAI_API_KEY=sk-your-actual-api-key-here python3 study-abroad-consultant.py
```

### 运行示例

```bash
cd /home/workspace/repo/ai-playground/crewai-demos

# 使用默认示例问题
python3 study-abroad-consultant.py

# 自定义问题
python3 study-abroad-consultant.py "我想申请京都大学的经济学研究科"
```

---

## 📚 学习路径

### 初学者

1. 阅读 `README.md` - 了解功能和使用方法
2. 运行示例代码 - 观察输出结果
3. 修改示例问题 - 尝试不同场景
4. 阅读 `CODE-ANALYSIS.md` 第 1-3 章 - 理解核心概念

### 进阶开发者

1. 阅读 `CODE-ANALYSIS.md` 第 4-5 章 - 学习设计模式和扩展方法
2. 修改 Agent 配置 - 调整角色、目标、backstory
3. 添加新 Agent - 实现多 Agent 协作
4. 集成工具 - 添加搜索、文件处理等能力

---

## 🔧 技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| CrewAI | 1.10.1 | 多 Agent 协作框架 |
| Python | 3.12+ | 运行环境 |
| pysqlite3-binary | 0.5.4 | SQLite 补丁 |
| 模型 | qwen3.5-plus | 阿里云百炼 - 通义千问 |

---

## 🔒 安全提示

**重要**: 本示例使用环境变量管理 API Key，请遵守以下安全规范：

1. ✅ **不要提交 .env 文件到 Git** - 已加入 .gitignore
2. ✅ **不要硬编码 API Key** - 使用 `os.getenv()` 读取
3. ✅ **使用 .env.example 模板** - 占位符不含真实 Key
4. ✅ **定期更换 API Key** - 如果怀疑泄露

**参考**: `RULES.md` - RULE-006 (API Key 安全管理规范)

---

## 📝 待开发示例

- [ ] 多 Agent 协作示例（研究员 + 作家 + 编辑）
- [ ] 带搜索工具的 Agent（实时信息查询）
- [ ] 结构化输出示例（Pydantic 模型）
- [ ] 带记忆的 Agent（跨会话上下文）
- [ ] 文件处理示例（读取 PDF/Word 文档）

---

## 🆘 常见问题

### Q: 运行时提示 sqlite3 错误？
**A**: 确保已安装 `pysqlite3-binary` 且脚本开头包含 sqlite3 补丁代码。

### Q: API 密钥错误？
**A**: 检查 .env 文件是否存在且包含正确的 API Key。

### Q: 响应速度太慢？
**A**: 这是正常现象（30-60 秒），复杂问题需要多次 LLM 迭代。

### Q: 如何查看 API 用量？
**A**: 登录阿里云百炼控制台查看。

---

## 📖 相关资源

- [CrewAI 官方文档](https://docs.crewai.com/)
- [CrewAI GitHub](https://github.com/joaomdmoura/crewai)
- [一人团队 Multi-Agent 系统设计](../design/一人团队设计.md)
- [全局规则配置](../../.openclaw/workspace/RULES.md)

---

**最后更新**：2026-03-16  
**维护者**：小黑 - 管家
