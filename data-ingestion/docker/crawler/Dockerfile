FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/project

COPY docker/crawler/requirements.txt /tmp/requirements.txt
COPY pyproject.toml README.md /opt/project/
COPY src /opt/project/src

RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    pip install -e .

CMD ["sh", "-c", "sleep infinity"]
