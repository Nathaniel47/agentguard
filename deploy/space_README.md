---
title: AgentGuard Arena
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Try to trick a tool-using AI agent past five guardrails
---

# AgentGuard Arena

A small tool-using AI agent (search, code, calendar, email, database) with five separate guardrails,
and an arena where you try to make it do something it should not. Whether you won is decided
automatically from what happened, not by a model. Everything is fake: the email is a mock outbox,
the customers are invented, and code runs in a sandbox.

Open the app, click an example, then try your own attack. The evaluation behind it is on the
Results page. Source code, design notes and write-up: https://github.com/Nathaniel47/agentguard
