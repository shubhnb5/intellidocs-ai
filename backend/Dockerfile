# Single-stage: the runtime image needs the same Python/pip toolchain used
# to install dependencies, so a build stage wouldn't actually drop anything.
# (Contrast with frontend/Dockerfile, where Node/npm genuinely aren't needed
# once the static bundle exists -- that one *does* multi-stage.)
FROM python:3.12-slim

WORKDIR /app

# curl: used by this image's own HEALTHCHECK below, nothing else.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
