# Multi-stage Dockerfile: build frontend then assemble python runtime with backend
FROM node:18-alpine AS frontend-build
WORKDIR /app/Frontend

# install dependencies (uses package-lock if present)
COPY Frontend/package*.json ./
RUN npm ci --silent
COPY Frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# system deps required for some Python packages and to run uvicorn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY chatbot-whatsapp-llm/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt || true

# Copy backend source
COPY chatbot-whatsapp-llm/ ./chatbot-whatsapp-llm/

# Copy frontend build from builder
COPY --from=frontend-build /app/Frontend/build ./frontend_build

# Ensure the entrypoint script is executable
RUN chmod +x ./chatbot-whatsapp-llm/clean_start.py || true

EXPOSE 8014 3000

# Use the clean_start entrypoint which starts backend then frontend
CMD ["python", "chatbot-whatsapp-llm/clean_start.py"]
