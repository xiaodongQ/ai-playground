# CrewAI 智能体使用指南

## 📁 项目结构

```
crewai-agents/
├── study-abroad-consultant.py    # 日本留学咨询顾问智能体
└── README.md                      # 本文件
```

---

## 🎯 智能体功能

### 日本留学咨询顾问 (`study-abroad-consultant.py`)

**功能定位**：专业解答日本研究生/修士申请相关问题

**核心能力**：
- ✅ 院校定位与推荐（东大、京大、东工大等）
- ✅ 申请路径规划（研究生→修士、直考、英语项目）
- ✅ 材料清单指导（研究计划书、推荐信、语言成绩）
- ✅ 时间轴规划（1-1.5 年准备周期）
- ✅ 套磁信与研究计划书指导
- ✅ 常见误区与注意事项提醒

**适用场景**：
- 学生咨询日本留学申请
- 快速生成专业回复
- 辅助留学顾问工作

---

## 🚀 快速开始

### 1. 环境准备

确保已安装依赖：
```bash
pip install crewai crewai-tools pysqlite3-binary
```

### 2. 运行智能体

**方式一：使用默认示例问题**
```bash
cd /root/.openclaw/workspace
python3 crewai-agents/study-abroad-consultant.py
```

**方式二：传入自定义问题**
```bash
python3 crewai-agents/study-abroad-consultant.py "我想申请京都大学的经济学研究科，需要准备什么？"
```

### 3. 示例问题

脚本内置了 5 个示例问题：
1. 我想申请东京大学的计算机专业修士，需要准备什么？
2. 我现在大二，想申请日本研究生，应该如何规划时间？
3. 我的日语是 N2，英语托福 80 分，能申请哪些学校？
4. 研究计划书应该怎么写？有什么注意事项？
5. 套磁信应该什么时候发？怎么写才能提高回复率？

---

## ⚙️ 配置说明

### API 配置

脚本已配置阿里云百炼（通义千问）API：
```python
os.environ['OPENAI_API_KEY'] = 'sk-sp-10fae675e5964548be93f3f0eabb4298'
os.environ['OPENAI_API_BASE'] = 'https://coding.dashscope.aliyuncs.com/v1'
os.environ['OPENAI_MODEL_NAME'] = 'qwen3.5-plus'
```

如需更换模型，修改以上配置即可。

### SQLite 补丁

由于系统 sqlite3 版本问题，脚本开头包含必需的补丁：
```python
import pysqlite3
import sys
sys.modules['sqlite3'] = pysqlite3
```

**⚠️ 注意**：此补丁不可删除，否则 CrewAI 无法正常运行。

---

## 📝 代码结构

```python
# 1. sqlite3 补丁（必需）
import pysqlite3
import sys
sys.modules['sqlite3'] = pysqlite3

# 2. 导入 CrewAI
from crewai import Agent, Task, Crew, Process

# 3. 创建 Agent
agent = Agent(
    role='日本留学申请专家',
    goal='为学生提供专业、详细的日本研究生/修士申请指导',
    backstory='...',
    verbose=True
)

# 4. 创建 Task
task = Task(
    description='请详细回答学生的留学咨询问题：...',
    expected_output='一份完整、专业的日本留学咨询回复',
    agent=agent
)

# 5. 创建 Crew 并执行
crew = Crew(agents=[agent], tasks=[task], verbose=True)
result = crew.kickoff()
```

---

## 🔧 扩展开发

### 创建新的智能体

复制 `study-abroad-consultant.py` 并修改：

1. **修改 Agent 定义**：
```python
agent = Agent(
    role='你的 Agent 角色',
    goal='你的 Agent 目标',
    backstory='你的 Agent 背景故事',
    verbose=True
)
```

2. **修改 Task 描述**：
```python
task = Task(
    description='你的任务描述',
    expected_output='期望的输出格式',
    agent=agent
)
```

3. **运行新智能体**：
```bash
python3 crewai-agents/your-new-agent.py
```

### 添加联网搜索功能

如需让 Agent 能够搜索最新信息，启用 SerperDevTool：

```bash
# 1. 获取 Serper API Key（https://serper.dev/）
export SERPER_API_KEY='your-api-key'

# 2. 在脚本中启用工具
from crewai_tools import SerperDevTool
agent = Agent(..., tools=[SerperDevTool()])
```

---

## 📊 测试结果

**测试问题**：我想申请东京大学的计算机专业修士，需要准备什么？

**测试时间**：2026-03-16

**测试结果**：✅ 成功

**输出质量**：
- ✅ 专业详细（涵盖申请路径、院校推荐、材料清单、时间规划、注意事项）
- ✅ 结构清晰（六大章节，层次分明）
- ✅ 语气友好（鼓励学生，提供 actionable 建议）
- ✅ 格式美观（使用 Markdown 列表、表格、强调）

**响应时间**：约 30-60 秒（取决于问题复杂度）

---

## ⚠️ 注意事项

1. **API 费用**：使用阿里云百炼 API 会产生费用，请监控用量
2. **响应时间**：复杂问题可能需要 30-60 秒
3. **信息时效性**：Agent 知识有截止日期，重要信息请以官网为准
4. **sqlite3 补丁**：每次使用 CrewAI 都必须包含 sqlite3 补丁

---

## 📚 相关资源

- [CrewAI 官方文档](https://docs.crewai.com/)
- [CrewAI Tools](https://docs.crewai.com/concepts/tools)
- [阿里云百炼文档](https://help.aliyun.com/zh/model-studio/)
- [日本留学申请指南](memory/crewai-installation.md)

---

## 🆘 常见问题

### Q: 运行时提示 sqlite3 版本错误？
**A**: 确保脚本开头包含 sqlite3 补丁代码，并已安装 `pysqlite3-binary`。

### Q: API 密钥错误？
**A**: 检查 `OPENAI_API_KEY` 和 `OPENAI_API_BASE` 配置是否正确。

### Q: 响应速度太慢？
**A**: 这是正常现象，CrewAI 会进行多轮思考。如需加速，可简化 Agent 的 backstory 和 task description。

### Q: 如何让 Agent 说中文？
**A**: 在 task description 中明确要求"请用中文回答"。

---

**最后更新**：2026-03-16
**维护者**：小黑 - 管家
