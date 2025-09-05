from __future__ import annotations

from typing import Callable, Dict, List, Optional
from .models import Task


class Scheduler:
    """Simple placement scheduler. Can assign tasks to local or remote nodes.

    discovery: callable -> List[str] of node IDs
    submit: callable(node_id, task) -> bool
    """

    def __init__(
        self,
        discovery: Callable[[], List[str]] | None = None,
        submit: Callable[[str, Task], bool] | None = None,
    ) -> None:
        self.discovery = discovery or (lambda: ["local"])
        self.submit = submit or (lambda node, task: True)

    def place(self, task: Task) -> str:
        nodes = self.discovery()
        # naive: prefer local, otherwise first remote
        node = nodes[0] if nodes else "local"
        self.submit(node, task)
        return node

