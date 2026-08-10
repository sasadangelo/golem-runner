# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""In-memory A2A task store for the runner process."""

from .models import A2ATask


class TaskStore:
    """Thread-safe in-memory registry of A2A tasks for the runner.

    One instance is created at application startup and shared across all
    requests. In Phase 2 this will be backed by Redis via a LangGraph
    checkpointer, but the interface remains identical.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, A2ATask] = {}

    def add(self, task: A2ATask) -> None:
        """Persist a new task record.

        Args:
            task: The task to store.
        """
        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> A2ATask | None:
        """Retrieve a task by its ID.

        Args:
            task_id: The unique task identifier.

        Returns:
            The task, or None if not found.
        """
        return self._tasks.get(task_id)

    def list_all(self) -> list[A2ATask]:
        """Return all stored tasks."""
        return list(self._tasks.values())

    def clear(self) -> None:
        """Remove all tasks — used in tests to reset state between cases."""
        self._tasks.clear()
