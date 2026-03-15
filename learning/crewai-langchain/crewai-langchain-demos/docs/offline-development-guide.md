# CrewAI 离线开发指南（2026 年 3 月更新）

> 📡 **离线开发专用**  
> 适用场景：无法直接访问 PyPI 或网络受限的开发环境  
> ⚠️ **最后更新**: 2026-03-15（已核实正确安装方式和 Python 版本要求）

---

## ⚠️ 重要更新说明（2026-03-15 23:30）

### Python 版本要求

| 组件 | 最低版本 | 最高版本 | 推荐版本 |
|------|---------|---------|---------|
| **Python** | **3.10** | **3.13** | **3.11 或 3.12** |

⚠️ **注意**: 
- Python 3.9 及以下：❌ 不支持
- Python 3.14 及以上：❌ 不支持（尚未兼容）

### 正确的安装方式

**crewai-tools 已经合并到 crewai 主包中！**

```bash
# ✅ 正确的安装方式（2026 年）
pip install "crewai[tools]"

# 或分开安装（也支持）
pip install crewai crewai-tools
```

### 版本信息

| 包名 | 最新版本 | 说明 |
|------|---------|------|
| `crewai` | `1.10.1` | ✅ 主包 |
| `crewai[tools]` | 包含 tools | ✅ **推荐** |
| `crewai-tools` | `1.10.1` | ⚠️ 独立包（可选） |

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速安装](#2-快速安装)
3. [离线开发方案](#3-离线开发方案)
4. [验证安装](#4-验证安装)
5. [常见问题](#5-常见问题)

---

## 1. 环境要求

### 1.1 Python 版本检查

```bash
# 检查 Python 版本（必须 >=3.10 且 <3.14）
python --version

# 如果版本不对，需要升级
# Ubuntu/Debian:
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# macOS (使用 Homebrew):
brew install python@3.11

# Windows:
# 下载 https://www.python.org/downloads/
```

### 1.2 创建虚拟环境（推荐）

```bash
# 创建虚拟环境（使用 Python 3.11）
python3.11 -m venv crewai-env

# 激活虚拟环境
# Linux/macOS:
source crewai-env/bin/activate

# Windows:
crewai-env\Scripts\activate

# 验证
python --version  # 应该显示 Python 3.11.x
```

### 1.3 升级 pip

```bash
# 升级 pip 到最新版本
python -m pip install --upgrade pip

# 验证 pip 版本
pip --version  # 建议 24.0+
```

---

## 2. 快速安装

### 2.1 在线安装（推荐）

```bash
# ✅ 官方推荐方式（包含 tools）
pip install "crewai[tools]"

# 或使用 uv（更快）
uv add "crewai[tools]"

# 或只安装核心包（不含 tools）
pip install crewai
```

### 2.2 依赖项

crewai[tools] 会自动安装以下依赖：
- `pydantic>=2.0` - 数据验证
- `click>=8.0` - CLI 工具
- `python-dotenv>=1.0` - 环境变量管理
- `chromadb>=0.5` - 向量数据库
- `openai>=1.83` - OpenAI API 客户端
- 等等...

---

## 3. 离线开发方案

### 3.1 方案一：在有网环境下载依赖包

```bash
# 创建 requirements.txt
cat > requirements.txt << EOF
crewai[tools]>=1.10.0
python-dotenv>=1.0.0
EOF

# 下载所有依赖（包括 tools）
pip download "crewai[tools]" -d packages/

# 验证下载结果
ls -lh packages/ | wc -l
# 应该看到 50+ 个 .whl 文件

# 打包
tar -czf crewai-offline-packages.tar.gz packages/

# 传输到离线环境
scp crewai-offline-packages.tar.gz user@offline-server:/path/to/
```

### 3.2 在离线环境安装

```bash
# 解压
tar -xzf crewai-offline-packages.tar.gz

# 离线安装
pip install --no-index --find-links=packages/ -r requirements.txt
```

---

## 4. 验证安装

### 4.1 基础验证

```bash
# 检查 crewai 版本
python -c "import crewai; print('crewai:', crewai.__version__)"

# 检查 tools
python -c "from crewai_tools import FileReadTool; print('tools OK')"
```

### 4.2 完整测试

```python
from crewai import Agent, Task, Crew
from crewai_tools import FileReadTool

# 创建 Agent
agent = Agent(
    role="测试员",
    goal="验证安装",
    backstory="测试 crewai 是否正常工作",
    tools=[FileReadTool()]
)

# 创建任务
task = Task(
    description="验证 crewai 安装",
    expected_output="安装成功",
    agent=agent
)

# 执行
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()

print("✅ 安装验证成功！")
```

---

## 5. 常见问题

### Q1: Python 版本不对怎么办？

**错误**: `crewai requires Python >=3.10, <3.14`

**解决方案**:

```bash
# 检查当前版本
python --version

# Ubuntu/Debian 安装 Python 3.11
sudo apt update
sudo apt install python3.11 python3.11-venv

# 使用特定版本
python3.11 -m pip install "crewai[tools]"
```

---

### Q2: `pip install "crewai[tools]"` 报错

**错误**: `No matching distribution found`

**解决方案**:

```bash
# 1. 升级 pip
python -m pip install --upgrade pip

# 2. 检查 Python 版本（需要 3.10-3.13）
python --version

# 3. 使用引号（bash 需要）
pip install "crewai[tools]"

# 4. 或转义
pip install crewai\[tools\]

# 5. 源码安装（慢但可靠）
pip install "crewai[tools]" --no-binary :all:
```

---

### Q3: 导入 `crewai_tools` 失败

**错误**: `ModuleNotFoundError: No module named 'crewai_tools'`

**解决方案**:

```bash
# 确认安装了 tools
pip install "crewai[tools]"

# 验证
python -c "from crewai_tools import FileReadTool; print('OK')"
```

---

### Q4: 离线环境如何验证版本？

```bash
# 查看已安装的包
pip list | grep crewai

# 查看详细信息
pip show crewai
pip show crewai-tools
```

---

## 📚 相关文档

- [CrewAI 核心概念](./crewai-langchain-research.md#1-crewai-核心概念)
- [快速入门](./crewai-langchain-research.md#2-crewai-快速入门)
- [Demo 示例](../demos/)

---

## 🔗 官方资源

| 资源 | 链接 |
|------|------|
| **GitHub** | https://github.com/crewAIInc/crewAI |
| **文档** | https://docs.crewai.com |
| **PyPI** | https://pypi.org/project/crewai/ |
| **社区** | https://community.crewai.com |

---

**维护者**: Edu·伴学堂 📚  
**最后更新**: 2026-03-15 23:30（已核实 Python 版本要求）  
**Python 要求**: >=3.10, <3.14（推荐 3.11 或 3.12）
