from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    id: str
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None


@dataclass
class Plan:
    root_task: Task
    subtasks: List[Task] = field(default_factory=list)

