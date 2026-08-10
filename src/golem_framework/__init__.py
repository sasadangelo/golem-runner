# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""golem-framework — LLM framework abstraction, LLM Gateway, and Graph Plugin system.

Phase 2 placeholder.  In the MVP all framework logic lives directly in
``golem-runner/agent.py`` (LangGraph loop + WatsonX client).  This package
will be populated in Phase 2 when the runner is split into three repositories:

    golem-runner        ← thin entrypoint
    golem-agent-sdk     ← A2A identity + task lifecycle  (already extracted)
    golem-framework     ← agentic loop + LLM Gateway + Graph Plugin  (this package)

Sub-modules planned for Phase 2:
    loop/
        base.py           abstract AgentLoop interface
        langgraph.py      built-in ReAct loop (default)
        plugin.py         custom graph loader from /app/graph/pipeline.py
        autogen.py        Phase 3
        crewai.py         Phase 3
    llm_gateway/
        base.py           abstract LLMClient interface
        watsonx.py        provider=watsonx, protocol=watsonx
        ollama_native.py  provider=ollama,  protocol=ollama
        ollama_openai.py  provider=ollama,  protocol=openai
"""
