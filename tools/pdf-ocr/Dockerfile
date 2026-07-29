FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PDF_OCR_MODEL_HOME=/models \
    DOCLING_ARTIFACTS_PATH=/models

RUN python -m pip install --no-cache-dir uv==0.11.26 \
    && groupadd --system pdfocr \
    && useradd --system --gid pdfocr --create-home --home-dir /home/pdfocr pdfocr \
    && mkdir -p /models \
    && chmod 0555 /models

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY schemas ./schemas
COPY models.lock.json ./

RUN chown -R pdfocr:pdfocr /app
ENV UV_OFFLINE=1
USER pdfocr

ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "python", "-m", "pdf_ocr.cli", "--model-lock", "/app/models.lock.json", "--model-home", "/models", "--uv-lock", "/app/uv.lock"]
