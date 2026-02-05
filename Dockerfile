# Stage 1: Build Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy dependency definitions first to leverage Docker cache
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Runtime
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y git openssh-client && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Configure SSH/Git (Keep existing configuration)
RUN mkdir -p /root/.ssh && ssh-keyscan github.com >> /root/.ssh/known_hosts && chmod 600 /root/.ssh/known_hosts
RUN git config --global --add safe.directory /codebase \
    && git config --global user.email "agent@gemini.local" \
    && git config --global user.name "Gemini Agent"

# Copy Backend Code
COPY app/ ./app/

# Copy Built Frontend Assets from Stage 1
# Vite output matches: /app/frontend -> ../app/static/dist -> /app/app/static/dist
COPY --from=frontend-builder /app/app/static/dist ./app/static/dist

EXPOSE 5000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
