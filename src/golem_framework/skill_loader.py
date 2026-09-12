# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""SkillLoader — reads Persona (AGENTS.md) and Skills (skills/*.md) at startup.

Both files are mounted into the pod as a Kubernetes ConfigMap.  They are
read once at container start and never mutated.

The loader is deliberately I/O-only: it reads files and returns strings.
All prompt-assembly logic lives in LangGraphLoop so this module has no
dependency on LangChain or any LLM framework.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("runner.skill_loader")

_DEFAULT_AGENTS_MD_PATH: Path = Path("/app/AGENTS.md")
_DEFAULT_SKILLS_DIR: Path = Path("/app/skills")


class SkillLoader:
    """Loads the Persona and Skills from the agent's mounted ConfigMap files.

    Args:
        agents_md_path: Path to the ``AGENTS.md`` persona file.
        skills_dir:     Directory containing ``*.md`` skill files.
    """

    def __init__(
        self,
        agents_md_path: Path = _DEFAULT_AGENTS_MD_PATH,
        skills_dir: Path = _DEFAULT_SKILLS_DIR,
    ) -> None:
        self._agents_md_path = agents_md_path
        self._skills_dir = skills_dir

    def load_persona(self) -> str | None:
        """Read the Persona (AGENTS.md) if it exists.

        Returns:
            The file content stripped of leading/trailing whitespace,
            or None when the file is absent.
        """
        if self._agents_md_path.is_file():
            content = self._agents_md_path.read_text(encoding="utf-8").strip()
            logger.info("AGENTS.md loaded from %s (%d chars)", self._agents_md_path, len(content))
            return content
        return None

    def load_skills(self) -> dict[str, str]:
        """Scan the skills directory and return a mapping of name → content.

        Returns:
            Dict mapping the stem of each ``.md`` filename to its content,
            e.g. ``{"read-logs": "# Read Logs skill …"}``.
            Empty dict when the directory does not exist or has no ``.md`` files.
        """
        if not self._skills_dir.is_dir():
            return {}
        index: dict[str, str] = {}
        for md_path in sorted(self._skills_dir.glob("*.md")):
            name = md_path.stem
            index[name] = md_path.read_text(encoding="utf-8").strip()
            logger.info("Skill '%s' indexed from %s", name, md_path)
        return index
