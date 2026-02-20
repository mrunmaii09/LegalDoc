# LegalDraft AI — Legal Document Generation Platform

A multi-agent AI system that generates personalised legal documents through natural conversation.

## Architecture Overview

```
User Message
     │
     ▼
┌─────────────────────────────┐
│      Guardrails Layer        │  ← Blocks advice requests & prompt injection
│  (runs BEFORE hitting LLM)   │    before they ever reach the LLM
└────────────┬────────────────┘
             │ (if safe)
             ▼
┌─────────────────────────────┐
│    Conversation Agent        │  ← Goal-directed agent (Groq / Llama 3.1)
│  Goal: collect all fields    │    Reads required fields from config YAML
│  from document config        │    Handles vague inputs, contradictions naturally
└────────────┬────────────────┘
             │ (once all fields collected)
             ▼
┌─────────────────────────────┐
│    Field Extraction          │  ← Separate LLM call (temp=0)
│  Structured data from chat   │    Pulls confirmed values from conversation
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│    Document Drafter Agent    │  ← Separate constrained LLM call (temp=0)
│  Fills template with data    │    Only uses provided facts, never invents
└────────────┬────────────────┘
             │
             ▼
        Final Document
```

## Key Design Decisions

### 1. Config-Driven Architecture
New document types = new YAML file in `/config`. Zero code changes.
```
config/
  will.yaml   → Last Will & Testament
  nda.yaml    → Non-Disclosure Agreement
  lease.yaml  → Add tomorrow, no refactoring needed ✓
```

### 2. Two-Agent Separation
- **Conversation Agent**: Natural dialogue, warm tone, asks follow-ups
- **Drafter Agent**: Constrained, formal, temperature=0, facts-only
Keeping these separate prevents the conversational agent from bleeding creative freedom into legal drafting.

### 3. Guardrails Before LLM
Injection and advice detection runs *before* user message reaches the LLM.
The LLM never sees malicious prompts.

### 4. Temperature Strategy
| Component | Temperature | Reason |
|---|---|---|
| Conversation Agent | 0.2 | Natural but consistent |
| Field Extractor | 0.0 | Deterministic |
| Document Drafter | 0.0 | Reproducible — same input = same doc |

### 5. What the LLM Handles vs Rules
| Concern | Approach |
|---|---|
| Vague inputs | LLM asks for clarification naturally |
| Contradictions | LLM detects from conversation history |
| Advice seeking | Rule-based (before LLM) |
| Prompt injection | Rule-based (before LLM) |
| Document drafting | Constrained LLM with strict system prompt |

## Setup

```bash
# Clone and install
pip install -r requirements.txt

# Set your Groq API key
export GROQ_API_KEY=your_key_here

# Run
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/doc-types` | List all available document types |
| POST | `/session/start` | Start conversation for a doc type |
| POST | `/session/chat` | Send message in session |
| POST | `/session/generate` | Generate final document |
| GET | `/session/{id}/status` | Check session state |

## Adding a New Document Type

1. Create `config/your_doc.yaml` (copy will.yaml as template)
2. Create `templates/your_doc.txt` with `{{field_name}}` placeholders
3. That's it. No code changes. Available immediately on next restart.

## LLM Choice: Why Groq?
- **Speed**: ~10x faster than OpenAI for same model — great for live demos
- **Free tier**: Generous for prototyping
- **Model**: Llama 3.1 8B (conversation) + 70B (drafting) — right size for each task
- **Deterministic**: Temperature=0 supported for reproducible outputs
