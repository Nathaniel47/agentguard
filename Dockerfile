FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN useradd --create-home agent
COPY . .
USER agent
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
