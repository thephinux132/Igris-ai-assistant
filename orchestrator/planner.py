from __future__ import annotations

from typing import Callable, List
from .models import Plan, Task


class Planner:
    """Hierarchical task planner using an LLM decomposer or rule-based fallback.

    llm_decompose: callable that returns a list of subtask dicts for a given task.
    """

    def __init__(self, llm_decompose: Callable[[str, dict], List[dict]] | None = None) -> None:
        self.llm_decompose = llm_decompose

    def plan(self, goal: str, params: dict | None = None) -> Plan:
        root = Task(id="root", name=goal, params=params or {})
        if self.llm_decompose is None:
            # fallback 3-phase model: plan -> execute -> verify
            subs = [
                Task(id="plan", name="plan", parent_id=root.id),
                Task(id="execute", name="execute", parent_id=root.id),
                Task(id="verify", name="verify", parent_id=root.id),
            ]
            return Plan(root_task=root, subtasks=subs)
        items = self.llm_decompose(goal, params or {})
        subs = [Task(id=f"t{i}", name=i.get("name", f"step_{idx}"), params=i, parent_id=root.id) for idx, i in enumerate(items)]
        return Plan(root_task=root, subtasks=subs)

