"""
AI Task Pickup System - Task Evaluator
Evaluates task execution results using AI models
"""
import os
import asyncio
from datetime import datetime
from typing import Optional

from models import Task, Evaluation, TaskType


class TaskEvaluator:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "minimax/MiniMax-M2.7"
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", "")
        self.model = model
    
    def _build_evaluation_prompt(self, task: Task) -> str:
        """Build evaluation prompt based on task type and result"""
        
        base_info = f"""Task: {task.title}
Type: {task.type}
Description: {task.description}

"""
        
        if task.type == TaskType.CODE_DEV:
            evaluation_criteria = """
## Evaluation Criteria for Code Development:
1. **Completeness** (0-100): Did the solution implement all required features?
2. **Correctness** (0-100): Is the code correct and bug-free?
3. **Code Quality** (0-100): Is the code clean, well-structured, and maintainable?
4. **Efficiency** (0-100): Is the implementation efficient?
"""
        else:  # DOC_SUMMARY
            evaluation_criteria = """
## Evaluation Criteria for Document Summary:
1. **Completeness** (0-100): Did the summary cover all key points?
2. **Accuracy** (0-100): Is the analysis accurate and insightful?
3. **Clarity** (0-100): Is the summary clear and well-organized?
4. **Value** (0-100): Does it provide actionable insights?
"""
        
        result_section = f"""
## Execution Result:
{task.result or "(No result)"}
"""
        
        solution_section = f"""
## Solution Approach:
{task.solution or "(No solution recorded)"}
"""
        
        instruction = """
## Your Task
Evaluate the above task execution result and provide:
1. Quality Score (0-100): Overall quality of the output
2. Efficiency Score (0-100): Based on execution time and resource usage
3. Overall Score (0-100): Weighted average (quality 70% + efficiency 30%)
4. Brief Comment: Key observations and suggestions

Format your response as:
```
Quality Score: [0-100]
Efficiency Score: [0-100]
Overall Score: [0-100]
Comment: [Your brief evaluation]
```
"""
        
        return base_info + evaluation_criteria + result_section + solution_section + instruction
    
    async def evaluate_task(self, task: Task) -> Evaluation:
        """
        Evaluate a completed task
        """
        prompt = self._build_evaluation_prompt(task)
        
        # Calculate efficiency based on timestamps
        efficiency_score = 50  # Default
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()
            # Penalize very slow executions (>30 min = low score)
            if duration < 300:  # < 5 minutes
                efficiency_score = 90
            elif duration < 900:  # < 15 minutes
                efficiency_score = 75
            elif duration < 1800:  # < 30 minutes
                efficiency_score = 60
            else:
                efficiency_score = 40
        
        # Try to use API for quality evaluation
        quality_score = await self._call_ai_api(prompt)
        
        if quality_score is None:
            # Fallback: basic evaluation based on result presence
            quality_score = 50
            if task.result:
                if len(task.result) > 1000:
                    quality_score = 70
                if "Error" in task.result:
                    quality_score = 30
        
        # Overall score: quality 70% + efficiency 30%
        overall_score = (quality_score * 0.7) + (efficiency_score * 0.3)
        
        # Generate comment
        if quality_score >= 80:
            comment = "Excellent execution, exceeds expectations"
        elif quality_score >= 60:
            comment = "Good execution, meets most requirements"
        elif quality_score >= 40:
            comment = "Average execution, some areas for improvement"
        else:
            comment = "Below average, requires significant revision"
        
        return Evaluation(
            quality_score=quality_score,
            efficiency_score=efficiency_score,
            overall_score=overall_score,
            comment=comment,
            evaluator=self.model,
            evaluated_at=datetime.now()
        )
    
    async def _call_ai_api(self, prompt: str) -> Optional[float]:
        """
        Call AI API for evaluation
        Returns score or None if failed
        """
        if not self.api_key:
            return None
        
        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url if self.base_url else None
            )
            
            response = client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Parse score from response
            for line in response_text.split('\n'):
                line = line.strip()
                if 'Overall Score:' in line or 'overall score:' in line.lower():
                    # Extract number
                    parts = line.split(':')
                    if len(parts) >= 2:
                        try:
                            score = float(parts[1].strip())
                            return min(max(score, 0), 100)
                        except ValueError:
                            pass
            
            return None
            
        except ImportError:
            # anthropic package not installed
            return None
        except Exception as e:
            print(f"API call failed: {e}")
            return None
    
    async def evaluate_task_simple(self, task: Task) -> Evaluation:
        """
        Simple evaluation without API call
        Based on result analysis
        """
        quality_score = 50
        efficiency_score = 50
        
        # Analyze result
        if task.result:
            result_lower = task.result.lower()
            
            # Check for errors
            if "error" in result_lower or "failed" in result_lower:
                quality_score -= 30
            
            # Check for completeness indicators
            if "implemented" in result_lower or "completed" in result_lower:
                quality_score += 10
            if "summary" in result_lower or "key points" in result_lower:
                quality_score += 10
            
            # Length indicator
            if len(task.result) > 500:
                quality_score += 10
            elif len(task.result) < 50:
                quality_score -= 20
        
        # Time-based efficiency
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()
            if duration < 120:  # < 2 min
                efficiency_score = 90
            elif duration < 300:  # < 5 min
                efficiency_score = 80
            elif duration < 600:  # < 10 min
                efficiency_score = 70
            elif duration < 1800:  # < 30 min
                efficiency_score = 60
            else:
                efficiency_score = 40
        
        # Clamp scores
        quality_score = max(0, min(100, quality_score))
        efficiency_score = max(0, min(100, efficiency_score))
        
        # Overall
        overall_score = (quality_score * 0.7) + (efficiency_score * 0.3)
        
        # Comment
        if overall_score >= 80:
            comment = "Excellent work"
        elif overall_score >= 60:
            comment = "Good work"
        elif overall_score >= 40:
            comment = "Acceptable, some improvements needed"
        else:
            comment = "Requires significant improvement"
        
        return Evaluation(
            quality_score=quality_score,
            efficiency_score=efficiency_score,
            overall_score=overall_score,
            comment=comment,
            evaluator="Simple Evaluator",
            evaluated_at=datetime.now()
        )
