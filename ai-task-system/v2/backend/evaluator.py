import os
from typing import Dict
from openai import OpenAI


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

    def __init__(self, default_model: str = "gpt-4o"):
        self.default_model = default_model
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY environment variable not set")
            self._client = OpenAI(api_key=api_key)
        return self._client

    async def evaluate(self, task_description: str, execution_output: str,
                       original_requirements: str = None,
                       iteration_count: int = 0,
                       model: str = None) -> Dict:
        """使用真实 OpenAI LLM API 进行评估"""
        model = model or self.default_model
        prompt = self.build_evaluation_prompt(
            task_description, execution_output, original_requirements, iteration_count
        )

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
        return self.parse_evaluation(text)

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
