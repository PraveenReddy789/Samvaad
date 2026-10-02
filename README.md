# 🎙️ Samvaad — Pan-Indian Multilingual Voice RAG Debt Collection & Recovery Assistant

A production-grade, 100% free & open-source **Voice RAG Collection & Customer Support Assistant** purpose-built for loan servicing, debt recovery, and financial hardship inquiries across 5 Pan-Indian languages (English, Telugu, Hindi, Tamil, Malayalam). Powered by **FastAPI**, **LangChain LCEL**, **Qdrant Vector Database**, **BM25 Keyword Search**, **Cross-Encoder Reranking**, **Reserve Bank & Fair Debt Recovery Policy Guardrails**, and **Neural Text-to-Speech (Edge-TTS)**.

---

## 🏛️ System Architecture

```
                         ┌───────────────┐
                         │   React UI    │  <-- Waveform visualizer, live transcript, audio player
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │    FastAPI    │  <-- REST & WebSocket gateway, audio streaming
                         └───────┬───────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   RAG Agent Orchestrator│
                    └───────────┬────────────┘
                                │
                    ┌───────────┼─────────────┐
                    │           │             │
                    ▼           ▼             ▼
               Query Router  Memory       Tool Router
                    │           │             │
                    ▼           ▼             ▼
              ┌─────────┐  ┌─────────┐   PostgreSQL / SQLite
              │ Hybrid  │  │ Previous│   Payment Verification API
              │ Search  │  │ Calls   │   Customer Loan API
              └────┬────┘  └─────────┘
                   │
             Dense + BM25 (RRF Fusion)
                   │
                   ▼
               Reranker (bge-reranker)
                   │
                   ▼
              Top Context
                   │
                   ▼
             Policy Engine (Fair Debt Recovery Guardrails)
                   │
                   ▼
               Local LLM (Ollama / Open-Mistral-7b)
                   │
         ┌─────────┼─────────┐
         ▼         ▼         ▼
      Answer    Tool Call  Escalate
         │         │         │
         └─────────┼─────────┘
                   ▼
                  TTS (Neural en-IN-Neerja)
                   │
                   ▼
                Customer
```

---

## 🔑 The Golden Architecture Rule

> [!IMPORTANT]
> **Strict Separation of Authoritative Facts vs. Semantic Knowledge:**
> - **DO NOT use RAG** to answer customer-specific facts such as current EMI, outstanding balance, due dates, or payment status. These are retrieved deterministically through **Database Tools** (`backend/db/tools.py`).
> - **Use Hybrid RAG** for policies (`data/policies/*.pdf`), Standard Operating Procedures (`data/sop/*.md`), and product specifications (`data/products/*.md`).
> - **Use Memory** for short-term dialogue context and past call histories (`data/calls/*.json`).
> - **The Policy Engine** enforces strict compliance (e.g. never confirming a payment without tool verification, never guaranteeing debt write-offs or waivers).

---

## 📦 100% Free & Open-Source Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | `FastAPI` | Asynchronous REST endpoints, audio streaming, metrics |
| **LLM Inference** | `Open-Mistral-7b` / `Ollama` | Grounded reasoning, tool parameter generation |
| **Embeddings** | `BGE-M3` / `Mistral-Embed` | 1024-dimensional dense semantic vectors |
| **Vector DB** | `Qdrant` | Persistent vector store with payload metadata filtering |
| **Keyword Search** | `BM25` (`rank-bm25`) | Lexical search for loan IDs, policy clauses, and fees |
| **Reranker** | `CrossEncoderReranker` | Re-scoring hybrid candidates via lexical & semantic density |
| **Database** | `SQLite` / `PostgreSQL` | Authoritative customer loans and verified payment transactions |
| **Voice / TTS** | `Edge-TTS` | Low-latency neural Indian English speech (`en-IN-NeerjaNeural`) |
| **Frontend** | `React` / Modern Glassmorphism Web UI | Audio waveform visualizer, transcript, telemetry & citation inspector |
| **Monitoring** | `Prometheus` + `Grafana` | Real-time retrieval latency, turn latency, tool counters |
| **Containers** | `Docker` & `Docker Compose` | Full multi-service deployment |

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Virtual Environment
Ensure dependencies are installed:
```bash
./.venv/bin/pip install -r requirements.txt
```

### 2. Seed Database & Ingest Knowledge Base
```bash
# 1. Seed customer accounts and verified payments into the relational DB:
./.venv/bin/python main.py --seed

# 2. Ingest PDFs, SOPs, products, and past call logs into Qdrant & BM25:
./.venv/bin/python main.py --index
```

### 3. Launch the Application & Web Dashboard
```bash
./.venv/bin/python main.py --port 8000
```
Open your browser to:
- **Interactive Voice Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Swagger API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)

### 4. Interactive Terminal CLI Mode
To chat with the agent directly from your terminal:
```bash
./.venv/bin/python main.py --cli --customer CUST001
```

---

## 🛠️ API Reference

- `GET /api/customers` — List all customers with account balances & overdue flags.
- `GET /api/customers/{id}` — Get customer loan details, payment records, and call history.
- `POST /api/chat` — Process a turn:
  ```json
  {
    "customer_id": "CUST001",
    "message": "I already paid 5000 on the 19th with reference TXN-70002",
    "session_id": "session_001"
  }
  ```
  Returns:
  ```json
  {
    "customer_id": "CUST001",
    "intent": "ALREADY_PAID",
    "outcome": "ALREADY_PAID",
    "is_escalated": false,
    "response": "Sir, I've verified your payment record...",
    "audio": { "audio_url": "/api/audio/speech_xxx.mp3", "audio_base64": "..." },
    "tool_executions": [ ... ],
    "citations": [ ... ],
    "turn_latency_ms": 1240.5
  }
  ```
- `GET /api/audio/{filename}` — Audio stream endpoint for generated speech.
- `GET /metrics` — Prometheus metrics endpoint.

---

## 🐳 Docker Compose Multi-Service Deployment

To launch the full production stack (FastAPI backend, Qdrant vector database, PostgreSQL, Redis, Prometheus, and Grafana):
```bash
docker compose up -d --build
```
- **Web App**: [http://localhost:8000](http://localhost:8000)
- **Qdrant Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)
- **Grafana**: [http://localhost:3001](http://localhost:3001) (User: `admin`, Pass: `admin`)
