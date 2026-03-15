# CrewAI 离线开发指南

> 📡 **离线开发专用**  
> 适用场景：无法直接访问 PyPI 或网络受限的开发环境  
> 最后更新：2026-03-15

---

## 目录

1. [离线开发准备](#1-离线开发准备)
2. [方案一：在有网环境下载依赖包](#2-方案一在有网环境下载依赖包)
3. [方案二：使用本地镜像源](#3-方案二使用本地镜像源)
4. [方案三：手动下载离线安装包](#4-方案三手动下载离线安装包)
5. [CrewAI 离线 Demo 运行](#5-crewai 离线 demo 运行)
6. [常见问题](#6-常见问题)

---

## 1. 离线开发准备

### 1.1 环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.10 | 3.11+ |
| pip | 21.0 | 24.0+ |
| git | 2.30 | 2.40+ |

### 1.2 检查 Python 环境

```bash
# 检查 Python 版本
python --version
# 或
python3 --version

# 检查 pip 版本
pip --version

# 升级 pip（推荐）
python -m pip install --upgrade pip
```

---

## 2. 方案一：在有网环境下载依赖包

### 2.1 创建依赖列表文件

在有网络的环境中，先创建 `requirements.txt`：

```bash
# 创建项目目录
mkdir crewai-offline-demo
cd crewai-offline-demo

# 创建 requirements.txt
cat > requirements.txt << EOF
crewai>=0.50.0
crewai-tools>=0.8.0
langchain>=0.1.0
langchain-community>=0.0.10
python-dotenv>=1.0.0
EOF
```

### 2.2 下载离线包

```bash
# 创建下载目录
mkdir packages

# 下载所有依赖包（包括依赖的依赖）
pip download -r requirements.txt -d packages/

# 验证下载结果
ls -lh packages/ | wc -l
# 应该看到 50+ 个 .whl 文件
```

### 2.3 打包离线包

```bash
# 压缩离线包
tar -czf crewai-offline-packages.tar.gz packages/
# 或使用 zip
zip -r crewai-offline-packages.zip packages/

# 传输到离线环境
scp crewai-offline-packages.tar.gz user@offline-server:/path/to/
```

### 2.4 在离线环境安装

```bash
# 解压离线包
tar -xzf crewai-offline-packages.tar.gz
# 或
unzip crewai-offline-packages.zip

# 离线安装
pip install --no-index --find-links=packages/ -r requirements.txt
```

---

## 3. 方案二：使用本地镜像源

### 3.1 搭建本地 PyPI 镜像（可选）

如果有多台机器需要离线开发，可以搭建本地镜像源：

```bash
# 使用 pip2pi 工具
pip install pip2pi

# 创建镜像目录
mkdir -p /opt/pypi-mirror

# 下载依赖到镜像目录
pip2pi /opt/pypi-mirror/ crewai crewai-tools langchain

# 启动简易 HTTP 服务器
cd /opt/pypi-mirror
python -m http.server 8080
```

### 3.2 配置 pip 使用本地源

```bash
# 创建 pip 配置文件
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << EOF
[global]
index-url = http://localhost:8080/simple
trusted-host = localhost
EOF

# 或使用命令行参数
pip install --index-url http://localhost:8080/simple crewai
```

---

## 4. 方案三：手动下载离线安装包

### 4.1 核心依赖列表

CrewAI 的核心依赖：

```
crewai>=0.50.0
├── crewai-tools>=0.8.0
│   ├── langchain>=0.1.0
│   ├── langchain-community>=0.0.10
│   └── beautifulsoup4>=4.12.0
├── pydantic>=2.0.0
├── click>=8.0.0
└── python-dotenv>=1.0.0
```

### 4.2 手动下载地址

| 包名 | PyPI 地址 | GitHub |
|------|----------|--------|
| crewai | https://pypi.org/project/crewai/ | https://github.com/joaomdmoura/crewAI |
| crewai-tools | https://pypi.org/project/crewai-tools/ | https://github.com/joaomdmoura/crewAI-tools |
| langchain | https://pypi.org/project/langchain/ | https://github.com/langchain-ai/langchain |

### 4.3 下载步骤

1. 访问 PyPI 页面
2. 点击 "Download files"
3. 下载 `.whl` 或 `.tar.gz` 文件
4. 传输到离线环境
5. 使用 `pip install xxx.whl` 安装

---

## 5. CrewAI 离线 Demo 运行

### 5.1 验证安装

```bash
# 检查 crewai 是否安装成功
python -c "import crewai; print(crewai.__version__)"

# 检查 crewai-tools
python -c "from crewai_tools import BaseTool; print('crewai-tools OK')"

# 检查 langchain
python -c "import langchain; print(langchain.__version__)"
```

### 5.2 运行离线 Demo

```bash
# 进入 demo 目录
cd /path/to/crewai-langchain-demos/demos/

# 运行基础示例（不需要联网）
python 01-basic-crew.py
```

### 5.3 离线工具替代方案

某些 crewai-tools 需要联网（如 SerperDevTool），可以使用离线替代：

```python
# ❌ 需要联网的工具
from crewai_tools import SerperDevTool  # 需要 API Key

# ✅ 离线工具替代
from crewai_tools import FileReadTool
from crewai_tools import DirectorySearchTool

# 使用本地文件作为数据源
file_tool = FileReadTool(file_path="local_data.txt")
dir_tool = DirectorySearchTool(directory="./data/")
```

### 5.4 创建离线 Agent 示例

```python
from crewai import Agent, Task, Crew
from crewai_tools import FileReadTool

# 使用本地文件的 Agent
offline_researcher = Agent(
    role="本地数据分析师",
    goal="分析本地文件中的数据",
    backstory="你擅长从本地文件中提取有价值的信息",
    tools=[FileReadTool()],
    verbose=True
)

# 任务
analysis_task = Task(
    description="读取并分析 data.txt 文件",
    expected_output="数据分析报告",
    agent=offline_researcher,
    output_file="analysis_report.md"
)

# 执行
crew = Crew(
    agents=[offline_researcher],
    tasks=[analysis_task],
    verbose=True
)

result = crew.kickoff()
```

---

## 6. 常见问题

### Q1: pip install 报错 "No matching distribution found"

**原因**: Python 版本不匹配或 pip 版本过旧

**解决方案**:
```bash
# 检查 Python 版本
python --version  # 需要 3.10+

# 升级 pip
python -m pip install --upgrade pip

# 指定版本安装
pip install crewai==0.50.0
```

---

### Q2: 离线安装时提示缺少依赖

**原因**: 下载的包不完整，缺少传递依赖

**解决方案**:
```bash
# 在有网环境重新下载，确保包含所有依赖
pip download -r requirements.txt -d packages/ --no-binary :none:

# 或使用 --download-dependencies
pip install crewai --download-dependencies -d packages/
```

---

### Q3: crewai-tools 安装失败

**原因**: 某些工具依赖需要额外安装

**解决方案**:
```bash
# 只安装核心工具（不需要额外依赖）
pip install crewai-tools --no-deps

# 或手动安装依赖
pip install beautifulsoup4 requests lxml
```

---

### Q4: 如何在完全离线环境获取依赖树？

**解决方案**:
```bash
# 在有网环境生成依赖树
pip install pipdeptree
pipdeptree --freeze > dependencies.txt

# 下载所有依赖
pip download -r dependencies.txt -d packages/
```

---

## 📚 相关文档

- [CrewAI 核心概念](./crewai-langchain-research.md#1-crewai-核心概念)
- [快速入门](./crewai-langchain-research.md#2-crewai-快速入门)
- [Demo 示例](../demos/)

---

**维护者**: Edu·伴学堂 📚  
**最后更新**: 2026-03-15
