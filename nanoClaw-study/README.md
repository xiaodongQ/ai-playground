# nanoClaw 深度学习指南

> 系统性学习 nanoClaw - 超轻量级安全 AI 助手框架

## 📖 学习路线

本教程带你深入理解 [nanoClaw](https://github.com/ysz/nanoClaw) 的设计思想、架构实现和扩展开发。

```
nanoClaw-study/
├── README.md              # 本文件 - 学习指南入口
├── 01-项目概览.md         # 项目定位、特性、与 OpenClaw 对比
├── 02-架构设计.md         # 整体架构、模块划分、数据流
├── 03-核心源码解析.md     # 核心源码逐行分析、设计模式
├── 04-实践指南.md         # 安装部署、配置、使用示例
└── 05-扩展开发.md         # 添加新功能、贡献代码、开发环境
```

## 🎯 学习目标

完成本教程后，你将能够：

- ✅ 理解 nanoClaw 的设计理念和核心特性
- ✅ 掌握整体架构和模块间的协作关系
- ✅ 深入理解核心源码的实现细节
- ✅ 独立部署和配置 nanoClaw
- ✅ 开发自定义技能和工具
- ✅ 为项目贡献代码

## 📝 前置知识

- **Python 基础**: 异步编程 (asyncio)、类型注解
- **AI Agent 概念**: LLM、Tool Calling、ReAct 模式
- **Linux 基础**: 命令行操作、文件系统权限
- **Git 基础**: 代码版本管理

## 🚀 快速开始

### 1. 阅读顺序建议

```
第一天：01-项目概览.md → 02-架构设计.md
第二天：03-核心源码解析.md (上)
第三天：03-核心源码解析.md (下)
第四天：04-实践指南.md (动手安装)
第五天：05-扩展开发.md (动手开发)
```

### 2. 实践环境准备

```bash
# 1. 克隆 nanoClaw 仓库
git clone https://github.com/ysz/nanoClaw.git
cd nanoClaw

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 运行测试
pytest
```

## 📊 项目核心数据

| 指标 | nanoClaw | OpenClaw |
|------|----------|----------|
| 代码行数 | ~3,000 | ~430,000 |
| 安装时间 | 2 分钟 | 复杂配置 |
| 依赖数量 | 6 个核心 | 大量依赖 |
| 安全性 | 默认安全 | 需手动配置 |
| 启动速度 | <2 秒 | 较慢 |

## 🎓 每章结构

每章包含：
- **理论讲解**: 核心概念和原理
- **代码示例**: 丰富的源码片段
- **图表辅助**: 架构图和流程图
- **小结**: 要点回顾
- **练习题**: 巩固所学知识

## 💡 学习建议

1. **边读边跑**: 不要只读代码，要运行起来看效果
2. **做笔记**: 在 `memory/` 目录下记录你的学习心得
3. **提问题**: 遇到不理解的地方，先思考再查阅
4. **动手改**: 尝试修改代码，观察变化
5. **分享输出**: 写博客或教别人是最好的学习

## 🔗 相关资源

- **官方仓库**: https://github.com/ysz/nanoClaw
- **OpenClaw**: https://github.com/openclaw-ai/openclaw
- **Python asyncio**: https://docs.python.org/3/library/asyncio.html
- **ReAct Pattern**: https://react-lm.github.io/

## 📞 学习支持

遇到问题？
1. 先查看本章的"常见问题"部分
2. 在仓库中搜索相关代码
3. 运行 `nanoclaw doctor` 检查环境

---

**开始学习吧！** 🦀 从 [01-项目概览.md](./01-项目概览.md) 开始你的 nanoClaw 之旅。
