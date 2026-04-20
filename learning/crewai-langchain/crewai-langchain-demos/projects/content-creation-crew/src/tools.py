"""
工具模块

提供内容创作过程中可能用到的工具
"""

from crewai_tools import tool

@tool
def word_count(text: str) -> str:
    """
    统计文本字数。
    
    Args:
        text: 要统计的文本
    
    Returns:
        字数统计结果
    """
    chars = len(text)
    words = len(text.split())
    lines = len(text.splitlines())
    return f"字符数：{chars}, 单词数：{words}, 行数：{lines}"

@tool
def check_code_syntax(code: str, language: str = "python") -> str:
    """
    检查代码语法（简化版，实际使用需要集成编译器/解释器）。
    
    Args:
        code: 要检查的代码
        language: 编程语言
    
    Returns:
        检查结果
    """
    # 简化实现，实际应该调用编译器/解释器
    if not code.strip():
        return "错误：代码为空"
    
    if language == "python":
        try:
            compile(code, '<string>', 'exec')
            return "语法检查通过 ✓"
        except SyntaxError as e:
            return f"语法错误：{str(e)}"
    else:
        return f"暂不支持{language}的语法检查"

@tool
def get_reading_time(text: str) -> str:
    """
    估算阅读时间。
    
    Args:
        text: 要估算的文本
    
    Returns:
        阅读时间（分钟）
    """
    words = len(text.split())
    # 平均阅读速度：200 词/分钟
    minutes = words / 200
    return f"预计阅读时间：{minutes:.1f} 分钟（约{int(minutes)}分钟）"

@tool
def extract_headings(text: str) -> str:
    """
    提取 Markdown 文本的标题结构。
    
    Args:
        text: Markdown 文本
    
    Returns:
        标题结构
    """
    headings = []
    for line in text.splitlines():
        if line.startswith('#'):
            headings.append(line)
    
    if not headings:
        return "未找到标题"
    
    return "标题结构:\n" + "\n".join(headings)
