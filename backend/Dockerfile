# syntax=docker/dockerfile:1
FROM golang:1.27-bookworm AS rmapi
ARG RMAPI_COMMIT=aa60dac8a8dbb1b4eb6a25f2caf2f3daea573373
RUN git clone https://github.com/ddvk/rmapi.git /src
WORKDIR /src
RUN git checkout "$RMAPI_COMMIT" && CGO_ENABLED=0 go build -trimpath -o /rmapi .

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libcairo2 libffi8 ca-certificates fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 app && mkdir -p /data/remarkable && chown -R app:app /data
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --from=rmapi /rmapi /usr/local/bin/rmapi
COPY --chmod=755 entrypoint.sh /usr/local/bin/noteforge-entrypoint
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
USER app
ENTRYPOINT ["noteforge-entrypoint"]
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
