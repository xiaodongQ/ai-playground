from typing import Dict

class Evaluator:
    DEFAULT_PROMPT_TEMPLATE = """## 任务
{task_description}

## 原始需求
{original_requirements}

## 执行结果
{execution_output}

## 评估报告
请对上述执行结果进行评估，输出以下格式：

### 评分: X/10
### 优点
- ...

### 问题
- ...

### 改进建议
1. ...

## 反馈给执行引擎
基于评估报告的改进建议，请生成新的执行指令...
"""

    def __init__(self, default_model: str = "claude-opus-4-6"):
        self.default_model = default_model

    def build_evaluation_prompt(self, task_description: str,
                                 execution_output: str,
                                 original_requirements: str = None,
                                 iteration_count: int = 0) -> str:
        return self.DEFAULT_PROMPT_TEMPLATE.format(
            task_description=task_description,
            original_requirements=original_requirements or task_description,
            execution_output=execution_output
        )

    def parse_evaluation(self, evaluation_text: str) -> Dict:
        score = 5
        comments = evaluation_text

        # 简单解析评分
        if "评分:" in evaluation_text:
            try:
                score_line = [l for l in evaluation_text.split('\n') if '评分:' in l][0]
                score = int(score_line.split(':')[1].strip().split('/')[0])
            except:
                pass

        return {"score": score, "comments": evaluation_text}

    def build_feedback_md(self, task_description: str,
                          execution_output: str,
                          evaluation_result: str,
                          iteration_count: int = 0) -> str:
        return f"""## 任务
{task_description}

## 执行结果
{execution_output}

## 评估报告
{evaluation_result}

## 反馈给执行引擎
基于上述评估报告的改进建议，请重新执行任务。这是第 {iteration_count + 1} 次迭代。
"""