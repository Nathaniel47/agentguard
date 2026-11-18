FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=7860 \
    AGENTGUARD_STATE_DIR=/tmp/agentguard/state \
    AGENTGUARD_CACHE_DIR=/tmp/agentguard/cache \
    AGENTGUARD_RESULTS_DIR=/app/results
COPY requirements.txt .
RUN pip install -r requirements.txt
# Hugging Face Spaces runs containers as user 1000; the same user works everywhere else.
RUN useradd --create-home --uid 1000 agent
COPY --chown=agent:agent . .
USER agent
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import os,urllib.request as u; u.urlopen('http://localhost:'+os.environ['PORT']+'/health')"
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
