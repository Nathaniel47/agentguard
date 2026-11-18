# Deploying the demo (Render, free)

The demo is one container: a FastAPI app that also serves the arena, leaderboard, trace viewer and results pages. It runs on Render's free web service straight from this repository's `Dockerfile`, with a public URL and no sign-up for visitors. Steps marked **[your login]** need your own account; everything else is a command.

Live deployment: https://agentguard-9q9m.onrender.com

## What you need

- A free Render account, signed up with GitHub **[your login]**.
- Your Groq API key. Without it the arena still works, but against the offline scripted agent, which falls for everything.

## Steps

1. **Create the service [your login].** In Render choose New, then Web Service, and connect the public repository `Nathaniel47/agentguard`. Set:
   - Runtime: **Docker** (Render finds the `Dockerfile` at the repository root)
   - Instance type: **Free**
   - Health check path: `/health`

2. **Add the key and settings [your login].** In the service's Environment tab:

   | Kind | Name | Value |
   |---|---|---|
   | Environment variable (secret) | `AGENTGUARD_GROQ_API_KEY` | your Groq key |
   | Environment variable | `AGENTGUARD_ARENA_BACKEND` | `groq` |
   | Environment variable | `AGENTGUARD_ARENA_DAILY_CAP` | `100` |

   The key lives only in Render's environment. It is never in the code or the image.

3. **Deploy.** Render builds the image and starts it (a few minutes). Every push to `main` redeploys automatically.

4. **Check it works** from this repository:

   ```bash
   python deploy/smoke_test.py https://YOUR-SERVICE.onrender.com
   ```

   It should print `model: openai/gpt-oss-20b`, then three "ok" lines and `smoke test passed`. It uses 3 of the day's attempts. If the first run says the server did not become healthy, the free instance was asleep; run it again.

## Things to know

- **Cold starts.** Render spins a free web service down after 15 minutes without traffic and wakes it on the next request, which takes up to about a minute. A running service answers in under a second.
- **The leaderboard resets** whenever the service restarts, redeploys or spins down, because free instances have no persistent disk. The results page is unaffected.
- **Memory.** The free instance has 512 MB of RAM. The sandbox kills code that passes its own 400 MB cap, but the app plus a code run can come close. If the service restarts with an out-of-memory message in its logs, lower `MEMORY_CAP_MB` in `agentguard/tools/sandbox.py`.
- **Cost control.** The arena counts every attempt against `AGENTGUARD_ARENA_DAILY_CAP` (UTC day), allows 6 attempts per visitor per 10 minutes, and stops with a clear message when Groq's free daily token allowance is used up. About 1,000 to 2,000 tokens per attempt means 100 attempts stay well inside the 200,000-token limit. Setting the cap to `0` pauses the arena without redeploying.
- **Safety.** Code from visitors runs only in the strict sandbox profile, in a container started as a non-root user. The sandboxed child process receives none of the parent's environment, so it never sees the Groq key. The email tool writes to an in-memory outbox and the data is invented.
- **What is public.** Nicknames (plain letters, digits, spaces, `_`, `-`, 20 characters) and trace links are visible to everyone, and traces include the visitor's attack text. The page tells visitors not to type anything personal. If someone posts something abusive, set the cap to `0`, restart the service (this clears the leaderboard and traces) and re-enable.

## Other hosts

- **Hugging Face Spaces.** Docker Spaces now require a paid plan (PRO). Only Static Spaces are free, which cannot run this app's Python backend. `deploy/export_space.py` still builds an upload folder with the Space README header if you have a paid plan: run it, push `build/space/` to a Docker Space, add the same variables, then run the smoke test.
- **Docker, locked down like production:** `docker compose up --build`, then open http://localhost:7860.
- **Without Docker:** `uvicorn api.main:app --port 7860` after `pip install -r requirements.txt`.
- **Anything else that runs a Dockerfile** (Fly.io, a small VM): set the same variables and the `PORT` the host expects; the image reads `PORT` and defaults to 7860.
