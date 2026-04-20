"""Task evaluator using LLM (via CLI or API)."""

import subprocess
import asyncio
from typing import Dict, Tuple
from backend.config import load_config, get_logger

logger = get_logger(__name__)


class Evaluator:
    DEFAULT_PROMPT_TEMPLATE = """## 任务
{task_description}

## 执行结果
{execution_output}

## 评估
评分: X/10
一句话改进建议: （必须输出，用一句话说明如何改进）
"""

    def __init__(self, default_model: str = None):
        config = load_config()
        eval_config = config.get('evaluator', {})
        self.default_model = default_model or eval_config.get('model', '')
        self.use_cli = eval_config.get('use_cli', True)
        self.api_base = eval_config.get('api_base', '')
        self.timeout = 300

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
        if "评分:" in evaluation_text:
            try:
                score_line = [l for l in evaluation_text.split('\n') if '评分:' in l][0]
                score = int(score_line.split(':')[1].strip().split('/')[0])
            except Exception:
                pass
        return {"score": score, "comments": evaluation_text}

    def build_feedback_md(self, task_description: str,
                          execution_output: str,
                          evaluation_result: str,
                          iteration_count: int = 0) -> str:
        """Return concise evaluation result."""
        return evaluation_result

    async def evaluate(self, task_description: str,
                       execution_output: str,
                       original_requirements: str = None,
                       iteration_count: int = 0) -> Tuple[int, str]:
        """Run evaluation via CLI or API."""
        prompt = self.build_evaluation_prompt(
            task_description, execution_output, original_requirements, iteration_count
        )
        if self.use_cli:
            return await self._evaluate_via_cli(prompt)
        else:
            return await self._evaluate_via_api(prompt)

    async def _evaluate_via_cli(self, prompt: str) -> Tuple[int, str]:
        """Evaluate using Claude CLI."""
        try:
            model_arg = f" --model {self.default_model}" if self.default_model else ""
            cmd = f'claude --print{model_arg} "{prompt.replace("\\", "\\\\").replace("\"", "\\\"")}"'

            def _run_sync():
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=self.timeout
                )
                return result.stdout, result.stderr, result.returncode

            output, error, returncode = await asyncio.to_thread(_run_sync)

            if returncode != 0:
                logger.warning(f"Evaluator CLI non-zero: {returncode}, error: {error}")
                return 5, f"评估失败，使用默认评分\n\n{output or error}"

            evaluation_text = output.strip()
            parsed = self.parse_evaluation(evaluation_text)
            return parsed["score"], evaluation_text

        except subprocess.TimeoutExpired:
            logger.warning("Evaluator timeout")
            return 5, "评估超时，使用默认评分"
        except Exception as e:
            logger.error(f"Evaluator error: {e}")
            return 5, f"评估异常，使用默认评分: {e}"

    async def _evaluate_via_api(self, prompt: str) -> Tuple[int, str]:
        """API evaluation (placeholder)."""
        return 5, "API 评估待实现"