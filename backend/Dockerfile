# portal/backend/Dockerfile
# Build context: minimal staging dir (see azure-deploy.sh Step 3)
# Expected layout in build context:
#   Dockerfile, requirements.txt, app/, bronze_framework/src/, silver_framework/src/

FROM python:3.12-slim

WORKDIR /app

# System dependencies (build-essential for chromadb native ext)
RUN apt-get update && apt-get install -y \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch FIRST.
# sentence-transformers pulls torch as a dep; if torch isn't already installed it
# downloads the CUDA variant (~2 GB). Installing CPU-only torch here prevents that.
RUN pip install --no-cache-dir \
    "torch==2.2.2" --index-url https://download.pytorch.org/whl/cpu

# Install app dependencies
COPY portal/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake framework SOURCE CODE into the image for validation imports.
# conf/ directories are NOT included here — they live on mounted volumes so the
# portal can create/edit YAML files that persist across container restarts.
COPY bronze_framework/src /workspace/bronze_framework/src
COPY silver_framework/src  /workspace/silver_framework/src

# Application code
COPY portal/backend/app /app/app

# Admin/ops scripts (e.g. add_user.py)
COPY portal/backend/scripts /app/scripts

# ── Runtime environment ──────────────────────────────────────────────────────
# All data paths point to directories that should be volume-mounted at runtime.
# These defaults match the volume names used in docker-compose.yml and
# the Azure Container Apps spec.

# Framework source roots (validation imports only)
ENV FRAMEWORK_ROOT=/workspace/bronze_framework
ENV SILVER_FRAMEWORK_ROOT=/workspace/silver_framework

# Config directories — override CONF_DIR / SILVER_CONF_DIR via env var
# so the portal reads/writes YAMLs from the mounted volume.
ENV CONF_DIR=/data/bronze_conf
ENV SILVER_CONF_DIR=/data/silver_conf

# Persistence paths
ENV CHROMADB_PERSIST_DIR=/data/chromadb
ENV TENANT_DB_PATH=/data/app/tenants.db

# HuggingFace model cache — put on volume so models survive restarts
ENV HF_HOME=/data/model_cache
ENV TRANSFORMERS_CACHE=/data/model_cache

# Disable git in container (no .git repo; configs are committed via Databricks upload)
ENV GIT_ENABLED=false

# ── Secrets — DO NOT set here; inject at runtime via env or Azure secrets ────
# DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID, ANTHROPIC_API_KEY

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
