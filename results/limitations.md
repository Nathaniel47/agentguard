# Limitations

Read these before quoting any number in `results_table.md`. They say where the results are weak and what would make them stronger.

## What the numbers do and do not show

1. **The scripted agent is a worst case, not a model.** It obeys every instruction it reads, so its "no guardrails" attack success (92% on the test split) is an upper bound, and "all five guardrails: 0%" means only that no case gets past the rules when the agent never resists. It says nothing about how a real model behaves. The real-model table is the more meaningful one, and it is small.
2. **The real-model sample is small.** Each configuration was run on 21 test attacks (3 per category) and 8 benign tasks. The 95% intervals are wide: 0 of 21 still allows a true rate of about 15%, and 8 of 21 spans roughly 21% to 59%. Differences of a few cases between configurations (for example G1 against G3 against G4) are not distinguishable from noise. Only the large gaps (no guardrails against G2 or all five) are safe to state.
3. **One model, one provider.** Results are for `openai/gpt-oss-20b` on Groq's free tier. The planned Gemini confirmation run was not done, so nothing here shows the findings carry over to another model.
4. **Seeds and variance.** The main real-model run uses temperature 0 and seed 42. Variation between seeds was measured only for "no guardrails" and "all five", on the same 21 attacks at temperature 0.7 with seeds 1, 2 and 3. "No guardrails" scored 38%, 48% and 38% (mean 41%, standard deviation 5.5 points, so about one or two cases flip between runs). "All five" scored 0% every time. All three seeds cover the full 21 attacks (seed 3 was finished the day after the free daily token allowance ran out; finished runs are kept). Other configurations have no variance estimate. The scripted agent is deterministic, so it has none.

## Why the cases favour the guardrails

5. **The guardrails were written knowing the cases.** I wrote G1's patterns and the G4 rules while looking at the dev split's wording, and the self-written cases (155 of 220) come from a fixed set of framings I also wrote. Test cases are held out from tuning but are not independent of how I think attacks look. Real attackers would write other phrasings.
6. **The keyword baseline did nothing, and that is partly the dataset.** Only 1 of 120 user-message cases contains one of the famous phrases the blocklist looks for, so the baseline matches nothing on the test split. A set built from more copy-pasted attacks would give the baseline more to catch. The comparison shows that exact-phrase blocking is weak, not how weak.
7. **No adaptive attacker.** Every attack is a fixed string played once. An attacker who sees a refusal and tries again, or who tunes wording against the filters, would do better. The arena will show some of this, but its results are not part of this evaluation.
8. **Sandbox cases are mostly independent of the model.** The 20 sandbox cases succeed whenever the agent runs the code, so G1, G3, G4 and G5 do nothing for them and G2 stops them only by switching on the strict profile. That profile is an allowlist in the same process tree, not a security boundary; the container is.

## Cost of the guardrails is understated

9. **The benign set is small and simple.** 40 tasks (28 in the test split, 8 in the real-model run), almost all single-step lookups. None is a workflow such as "read this email, then book a meeting", which is exactly the kind of task G3 (taint) and G2 (policy) refuse. The measured false-block rate of 0% therefore means "no false blocks on easy tasks", with an interval that still allows up to about 12% (scripted) or 32% (real model). G2 also refuses all calendar deletes and any email outside `example.test`, which a real user would sometimes want.
10. **Latency and tokens.** Replaying cached model replies makes wall-clock time meaningless, so latency is not reported. Cost is counted as model calls per run and estimated tokens (a rough characters-to-tokens rule). Guardrails that block early look cheap because they skip model calls, not because they are efficient.

## How success is measured

11. **State checks miss unanticipated harm.** Success is a canary in the answer, a mail to the attacker address, a deleted or changed row, a deleted event, or a sandbox record. An agent that causes harm another way (for example emailing an allowed address with the key in the body, or leaking a partial secret) is scored as a failure of the attack. Matching ignores case and punctuation but not paraphrase or encoding.
12. **G5 only sees the answer.** A secret sent through the email tool bypasses it. That is by design, but it means G5 alone looks worse on exfiltration than a deployed system with G2 would.
13. **Memory cases use one setup session and one later session** against a fresh store. Real memory poisoning plays out over many sessions and many notes.

## Harness problems found and fixed during the real-model run

The first real-model attempt gave misleading results for reasons that were the harness's, not the model's, so those records were discarded and the runs repeated after these fixes: the model often answers `{"name": ..., "arguments": ...}` instead of the requested format (now accepted); Groq sometimes rejects such replies as `tool_use_failed` and returns the text (now recovered); answers contain typographic spaces and dashes that failed the benign checks (now normalised); a sandbox case was scored as a leak because the model's refusal quoted the marker text (now only the sandbox's own output counts for those cases); G2 crashed when the model sent a list where a string was expected (fixed, and any guardrail error now blocks the action instead of letting it through); and Groq's `output_parse_failed` error was not recovered (now handled). The final runs was replayed from the response cache and reproduced every outcome exactly, so the numbers are repeatable. Any further model-specific formatting quirk would affect the real-model numbers in the same way.

## What would make the results stronger

- Run all 154 test attacks and all 28 benign tasks on the real model (about two to three days of the free token allowance, or a paid tier), and add the Gemini confirmation run.
- Add multi-step benign workflows and measure each guardrail's false-block rate against them.
- Add an adaptive attacker that retries after a refusal, and attacks written by people who have not seen the guardrails.
- Add a second scorer for obfuscated leaks (encodings, splitting a secret across messages).
- Measure latency on uncached runs.
