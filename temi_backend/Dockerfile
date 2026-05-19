FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md main.py ./
COPY src ./src

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
CMD ["temi-backend"]
