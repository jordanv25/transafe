# Transafe - build from the folder that contains run.py:   docker build -t transafe .
# Run:  docker run --rm -p 8000:8000 transafe        then open http://127.0.0.1:8000
# Optional keys (maps, X, Reddit):  docker run --rm -p 8000:8000 --env-file .env transafe
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# models/ is git-ignored, so train once at build time: the container then starts in a second instead of ~15 s
RUN python -c "from app.nlp.models import train_all; train_all()"

# the app writes its SQLite log and models into /app, so give it to a non-root user
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
# the first start backfills 50 h of simulated history (about a minute)
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/meta', timeout=4)"

# 0.0.0.0 is needed so the published port is reachable from outside the container
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000", "--no-browser"]
