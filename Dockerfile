# ── Stage 1: dependency builder ────────────────────────────────────────────
# Alpine builder ensures pip downloads musllinux wheels (musl-compatible).
# build-base + libffi-dev needed by cffi/cryptography if no pre-built wheel.
FROM python:3.11-alpine AS builder

RUN apk add --no-cache build-base libffi-dev

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ────────────────────────────────────────────────────────
# No build tools — only the venv + app code land here.
# libstdc++ required by some compiled wheels (rapidfuzz, uvloop, tiktoken).
FROM python:3.11-alpine AS runtime

RUN apk add --no-cache curl libstdc++

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . .

RUN adduser -D -u 1000 agent && chown -R agent:agent /app
USER agent

EXPOSE 8000
CMD ["uvicorn", "webhook.server:app", "--host", "0.0.0.0", "--port", "8000"]
