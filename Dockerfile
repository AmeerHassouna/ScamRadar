FROM python:3.11-slim

WORKDIR /app

# System deps: gcc/g++ for native extensions (sklearn / scipy wheels
# on some slim base images). No FAISS in requirements.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code and trained models
COPY . .

ENV PYTHONPATH=.

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
