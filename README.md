# cmpe-295a-masters-project
CMPE 295A Master's Project – San José State University
# Agentic Retail System Project    

---

## 📌 Project Overview  

**Agentic System for Intelligent Retail Operations** is a research and development project focused on designing an autonomous, multi-agent decision-making system for retail environments. The system integrates demand forecasting, inventory optimization, and real-time operational responsiveness to improve retail efficiency and reduce stockouts and overstock situations.

This repository contains the codebase, documentation, and meeting logs related to this project for CMPE 295A — Master’s Project.

---

## 📁 Repository Structure  

A brief view of how this repository is organized:
/ (root)
│
├── meetings/ # Weekly team and advisor meeting logs
├── backend/ # FastAPI backend services
├── frontend/ # React dashboard UI
├── data/ # Datasets and preprocessing scripts
├── docs/ # Project documentation (if any)
├── scripts/ # Utility & evaluation scripts
├── .gitignore
├── README.md
└── requirements.txt # Project dependencies


---


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

## 🚀 Core Features (In Progress)

- 📈 Demand Forecasting Module (Prophet baseline, LSTM planned)
- 📦 Inventory Agent (rule-based reorder logic)
- 📊 Dashboard for stock alerts and forecast visualization
- ☁️ AWS-based backend deployment (EC2, RDS, S3)
- 📉 Performance metrics tracking (MAE, RMSE, stockout rate)

---

## 🧪 Testing & Evaluation (Planned)

- Forecast accuracy validation using MAE and RMSE.
- Inventory performance evaluation using stockout and overstock rates.
- End-to-end pipeline validation:
  
  Sales Data → Forecast → Inventory Decision → Dashboard

- System performance measurement (API latency and response time).

---

## 🛠 Technology Stack

**Backend**
- Python 3.11
- FastAPI
- PostgreSQL
- SQLAlchemy

**Machine Learning**
- Prophet
- PyTorch
- Pandas / NumPy

**Frontend**
- React
- Recharts

**Infrastructure**
- Docker
- AWS EC2
- AWS RDS
- AWS S3
- CloudWatch

---
---

## 👥 Team Members  

- **Sriram Lakumarapu**  
- **Vignesh Jetty Ravi**  
- **Abdul Muqtadir Mohammed**  

### 🎓 Project Advisor  

- **Prof. Chandrasekar Vuppalapati**

