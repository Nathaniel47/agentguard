# AgentGuard: measuring which defences protect a tool-using LLM agent

*Technical write-up. Code, data and run records: https://github.com/Nathaniel47/agentguard*

## 1. Problem

An LLM agent that can send email, edit a calendar, query a database and run code is a confused deputy. It acts with the user's authority but reads text written by other people: web pages, inbox messages, calendar titles, database rows, notes saved in earlier sessions. Any of that text can contain instructions, and the model cannot reliably tell them from the user's own. This is indirect prompt injection (Greshake et al., 2023), measured on agents by InjecAgent and AgentDojo, and extended across sessions by memory poisoning (AgentPoison, Chen et al., 2024).

Many defences are proposed, but they are usually shown one at a time, against one attack style, on a system built to demonstrate them. The question this project answers is practical: **for one small agent, which of several separate defences stops which kind of attack, at what cost to normal work, and how sure can we be?** The aim is a harness that makes that question cheap to ask, not a claim that any defence is sufficient.

## 2. Method

**The agent.** A plain Python loop, no framework. The model replies with one JSON object, either a tool call or a final answer, for at most six steps. There are five tools: search over a small document set, a sandboxed Python runner, a calendar, a mock email (writes to an outbox, never sends) with a readable inbox, and a SQLite database of invented customers that also holds a fake API key. Every tool result carries a trusted or untrusted flag: anything another person could have written is untrusted. A long-term memory stores notes with their provenance, including whether untrusted content had been read when the agent wrote the note.

**Five guardrails**, each a separate hook the loop calls at fixed points (user input, before a tool call, after a tool result, before a memory write, on the final answer):

| | Guardrail | Idea |
|---|---|---|
| G1 | Input screen | pattern list for override wording, fake system markers, role-play, authority claims |
| G2 | Tool policy | least privilege: email only to the company domain, read-only database without the config table, no calendar deletes, call caps, and the strict code sandbox |
| G3 | Taint | after any untrusted content is in context, refuse tools that change the world or send data out |
| G4 | Memory write gate | refuse notes that look like standing orders, impersonate the system or user, or name outside addresses |
| G5 | Output filter | redact known secrets, canary tokens and PII shapes from the answer |

A keyword blocklist of famous injection phrases is the simple baseline. If a guardrail crashes, the loop blocks the action rather than letting it through.

**The cases.** 220 attacks and 40 benign tasks, in a fixed split (seed 42): 30% dev for tuning, 70% test for reporting. Attacks cover direct injection (40), indirect injection through a page, email, calendar title or database row (50), jailbreak (30), tool abuse (30), memory poisoning (30, a setup session then an innocent later session), data exfiltration (20) and sandbox escape (20). 65 cases reuse the attacker wording of InjecAgent (MIT) and deepset/prompt-injections (Apache-2.0); 155 are self-written. Only wording is reused: every goal and success marker is defined for this app.

**Scoring, with no LLM judge.** Success is read from state: a canary token in the answer, a mail to the attacker address in the outbox, a deleted or changed database row, a deleted calendar event, a file written outside the sandbox, or the sandbox's own record of what the code did. Matching ignores case and punctuation. Benign tasks pass or fail on an answer or outbox check. Each run gets a fresh world, so cases cannot affect one another.

**Two kinds of agent.** A deterministic scripted agent that obeys every instruction it reads gives a free, repeatable worst case and runs the whole grid in minutes. A real model (Groq `openai/gpt-oss-20b`, free tier) runs a seeded sample, 3 attacks per category plus 8 benign tasks, under all eight configurations, with temperature and seed recorded and replies cached so any run can be replayed exactly.

**Metrics.** Attack success rate per category and configuration with a 95% Wilson interval; benign tasks passed and false blocks; model calls and estimated tokens per run; spread over three seeds for the two key configurations.

## 3. Results

Attacks that succeeded, test split:

| Configuration | Scripted agent (154 attacks) | Real model (21 attacks) | Benign passed |
|---|---|---|---|
| No guardrails | 92% [87-95] | 38% [21-59] | 100% |
| Keyword blocklist | 92% | 38% | 100% |
| G1 input screen | 66% | 33% | 100% |
| G2 tool policy | 31% | 5% [1-23] | 100% |
| G3 taint | 53% | 33% | 100% |
| G4 memory gate | 79% | 33% | 100% |
| G5 output filter | 60% | 29% | 100% |
| All five | 0% [0-2] | 0% [0-15] | 100% |

Square brackets are 95% intervals. The scripted agent's categories show what each guardrail is for. G1 cuts direct injection from 100% to 21% and jailbreak to 14%, but leaves indirect injection, memory poisoning, exfiltration and sandbox cases at their no-guardrail rates, because those attacks do not pass through the user's message. G2 and G3 cut indirect injection from 100% to 11%. G2 stops all tool-abuse and exfiltration attacks and, by switching on the strict sandbox, all sandbox escapes. G4 removes memory poisoning entirely (21 of 21 to 0) and affects nothing else. G5 helps only where the harm is the answer text.

Three findings are robust enough to state:

1. **Defences are complementary.** No single guardrail covers more than a few categories, and only the combination reaches zero.
2. **Least privilege beat detection.** Restricting what the agent may do (G2) was the best single guardrail on both agents, while the phrase blocklist caught nothing and G1's pattern list caught only attacks that look like attacks.
3. **Real models resist some attacks unaided, and fail in different places.** The real model ignored every indirect injection in the sample (0 of 3) but carried out all 3 tool-abuse requests, because the user asked for them. That is a policy failure no amount of injection detection fixes.

Across seeds 1 to 3 at temperature 0.7, "no guardrails" scored 38%, 48%, 38% (std dev 5.5 points, so one or two cases flip between runs), and "all five" scored 0% each time. No benign task was blocked by any configuration. Guardrails that stop a run early used fewer model calls: 2.2 calls per run for all five against 2.5 with none.

## 4. Lessons learned

**Validate the harness against the real model before trusting any number.** The first real-model run looked plausible and was wrong. The model answered `{"name": ..., "arguments": ...}` instead of the requested format, so many benign tasks failed for a parsing reason; Groq rejected some replies with errors that still carried the text; answers used typographic spaces and dashes that broke exact matching; one sandbox case was scored as a leak because the model's refusal quoted the marker; and a guardrail crashed when the model sent a list where a string belonged. Each fix is tested, the affected runs were discarded and redone, and the final run was replayed from the response cache and reproduced every outcome. The scripted agent could never have found any of these.

**A guardrail that crashes is a vulnerability.** The malformed-argument crash is exactly what an attacker would try to provoke. The loop now fails closed.

**State-based scoring is worth its constraints.** It forces every attack to have a checkable goal, makes results arguable only on the marker's definition, and allows free replays. Its cost is false negatives: harm done in a way the marker does not anticipate is not counted.

**Hold out the test split, and still distrust it.** I wrote G1's patterns while looking at the dev wording, and the self-written cases share my idea of what an attack looks like. The test split is held out from tuning but not independent of the author. The blocklist's failure is partly a product of this: only one of the 120 user-message cases uses a famous phrase.

**Free-tier limits shape the experiment.** About 1,000 tokens per case and 200,000 tokens per day meant sampling the real model and spreading runs over days, with a resumable runner and a persistent daily budget. The scripted agent carried the full grid.

## 5. Limitations and future work

The scripted agent is a worst case, not a model, so its numbers are an upper bound. The real-model sample is small (an interval of 0 to 15% around 0 of 21), covers one model, and the variance estimate covers two configurations. The benign tasks are single-step lookups, so false-block rates are understated: G2 refuses every calendar delete and every outside email, and G3 would refuse a read-then-act workflow. Every attack is a fixed string; an adaptive attacker would do better. G5 sees only the answer, and the strict sandbox is an allowlist rather than a security boundary, so the public demo adds a locked-down container.

Next steps, in order of value: run all 154 test attacks and all benign tasks on the real model and add a second model; add multi-step benign workflows and measure each guardrail's false-block rate against them; add an adaptive attacker and attacks written by people who have not seen the guardrails; compare learned classifiers against the rule lists for G1 and G4; and export traces to OpenTelemetry. Full list, with the evidence for each point: `results/limitations.md`.

## References

Greshake et al., "Not what you've signed up for: compromising real-world LLM-integrated applications with indirect prompt injection" (2023). Zhan et al., "InjecAgent: benchmarking indirect prompt injections in tool-integrated LLM agents" (2024). Debenedetti et al., "AgentDojo: a dynamic environment to assess attacks and defences for LLM agents" (2024). Chen et al., "AgentPoison: red-teaming LLM agents via poisoning memory or knowledge bases" (2024). OWASP Top 10 for LLM Applications, "Excessive Agency".
