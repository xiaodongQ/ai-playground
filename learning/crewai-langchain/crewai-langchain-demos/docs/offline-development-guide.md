# CrewAI 离线开发指南（2026 年 3 月更新）

> 📡 **离线开发专用**  
> 适用场景：无法直接访问 PyPI 或网络受限的开发环境  
> ⚠️ **最后更新**: 2026-03-15（已核实最新版本）

---

## ⚠️ 重要更新说明（2026-03-15）

### 包名和版本变更

| 包名 | 最新版本 | 说明 |
|------|---------|------|
| `crewai` | `0.5.0` | ✅ 正常发布 |
| `crewai-tools` | `1.10.1` | ✅ **存在**，但需要正确的 pip 版本 |

### 安装失败原因排查

如果你遇到 `ERROR: No matching distribution found crewai-tools`：

```bash
# 1. 检查 Python 版本（需要 3.10+）
python --version

# 2. 升级 pip（必须 21.0+）
python -m pip install --upgrade pip

# 3. 检查平台兼容性
pip --version

# 4. 尝试指定版本安装
pip install crewai-tools==1.10.1

# 5. 如果仍然失败，可能是平台 wheel 不可用，使用源码安装
pip install crewai-tools --no-binary :all:
```

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

### 2.1 创建依赖列表文件（2026 年 3 月更新）

```bash
# 创建项目目录
mkdir crewai-offline-demo
cd crewai-offline-demo

# 创建 requirements.txt（使用最新兼容版本）
cat > requirements.txt << EOF
crewai==0.5.0
crewai-tools>=1.8.0
python-dotenv>=1.0.0
pydantic>=2.0.0
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

# 传输到离线环境
scp crewai-offline-packages.tar.gz user@offline-server:/path/to/
```

### 2.4 在离线环境安装

```bash
# 解压离线包
tar -xzf crewai-offline-packages.tar.gz

# 离线安装
pip install --no-index --find-links=packages/ -r requirements.txt
```

---

## 3. 方案二：使用本地镜像源

### 3.1 搭建本地 PyPI 镜像（可选）

```bash
# 使用 pip2pi 工具
pip install pip2pi

# 创建镜像目录
mkdir -p /opt/pypi-mirror

# 下载依赖到镜像目录
pip2pi /opt/pypi-mirror/ crewai crewai-tools

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
```

---

## 4. 方案三：手动下载离线安装包

### 4.1 核心依赖列表（2026 年 3 月）

```
crewai==0.5.0
├── pydantic>=2.0.0
├── click>=8.0.0
└── python-dotenv>=1.0.0

crewai-tools>=1.10.1
├── beautifulsoup4>=4.12.0
├── requests>=2.31.0
└── lxml>=5.0.0
```

### 4.2 手动下载地址

| 包名 | PyPI 地址 |
|------|----------|
| crewai | https://pypi.org/project/crewai/#files |
| crewai-tools | https://pypi.org/project/crewai-tools/#files |

---

## 5. CrewAI 离线 Demo 运行

### 5.1 验证安装

```bash
# 检查 crewai
python -c "import crewai; print('crewai:', crewai.__version__)"

# 检查 crewai-tools
python -c "from crewai_tools import BaseTool; print('crewai-tools OK')"
```

### 5.2 离线工具替代方案

```python
# ✅ 离线工具（使用本地文件）
from crewai_tools import FileReadTool, DirectorySearchTool

file_tool = FileReadTool(file_path="local_data.txt")
dir_tool = DirectorySearchTool(directory="./data/")
```

---

## 6. 常见问题

### Q1: `pip install crewai-tools` 报错 "No matching distribution found"

**解决方案**:

```bash
# 1. 升级 pip
python -m pip install --upgrade pip

# 2. 检查 Python 版本（需要 3.10+）
python --version

# 3. 尝试指定版本
pip install crewai-tools==1.10.1

# 4. 使用源码安装（慢但可靠）
pip install crewai-tools --no-binary :all:

# 5. 检查平台兼容性
pip debug --verbose | grep "Compatible tags"
```

---

### Q2: 离线安装时提示缺少依赖

**解决方案**:

```bash
# 在有网环境重新下载，确保包含所有依赖
pip download -r requirements.txt -d packages/ --no-binary :none:
```

---

### Q3: crewai-tools 安装成功但导入失败

**检查**:

```bash
# 检查安装位置
pip show crewai-tools

# 检查 Python 路径
python -c "import sys; print('\n'.join(sys.path))"

# 尝试重新安装
pip uninstall crewai-tools
pip install crewai-tools --no-cache-dir
```

---

## 📚 相关文档

- [CrewAI 核心概念](./crewai-langchain-research.md#1-crewai-核心概念)
- [快速入门](./crewai-langchain-research.md#2-crewai-快速入门)
- [Demo 示例](../demos/)

---

**维护者**: Edu·伴学堂 📚  
**最后更新**: 2026-03-15（已核实最新版本）
