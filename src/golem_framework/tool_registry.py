# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""ToolRegistry — maps built-in tool names to their LangChain BaseTool instances.

Built-in tools are activated per agent via the ``agent.builtin_tools`` list
in ``config.yaml``.  Only the tools named there are loaded into the graph.

Adding a new built-in tool:
  1. Implement it under ``golem-runner/src/golem-runner/tools/``.
  2. Import it here and add it to ``BUILTIN_TOOLS``.
  3. Add its key to ``agent.builtin_tools`` in the relevant ``config.yaml``.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from tools.a2a_tools import delegate_to_agent
from tools.http_tools import http_health_check
from tools.system_tools import execute_bash_command

# Central registry — key matches the string used in config.yaml builtin_tools list.
BUILTIN_TOOLS: dict[str, BaseTool] = {
    "bash": execute_bash_command,
    "http_check": http_health_check,
    "delegate": delegate_to_agent,
}


def resolve_builtin_tools(names: list[str]) -> list[BaseTool]:
    """Return the BaseTool instances for the given tool names.

    Unknown names are silently skipped (the runner logs them separately).

    Args:
        names: List of tool key strings from ``agent.builtin_tools``.

    Returns:
        Ordered list of BaseTool instances for the recognised names.
    """
    return [BUILTIN_TOOLS[name] for name in names if name in BUILTIN_TOOLS]
