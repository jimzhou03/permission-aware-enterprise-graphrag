FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /workspace

COPY services/api/requirements.txt /workspace/services/api/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /workspace/services/api/requirements.txt

COPY services/api /workspace/services/api
COPY sample_data /workspace/sample_data
COPY .env.example /workspace/.env.example

WORKDIR /workspace/services/api

EXPOSE 8000

CMD ["python", "main.py"]

