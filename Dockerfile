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
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl ca-certificates nodejs npm && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
# requirements.txt lives at the repo root (build context), not under a nested `chatbot-whatsapp-llm/` dir
COPY requirements.txt ./requirements.txt
# Upgrade pip and install build tools to reduce wheel/build issues
RUN python -m pip install --upgrade pip setuptools wheel
# Install Python requirements (do not ignore failures so build fails if deps are missing)
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
# Copy the repository contents into the image so paths like
# `chatbot-whatsapp-llm/clean_start.py` exist as expected.
COPY . ./

# Install production frontend dependencies
WORKDIR /app/Frontend
RUN npm install --production
WORKDIR /app

# Copy frontend build from builder
# Next.js outputs the compiled site to `.next` (not `build`). Copy `.next` into the image
COPY --from=frontend-build /app/Frontend/.next /app/Frontend/.next

# Ensure the entrypoint script is executable (clean_start.py lives at repo root in the image)
RUN chmod +x ./clean_start.py || true

EXPOSE 8014 3000

# Use the clean_start entrypoint which starts backend then frontend
CMD ["python", "clean_start.py"]
