# Deploying the demo (Hugging Face Spaces)

The demo is one container: a FastAPI app that also serves the arena, leaderboard, trace viewer and results pages. Hugging Face Spaces runs a Docker container for free, with a public URL and no sign-up for visitors. Steps marked **[your login]** need your own account; everything else is a command.

## What you need

- A free Hugging Face account **[your login]**, and an access token with *write* permission (Settings, Access Tokens).
- Your Groq API key (the one in `.env`). Without it the arena still works, but against the offline scripted agent, which falls for everything.

## Steps

1. **Build the upload folder** (copies only what the app needs, plus the Space README with its YAML header):

   ```bash
   python deploy/export_space.py
   ```

   This creates `build/space/`. It is git-ignored.

2. **Create the Space [your login].** Go to https://huggingface.co/new-space. Choose a name (for example `agentguard-arena`), SDK **Docker**, template **Blank**, hardware **CPU basic (free)**, visibility **Public**.

3. **Add the key and settings [your login].** In the Space, open Settings, then *Variables and secrets*:

   | Kind | Name | Value |
   |---|---|---|
   | Secret | `AGENTGUARD_GROQ_API_KEY` | your Groq key |
   | Variable | `AGENTGUARD_ARENA_BACKEND` | `groq` |
   | Variable | `AGENTGUARD_ARENA_DAILY_CAP` | `100` |

   The key lives only in the Space's secret store. It is never in the code or the image.

4. **Upload the files.** Replace `YOUR_NAME` and the Space name:

   ```bash
   git clone https://huggingface.co/spaces/YOUR_NAME/agentguard-arena build/hf-space
   cp -r build/space/. build/hf-space/
   cd build/hf-space
   git add -A
   git commit -m "Deploy AgentGuard arena"
   git push
   ```

   When asked for a password, paste your Hugging Face access token **[your login]**. (Username is your Hugging Face username.)

5. **Wait for the build** (a few minutes; the Space page shows the log). Then open `https://YOUR_NAME-agentguard-arena.hf.space`.

6. **Check it works** from this repo:

   ```bash
   python deploy/smoke_test.py https://YOUR_NAME-agentguard-arena.hf.space
   ```

   It should print `model: openai/gpt-oss-20b`, then three "ok" lines and `smoke test passed`. It uses 3 of the day's attempts.

7. **Add the link** to the top of `README.md` (Step 8 does this too).

To update later: change the code, run `python deploy/export_space.py`, copy into the clone, commit and push.

## Things to know

- **Cold starts.** Free Spaces go to sleep after a period with no visitors (currently about two days) and take a minute or two to wake. A running Space loads the page in well under a second.
- **The leaderboard resets** when the Space restarts or is rebuilt, because free Spaces have no persistent disk. Persistent storage is a paid option; for a portfolio demo the reset is acceptable and the results page is unaffected.
- **Cost control.** The arena counts every attempt against `AGENTGUARD_ARENA_DAILY_CAP` (UTC day), allows 6 attempts per visitor per 10 minutes, and stops with a clear message when Groq's free daily token allowance is used up. About 1,000 to 2,000 tokens per attempt means 100 attempts stay well inside the 200,000-token limit. Setting the cap to `0` pauses the arena without redeploying.
- **Safety.** Code from visitors runs only in the strict sandbox profile, in a container with no secrets besides the Groq key held by the server process (the sandboxed child receives none of the parent's environment). The email tool writes to an in-memory outbox and the data is invented.
- **What is public.** Nicknames (plain letters, digits, spaces, `_`, `-`, 20 characters) and trace links are visible to everyone, and traces include the visitor's attack text. The page tells visitors not to type anything personal. If someone posts something abusive, set the cap to `0`, restart the Space (this clears the leaderboard and traces) and re-enable.

## Run it yourself instead

- **Docker, locked down like production:** `docker compose up --build`, then open http://localhost:7860.
- **Without Docker:** `uvicorn api.main:app --port 7860` after `pip install -r requirements.txt`.
- **Another host.** Anything that runs a Dockerfile works (Render, Fly.io, a small VM). Set the same variables and the `PORT` the host expects; the image reads `PORT` and defaults to 7860. Render's free tier sleeps after 15 minutes idle and needs a payment card on file for some plans, which is why it was not the first choice.
