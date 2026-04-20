#!/bin/bash
# 运行内容创作 Crew

set -e

echo "🚀 启动内容创作系统..."
echo ""

# 创建输出目录
mkdir -p output

# 运行主程序
python main.py "$@"

echo ""
echo "✅ 完成！查看 output/ 目录获取结果。"
