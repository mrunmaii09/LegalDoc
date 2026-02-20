from dotenv import load_dotenv
load_dotenv()
"""
Legal Document Generation Platform
FastAPI Backend

Architecture:
- /doc-types          → lists available document types (config-driven)
- /session/start      → starts a new conversation session for a doc type
- /session/chat       → sends a message in an existing session
- /session/generate   → generates the final document once collection is complete
"""

import uuid
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from services.config_loader import load_config, list_available_doc_types
from services.conversation import ConversationAgent
from services.document_generator import DocumentGenerator


app = FastAPI(title="Legal Document Generation Platform", version="1.0.0")

# In-memory session store 
sessions: dict[str, ConversationAgent] = {}
doc_generator = DocumentGenerator()

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Models ───────────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    doc_type: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class GenerateRequest(BaseModel):
    session_id: str


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")


@app.get("/doc-types")
async def get_doc_types():
    """Returns all available document types. Config-driven — no code change needed for new types."""
    return {"doc_types": list_available_doc_types()}


@app.post("/session/start")
async def start_session(request: StartSessionRequest):
    """
    Creates a new conversation session for the given document type.
    The agent reads the config and begins collecting required fields.
    """
    try:
        config = load_config(request.doc_type)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document type '{request.doc_type}' not found")

    session_id = str(uuid.uuid4())
    agent = ConversationAgent(config)
    sessions[session_id] = agent

    # Get opening message from agent
    opening = agent.chat("Hello, I'd like to create a document.")

    return {
        "session_id": session_id,
        "doc_type": request.doc_type,
        "display_name": config.get("display_name"),
        "opening_message": opening["reply"],
        "total_fields": len(config.get("required_fields", [])),
    }


@app.post("/session/chat")
async def chat(request: ChatRequest):
    """
    Send a message in an existing session.
    Guardrails run before the message hits the LLM.
    Returns the agent's reply and current state.
    """
    agent = sessions.get(request.session_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Session not found")

    result = agent.chat(request.message)

    return {
        "session_id": request.session_id,
        "reply": result["reply"],
        "blocked": result["blocked"],
        "block_reason": result["block_reason"],
        "is_complete": result["is_complete"],
        "fields_collected": len(result["collected_data"]),
        "total_fields": len(agent.required_fields),
        "collected_data": result["collected_data"],
    }


@app.post("/session/generate")
async def generate_document(request: GenerateRequest):
    """
    Generates the final legal document using collected data.
    Only callable once collection is complete.
    Uses a separate constrained LLM call for drafting.
    """
    agent = sessions.get(request.session_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Session not found")

    if not agent.is_complete and len(agent.collected_data) == 0:
        raise HTTPException(
            status_code=400,
            detail="Document generation requires completing the conversation first"
        )

    doc_type = agent.doc_config.get("document_type")
    result = doc_generator.generate(doc_type, agent.collected_data)

    return {
        "session_id": request.session_id,
        "doc_type": doc_type,
        "document": result["document"],
        "missing_fields": result["missing_fields"],
        "collected_data": result["collected_data"],
    }


@app.get("/session/{session_id}/status")
async def session_status(session_id: str):
    """Check status of a session"""
    agent = sessions.get(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "is_complete": agent.is_complete,
        "collected_data": agent.collected_data,
        "fields_collected": len(agent.collected_data),
        "total_fields": len(agent.required_fields),
    }
