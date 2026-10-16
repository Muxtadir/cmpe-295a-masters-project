# cmpe-295a-masters-project

CMPE 295A Master's Project – San José State University

# Agentic Retail System Project

---

## 📌 Project Overview

**Agentic System for Intelligent Retail Operations** is a research and development project focused on designing an autonomous, multi-agent decision-making system for retail environments. The system integrates demand forecasting, inventory optimization, market basket analysis, and real-time operational responsiveness to improve retail efficiency and reduce stockouts and overstock situations.

This repository contains the codebase, documentation, and meeting logs related to this project for CMPE 295A — Master’s Project.

**Current active pipeline:** [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) (UCI) — invoice-level baskets for association mining and StockCode-level daily demand for forecasting. Raw dataset files are gitignored; use the loaders under `backend/scripts/`.

---

## 📁 Repository Structure

```
/ (root)
│
├── meetings/              # Weekly team and advisor meeting logs
├── backend/               # FastAPI backend services
│   ├── app/               # Agents, models, routes, services
│   ├── scripts/           # Dataset loaders & utilities
│   ├── tests/             # Backend tests
│   ├── data/              # Local data helpers (raw files gitignored)
│   ├── requirements.txt   # Python dependencies
│   └── .env.example       # Environment template (do not commit .env)
├── frontend/              # React (Vite) Retail Command Center UI
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## 🗂 Meeting Logs

All official project meeting notes are maintained in the `/meetings/` folder.

These logs:

- Track weekly student team meetings (Mondays).
- Track advisor meetings (Mondays, when scheduled).
- Include agendas, decisions, blockers, and action items with ownership.

Direct link to meeting folder:

https://github.com/Crimsonbeetle/cmpe-295a-masters-project/tree/main/meetings

---

## 🚀 Core Features

- 📈 **Demand forecasting** — Prophet baseline with association-aware regressors (LSTM planned)
- 🛒 **Market basket analysis** — Apriori association rules from Online Retail II invoices
- 📦 **Inventory agent** — rule-based reorder / alignment logic
- 🖥 **Retail Command Center** — manager-oriented dashboard (Manager / Research view toggle)
- 📉 **Evaluation** — forecast metrics (MAE, RMSE) and association-aware A/B evaluation APIs
- 🔐 **Auth** — user registration / login with role-based access
- ☁️ **AWS deployment** (planned / in progress) — EC2, RDS, S3

---

## 🧪 Testing & Evaluation

- Forecast accuracy validation using MAE and RMSE
- Association-aware vs baseline forecast comparison
- Inventory performance evaluation using stockout and overstock rates
- End-to-end pipeline validation:

  Sales / Basket Data → Forecast (+ associations) → Inventory Decision → Dashboard

- System performance measurement (API latency and response time)

---

## 🛠 Technology Stack

**Backend**

- Python 3.11
- FastAPI
- PostgreSQL (production) / SQLite (local `dev.db`, gitignored)
- SQLAlchemy

**Machine Learning**

- Prophet
- PyTorch
- Pandas / NumPy
- Apriori (market basket / association rules)

**Frontend**

- React (Vite)
- Recharts

**Infrastructure**

- Docker
- AWS EC2
- AWS RDS
- AWS S3
- CloudWatch

---

## ▶️ Quick Start (local)

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit as needed
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Load Online Retail II (place `online_retail_II.xlsx` under `backend/data/` — file is gitignored):

```bash
cd backend
python scripts/load_online_retail_ii.py
```

---

## 👥 Team Members

- **Sriram Lakumarapu**
- **Vignesh Jetty Ravi**
- **Abdul Muqtadir Mohammed**

### 🎓 Project Advisor

- **Prof. Chandrasekar Vuppalapati**
