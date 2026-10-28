# CityFlow 🚇🚌🚶

> **Multimodal Urban Journey Planner & Mobility Intelligence Platform for Bengaluru**

[![CI](https://github.com/kaushikbalaji/cityflow/actions/workflows/ci.yml/badge.svg)](https://github.com/kaushikbalaji/cityflow/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostGIS](https://img.shields.io/badge/PostgreSQL_16-PostGIS_3.4-336791?logo=postgresql&logoColor=white)](https://postgis.net)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-KRaft_Mode-231F20?logo=apachekafka&logoColor=white)](https://kafka.apache.org)
[![Spark](https://img.shields.io/badge/PySpark-Structured_Streaming-E25A1C?logo=apachespark&logoColor=white)](https://spark.apache.org)

---

## 🌟 Overview

**CityFlow** is an end-to-end urban transit intelligence and journey-planning engine initially focused on Bengaluru, India. It models real-world urban transit conditions across multiple transport modes:
- 🚶 **Walking** (Pedestrian footpaths, station access, transfer walks)
- 🚌 **BMTC Buses** (Bangalore Metropolitan Transport Corporation scheduled routes, Ordinary & Vajra AC)
- 🚇 **Namma Metro** (BMRCL Purple, Green, and connecting corridors)
- 🚗 **Road Vehicles** (Congestion-aware driving & auto-rickshaw routing)

### Key Features
- **Multi-Objective Optimization:** Compare journeys by fastest arrival, lowest cost (₹ INR), fewest transfers, or least walking.
- **Realistic Transfer Logic:** Station ingress/egress penalties, waiting-time estimations, and platform interchange delays.
- **Dynamic Streaming Intelligence:** Real-time road congestion and transit delay events ingested through **Apache Kafka** and aggregated using **PySpark Structured Streaming**.
- **Transparent Assumptions:** Clear labeling of scheduled timetables, walking speeds (1.2 m/s), and simulated delay factors.

---

## 🏗️ Architecture

```mermaid
flowchart LR
    UI[Next.js + MapLibre UI] <--> API[FastAPI Routing Engine]
    API <--> DB[(PostgreSQL + PostGIS)]
    API <--> Cache[Dynamic Live State]
    Sim[Event Producers] --> Kafka[Apache Kafka KRaft]
    Kafka --> Spark[PySpark Structured Streaming]
    Spark --> Cache
```

For the full architectural breakdown, data-source feasibility matrix, and routing algorithm specifications, refer to [docs/architecture/STAGE_0_RESEARCH_AND_ARCHITECTURE.md](docs/architecture/STAGE_0_RESEARCH_AND_ARCHITECTURE.md).

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- **Node.js**: v20+ (v24 recommended)
- **Python**: 3.11+ (3.13 recommended)
- **Docker & Docker Compose** (Optional for containerized mode)

### 1. Clone & Configure
```bash
git clone https://github.com/kaushikbalaji/cityflow.git
cd cityflow
cp .env.example .env
```

### 2. Run Backend (FastAPI)
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API Documentation will be accessible at: `http://localhost:8000/docs`

### 3. Run Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 🧪 Testing

```bash
# Run backend & routing engine test suite
cd backend
pytest -v

# Run frontend tests
cd frontend
npm test
```

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
