# ============================================================
# PAFCCI - CyberAnalyser
# Dockerfile — multi-service Streamlit container
#
#   app.py        → port 8501  (main dashboard)
#   portal_app.py → port 8502  (authority portal)
#
# Build:
#   docker build -t cyberanalyser .
#
# Run (both apps):
#   docker run -p 8501:8501 -p 8502:8502 --env-file .env cyberanalyser
# ============================================================

# ---------- base image ----------
FROM python:3.11-slim

# Metadata
LABEL maintainer="MineSafe Stimulation"
LABEL description="PAFCCI CyberAnalyser — Synthetic Cybercrime Intelligence Platform"
LABEL version="1.0"

# ---------- environment ----------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---------- system dependencies ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---------- working directory ----------
WORKDIR /app

# ---------- install Python dependencies first (layer cache) ----------
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ---------- copy project files ----------
COPY . .

# ---------- expose Streamlit ports ----------
EXPOSE 8501 8502

# ---------- startup script ----------
# Launches both Streamlit apps; portal_app runs in the background.
CMD ["sh", "-c", "\
    streamlit run portal_app.py \
        --server.port 8502 \
        --server.address 0.0.0.0 \
        --server.headless true \
        --browser.gatherUsageStats false & \
    streamlit run app.py \
        --server.port 8501 \
        --server.address 0.0.0.0 \
        --server.headless true \
        --browser.gatherUsageStats false \
"]
