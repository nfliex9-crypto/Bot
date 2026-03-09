FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY configs /app/configs

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src
CMD ["python", "-m", "quant_lab.pipeline.run_research"]
