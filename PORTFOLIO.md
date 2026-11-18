# Portfolio card

## Description (120 words)

AgentGuard asks how safe a tool-using LLM agent really is, and which defences earn their place. I built a small agent with five tools (search, sandboxed code, calendar, mock email, database) and persistent memory, then wrapped it in five separate guardrails. An automated red-team harness runs 220 attacks, including indirect prompt injection, memory poisoning and sandbox escapes, and scores each one from system state, with no LLM judge. Against a worst-case agent, attacks succeeded 92% of the time with no guardrails and 0% with all five. Tool-level least privilege beat a phrase blocklist, which stopped nothing. A public arena lets visitors attack the agent live. Limits are published alongside the results, and every number is reproducible. Python, FastAPI, SQLite, Docker, Groq.

Links: demo https://agentguard-9q9m.onrender.com, code https://github.com/Nathaniel47/agentguard, write-up `docs/WRITEUP.md`.

## One sentence for emailing researchers

My project AgentGuard measures, with automatic state-based scoring and no LLM judge, how well separate guardrails (least-privilege tool policy, taint tracking of untrusted tool output, a memory write gate) defend a tool-using LLM agent against indirect prompt injection and memory poisoning, following the threat models of InjecAgent, AgentDojo and AgentPoison.

Use as is for groups working on LLM agents, agent memory or agentic-system security. For a memory-focused group, replace the ending with "...with a provenance-tracked long-term memory whose write gate stops all 21 poisoning attacks in my test split". The one-click demo is live at https://agentguard-9q9m.onrender.com (free tier: allow up to a minute for the first load).
