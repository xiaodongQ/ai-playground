# CrewAI 离线开发指南（2026 年 3 月更新）

> 📡 **离线开发专用**  
> 适用场景：无法直接访问 PyPI 或网络受限的开发环境  
> ⚠️ **最后更新**: 2026-03-15（已核实正确安装方式）

---

## ⚠️ 重要更新说明（2026-03-15 23:00）

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
| `crewai` | `0.5.0` | ✅ 主包 |
| `crewai[tools]` | 包含 tools | ✅ **推荐** |
| `crewai-tools` | `1.10.1` | ⚠️ 独立包（可选） |

### 为什么推荐 `crewai[tools]`？

1. **官方推荐** - crewAI 官方文档推荐的安装方式
2. **依赖管理** - 自动安装所有必要的工具依赖
3. **版本兼容** - 确保 crewai 和 tools 版本匹配
4. **简化安装** - 一条命令搞定

---

## 目录

1. [快速安装](#1-快速安装)
2. [离线开发方案](#2-离线开发方案)
3. [验证安装](#3-验证安装)
4. [常见问题](#4-常见问题)

---

## 1. 快速安装

### 1.1 在线安装（推荐）

```bash
# 方式一：安装 crewai + tools（推荐）
pip install "crewai[tools]"

# 方式二：只安装 crewai 核心（不含 tools）
pip install crewai

# 方式三：分开安装
pip install crewai crewai-tools
```

### 1.2 环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.10 | 3.11+ |
| pip | 21.0 | 24.0+ |

```bash
# 检查环境
python --version  # 需要 3.10+
pip --version     # 需要 21.0+

# 升级 pip
python -m pip install --upgrade pip
```

---

## 2. 离线开发方案

### 2.1 方案一：在有网环境下载依赖包

```bash
# 创建 requirements.txt
cat > requirements.txt << EOF
crewai[tools]>=0.5.0
python-dotenv>=1.0.0
EOF

# 下载所有依赖（包括 tools）
pip download "crewai[tools]" -d packages/

# 传输到离线环境
scp -r packages/ user@offline-server:/path/to/

# 在离线环境安装
pip install --no-index --find-links=packages/ -r requirements.txt
```

### 2.2 方案二：手动下载离线包

```bash
# 在有网环境下载
pip download "crewai[tools]==0.5.0" -d packages/

# 打包
tar -czf crewai-offline.tar.gz packages/

# 在离线环境解压安装
tar -xzf crewai-offline.tar.gz
pip install --no-index --find-links=packages/ crewai
```

---

## 3. 验证安装

### 3.1 基础验证

```bash
# 检查 crewai 版本
python -c "import crewai; print('crewai:', crewai.__version__)"

# 检查 tools
python -c "from crewai_tools import FileReadTool; print('tools OK')"
```

### 3.2 完整测试

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

## 4. 常见问题

### Q1: `pip install "crewai[tools]"` 报错

**错误**: `No matching distribution found`

**解决方案**:

```bash
# 1. 升级 pip
python -m pip install --upgrade pip

# 2. 检查 Python 版本（需要 3.10+）
python --version

# 3. 使用引号（bash 需要）
pip install "crewai[tools]"

# 4. 或使用转义
pip install crewai\[tools\]

# 5. 源码安装（慢但可靠）
pip install "crewai[tools]" --no-binary :all:
```

---

### Q2: 导入 `crewai_tools` 失败

**错误**: `ModuleNotFoundError: No module named 'crewai_tools'`

**解决方案**:

```bash
# 确认安装了 tools
pip install "crewai[tools]"

# 或单独安装
pip install crewai-tools

# 验证
python -c "from crewai_tools import FileReadTool; print('OK')"
```

---

### Q3: 离线环境如何验证版本？

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
**最后更新**: 2026-03-15 23:00（已核实正确安装方式）  
**感谢**: 感谢用户指出正确的安装方式 `pip install "crewai[tools]"`！
