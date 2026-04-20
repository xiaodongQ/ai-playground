"""Structured prompts for human confirmation and output parsing."""

HUMAN_CONFIRM_PROMPT = """你是一个任务执行助手。当前任务需要人工确认。
任务描述: {task_description}
执行输出: {output}

请用以下JSON格式输出（只输出JSON，不要其他内容）:
{{
  "confirm_type": "single_choice|fill_blank|confirm|continue_session",
  "question": "要问用户的具体问题",
  "options": ["选项1", "选项2"],
  "fill_blanks": [
    {{"field": "字段名", "label": "显示标签", "default": "默认值"}}
  ],
  "continue_prompt": "下一轮对话的系统提示"
}}
"""

# Signal patterns to detect interactive prompts that need user confirmation
INTERACTIVE_SIGNALS = [
    '?', '[Y/n]', '[是/否]', '[y/n]', '[Yes/No]',
    '是否要', '要不要', '是否需要', '请确认',
    '不确定', '需要更多信息', '请告诉我', '请选择',
    'Press Enter', '按 Enter', '输入选择',
    'Continue?', 'Proceed?', 'Confirm',
]


def build_confirm_prompt(task_description: str, output: str) -> str:
    """Build a human confirmation prompt from task description and output."""
    return HUMAN_CONFIRM_PROMPT.format(
        task_description=task_description,
        output=output
    )