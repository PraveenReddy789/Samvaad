import os
import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.config import TTS_AUDIO_DIR, BASE_DIR
from backend.db.database import SessionLocal
from backend.db.models import Customer, Payment, Escalation, CallDisposition
from backend.agent.orchestrator import get_orchestrator
from backend.rag.indexer import load_and_index_all
from backend.services.metrics import get_prometheus_metrics
from backend.services.tts_service import generate_speech_audio, get_voice_for_customer

app = FastAPI(
    title="RAG Voice Collection Agent API",
    description="Enterprise Open-Source RAG Voice Collection & Loan Recovery Assistant",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class ChatRequest(BaseModel):
    customer_id: str
    message: str
    session_id: Optional[str] = None
    voice: Optional[str] = None
    language: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    customer_name: Optional[str] = None


@app.get("/api/rules")
def get_rules_and_regulations():
    """Returns RBI Fair Debt Recovery regulations, agent persona rules, and recovery SOPs."""
    return {
        "persona_rules": [
            "Authoritative Facts: All loan balances, EMIs, and due dates must be fetched directly from database tools, never invented.",
            "Payment Verification: Must verify UTR / Ref IDs in core database before confirming payment receipt.",
            "Voice-Ready Brevity: Responses must be concise (1-2 sentences) for real-time natural telephony TTS.",
            "Empathetic & Non-Threatening: Must maintain professional empathy without promising debt write-offs without approval."
        ],
        "rbi_regulations": [
            "Permissible Contact Hours: Customers may only be contacted between 08:00 AM and 07:00 PM.",
            "Prohibition of Harassment: Strict ban on intimidation, abusive language, threatening police or legal force, or public humiliation.",
            "Privacy & Confidentiality: Loan details must not be disclosed to unauthorized third parties or relatives.",
            "Grievance Redressal: Must provide clear escalation pathways to human supervisors upon customer request."
        ],
        "recovery_sops": [
            {"sop": "Already Paid SOP", "rule": "Verify transaction reference in core payments DB. If found, mark EMI cleared. If missing, ask for UTR."},
            {"sop": "Financial Hardship SOP", "rule": "Express empathy, register hardship review in database, schedule follow-up without unauthorized waivers."},
            {"sop": "Payment Dispute SOP", "rule": "Open dispute ticket in accounts system, freeze immediate penalty accumulation, refer to dispute team."},
            {"sop": "Refusal to Pay SOP", "rule": "Politely advise customer regarding credit bureau score impacts and late fee consequences as per policy."}
        ]
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "RAG Voice Collection Assistant"}


@app.get("/metrics")
def metrics():
    data, content_type = get_prometheus_metrics()
    return Response(content=data, media_type=content_type)


@app.get("/api/customers")
def list_customers():
    """Returns all customers with loan accounts and payment status."""
    db = SessionLocal()
    try:
        customers = db.query(Customer).all()
        return [
            {
                "customer_id": c.customer_id,
                "name": c.name,
                "mobile_number": c.mobile_number,
                "loan_id": c.loan_id,
                "product_id": c.product_id,
                "emi_amount": c.emi_amount,
                "emi_due_date": c.emi_due_date,
                "status": c.status,
                "promise_to_pay_date": c.promise_to_pay_date,
                "hardship_flag": c.hardship_flag,
            }
            for c in customers
        ]
    finally:
        db.close()


@app.get("/api/customers/{customer_id}")
def get_customer_profile(customer_id: str):
    """Returns comprehensive customer detail: account, payments, call history, and escalations."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.customer_id == customer_id.strip()).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        payments = db.query(Payment).filter(Payment.customer_id == customer_id.strip()).all()
        escalations = db.query(Escalation).filter(Escalation.customer_id == customer_id.strip()).all()
        calls = (
            db.query(CallDisposition)
            .filter(CallDisposition.customer_id == customer_id.strip())
            .order_by(CallDisposition.timestamp.desc())
            .all()
        )

        return {
            "customer": {
                "customer_id": customer.customer_id,
                "name": customer.name,
                "mobile_number": customer.mobile_number,
                "loan_id": customer.loan_id,
                "product_id": customer.product_id,
                "emi_amount": customer.emi_amount,
                "emi_due_date": customer.emi_due_date,
                "status": customer.status,
                "promise_to_pay_date": customer.promise_to_pay_date,
                "hardship_flag": customer.hardship_flag,
                "hardship_reason": customer.hardship_reason,
                "notes": customer.notes,
            },
            "payments": [
                {
                    "payment_id": p.payment_id,
                    "payment_date": p.payment_date,
                    "amount": p.amount,
                    "status": p.status,
                    "transaction_reference": p.transaction_reference,
                }
                for p in payments
            ],
            "escalations": [
                {
                    "escalation_id": e.escalation_id,
                    "category": e.category,
                    "reason": e.reason,
                    "status": e.status,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in escalations
            ],
            "call_history": [
                {
                    "call_id": c.call_id,
                    "timestamp": (
                        json.loads(c.summary).get("start_time", c.timestamp)
                        if c.summary and c.summary.strip().startswith("{") and "start_time" in json.loads(c.summary)
                        else c.timestamp
                    ),
                    "direction": c.direction,
                    "intent": c.intent,
                    "outcome": c.outcome,
                    "sentiment": c.sentiment,
                    "summary": (
                        json.loads(c.summary).get("summary", f"Call completed with outcome {c.outcome}.")
                        if c.summary and c.summary.strip().startswith("{") and "summary" in json.loads(c.summary)
                        else (
                            f"Customer inquiry: \"{json.loads(c.summary).get('customer_message', '')[:65]}...\""
                            if c.summary and c.summary.strip().startswith("{") and "customer_message" in json.loads(c.summary)
                            else (c.summary or f"Call completed with outcome {c.outcome}.")
                        )
                    ),
                    "total_turns": (
                        len(json.loads(c.summary).get("turns", [])) // 2 or len(json.loads(c.summary).get("turns", []))
                        if c.summary and c.summary.strip().startswith("{") and "turns" in json.loads(c.summary)
                        else 1
                    ),
                    "turns": (
                        json.loads(c.summary).get("turns")
                        if c.summary and c.summary.strip().startswith("{") and "turns" in json.loads(c.summary)
                        else (
                            [
                                {"speaker": "Customer", "message": json.loads(c.summary).get("customer_message", ""), "timestamp": json.loads(c.summary).get("timestamp", c.timestamp)},
                                {"speaker": "Samvaad Voice Agent", "message": json.loads(c.summary).get("agent_response", ""), "timestamp": json.loads(c.summary).get("timestamp", c.timestamp)}
                            ]
                            if c.summary and c.summary.strip().startswith("{") and ("customer_message" in json.loads(c.summary) or "agent_response" in json.loads(c.summary))
                            else [{"speaker": "Call Transcript", "message": c.summary or "Official banking call on record.", "timestamp": c.timestamp}]
                        )
                    )
                }
                for c in calls
            ]
        }
    finally:
        db.close()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Processes a conversational customer turn."""
    orchestrator = get_orchestrator()
    result = await orchestrator.process_turn(
        customer_id=request.customer_id,
        message=request.message,
        session_id=request.session_id,
        voice=request.voice,
        language=request.language
    )
    return result


@app.post("/api/tts")
async def generate_tts(request: TTSRequest):
    """Generates TTS audio on-demand for greetings or custom statements."""
    voice = request.voice
    if not voice and request.customer_name:
        voice = get_voice_for_customer(request.customer_name)
    audio_res = await generate_speech_audio(request.text, voice=voice)
    return audio_res


@app.get("/api/audio/{filename}")
def get_audio(filename: str):
    """Streams generated TTS audio mp3 file."""
    audio_path = Path(TTS_AUDIO_DIR) / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(audio_path), media_type="audio/mpeg")


@app.post("/api/index")
def reindex_knowledge():
    """Triggers knowledge base re-indexing across PDFs, SOPs, and products."""
    count = load_and_index_all()
@app.get("/api/qdrant/status")
def get_qdrant_status():
    """Returns the Qdrant vector database mode, collections, and points."""
    from backend.rag.vectorstore import get_vector_store
    from backend.config import QDRANT_HOST, QDRANT_PORT, QDRANT_STORAGE_PATH, QDRANT_COLLECTION
    try:
        vs = get_vector_store()
        colls = [c.name for c in vs.client.get_collections().collections]
        points_count = vs.client.count(vs.collection_name).count
        return {
            "status": "online",
            "mode": "standalone_server" if QDRANT_HOST else "embedded_local",
            "storage_path": QDRANT_STORAGE_PATH if not QDRANT_HOST else f"http://{QDRANT_HOST}:{QDRANT_PORT}",
            "active_collection": QDRANT_COLLECTION,
            "total_points_indexed": points_count,
            "collections": colls,
            "web_dashboard_available": bool(QDRANT_HOST),
            "info": "Qdrant is running in Embedded Local Mode directly inside the Python environment. Standalone web dashboard requires Qdrant Docker container on port 6333."
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Serve Frontend static assets
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
