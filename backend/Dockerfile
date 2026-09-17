FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    U2NET_HOME=/home/selfbg/.u2net

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl \
      libglib2.0-0 \
      libgl1 \
      libjpeg62-turbo \
      libpng16-16 \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash --uid 1000 selfbg

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

RUN mkdir -p "$U2NET_HOME" /data/jobs \
 && chown -R selfbg:selfbg /app "$U2NET_HOME" /data

USER selfbg

# Pre-download the default model so the first request doesn't stall.
# Override at build time with --build-arg SELFBG_MODEL=<name> to bake a
# different model into the image.
ARG SELFBG_MODEL=birefnet-general
RUN python -c "from rembg import new_session; new_session('${SELFBG_MODEL}')"

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz > /dev/null || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
