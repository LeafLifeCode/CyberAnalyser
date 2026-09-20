# Running PAFCCI with Docker (macOS & Windows)

This application includes a multi-service Docker configuration that runs both the **Analyst Dashboard (Port 8501)** and the **Privileged Cyber Portal (Port 8502)** concurrently with shared file logging and live hot-reloading.

---

## 🚀 Quick Start (macOS / Linux / Windows)

### Prerequisites
- Install and launch **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**.

### 1. Launch Both Services with One Command
Open your terminal (Terminal app on macOS, or PowerShell on Windows) in this folder:

```bash
docker compose up --build
```

Docker will:
1. Build the Python container image (compatible with Apple Silicon M1/M2/M3 and Intel/AMD).
2. Install dependencies (`requirements.txt`).
3. Start both services simultaneously.

---

## 🌐 Accessing the Services

Once started, open your web browser:

| Application | URL | Purpose |
| :--- | :--- | :--- |
| **Delivery Model & Action Routing** | [http://localhost:8501](http://localhost:8501) | Analyst Dashboard, Heatmaps, OTP-gated Action Routing |
| **Privileged Cyber Portal** | [http://localhost:8502](http://localhost:8502) | Authority Directory, OTP Generation, Live Committed Actions |

---

## 🔄 Live Code Updates & Data Persistence

- **Live Code Edits:** Because `docker-compose.yml` mounts the current folder (`.:/app`), any change you save in `app.py`, `portal_app.py`, or other files is **instantly reflected in your browser** without rebuilding Docker.
- **Data Persistence:** Staged actions and session records are written to:
  - `cyber_portal_authority_actions.csv`
  - `cyber_portal_session_log.txt`
  - `portal_sessions.json`
  These files are persisted directly to your local machine disk.

---

## ⏹️ Stopping the Application

To stop the services:
- Press `Ctrl + C` in your terminal.
- Or run:
  ```bash
  docker compose down
  ```
