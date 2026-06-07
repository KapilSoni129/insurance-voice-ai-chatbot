# Insurance VoiceAI Claims Agent

An AI-powered voice agent that handles inbound insurance claim calls. Callers dial a real phone number, authenticate via phone + DOB/SSN, check claim status, ask FAQ questions, and escalate to a human when needed.

## Architecture

```
Caller (Phone)
  → Vapi (Deepgram STT → GPT-5.4 → ElevenLabs TTS)
  → Tool calls POST to FastAPI webhook
  → LangGraph multi-agent orchestration
      ├── Auth Agent (Google Sheets lookup + identity verification)
      ├── Claims Agent (claim status retrieval)
      ├── FAQ Agent (FAISS RAG semantic search)
      └── Escalation Agent (logs to Airtable, transfers call)
  → Result returned to GPT-5.4 → spoken to caller
```

## Tech Stack

- **Voice Platform:** Vapi (telephony, STT, TTS, LLM hosting)
- **Backend:** FastAPI + Python 3.11+
- **Orchestration:** LangGraph StateGraph with supervisor pattern
- **LLM:** GPT-5.4 (via Vapi) + OpenAI embeddings
- **Knowledge Base:** FAISS vector store with LangChain
- **Data (Read):** Google Sheets API via `gspread`
- **Data (Write):** Airtable REST API via `httpx`
- **Tunnel:** ngrok (for local development)

## Prerequisites

- Python 3.11+
- [ngrok](https://ngrok.com/) account and CLI installed
- [Vapi](https://vapi.ai/) account (free tier works)
- [OpenAI](https://platform.openai.com/) API key
- [Google Cloud](https://console.cloud.google.com/) service account with Sheets API enabled
- [Airtable](https://airtable.com/) account with a personal access token

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd Observe
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Google Sheets
GOOGLE_SERVICE_ACCOUNT_KEY_PATH=./service-account-key.json
GOOGLE_SHEET_ID=your-sheet-id

# Airtable
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...
AIRTABLE_TABLE_NAME=Call Logs

# Vapi
VAPI_PRIVATE_KEY=your-private-key
VAPI_PUBLIC_KEY=your-public-key
VAPI_ASSISTANT_ID=
```

### 3. Set up Google Sheets

Create a Google Spreadsheet with two worksheets:

**`customers` sheet:**

| name | phone | account_id | dob | last4ssn |
|------|-------|-----------|-----|----------|
| John Smith | 5551234567 | ACC001 | 01/15/1985 | 4567 |
| Jane Doe | 5559876543 | ACC002 | 03/22/1990 | 8901 |

**`claims` sheet:**

| claim_id | account_id | type | status | date_filed | last_updated | documents_needed | adjuster_name | notes |
|----------|-----------|------|--------|-----------|-------------|-----------------|--------------|-------|
| CLM001 | ACC001 | auto | in_review | 2024-11-01 | 2024-11-10 | Photos of damage | Mike Johnson | Rear-end collision |
| CLM002 | ACC002 | home | approved | 2024-10-15 | 2024-11-05 | | Sarah Williams | Water damage claim |

Share the spreadsheet with your service account email (found in `service-account-key.json` under `client_email`).

### 4. Set up Airtable

Create a base in Airtable. The following tables will be used:

**`Call Logs` table** (fields):
- `caller_name` (Single line text)
- `phone` (Single line text)
- `call_summary` (Long text)
- `sentiment` (Single line text)
- `timestamp` (Single line text)
- `resolution` (Single line text)
- `agent_types_used` (Single line text)
- `call_id` (Single line text)
- `duration_seconds` (Number)

**`Escalations` table** (fields):
- `caller_name` (Single line text)
- `phone` (Single line text)
- `escalation_reason` (Long text)
- `is_emergency` (Checkbox)
- `timestamp` (Single line text)
- `call_id` (Single line text)

### 5. Build the FAISS index

```bash
python backend/knowledge/build_index.py
```

You should see: `FAISS index built with 17 documents at backend/knowledge/faiss_index`

### 6. Start ngrok

In a separate terminal:

```bash
ngrok http 8000
```

Copy the `https://` forwarding URL (e.g., `https://abc123.ngrok.io`).

### 7. Create/update the Vapi assistant

```bash
python scripts/create_vapi_assistant.py --server-url https://abc123.ngrok.io
```

This creates the assistant with the system prompt, tools, and webhook configuration. If `VAPI_ASSISTANT_ID` is set in `.env`, it updates the existing assistant. Otherwise it creates a new one and prints the ID to add to `.env`.

### 8. Start the backend server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 9. Assign a phone number

In the [Vapi dashboard](https://dashboard.vapi.ai/), go to Phone Numbers → Buy a number → Assign it to your assistant.

### 10. Test it

Call the phone number. The agent will:
1. Greet you and confirm your caller ID number
2. Ask for identity verification (DOB or last 4 SSN)
3. Authenticate you against Google Sheets
4. Offer to check your claim status
5. Answer FAQ questions
6. Escalate to a human if needed

## Project Structure

```
Observe/
├── .env.example                    # Environment template
├── backend/
│   ├── main.py                     # FastAPI app entry
│   ├── config.py                   # Pydantic settings
│   ├── requirements.txt
│   ├── api/
│   │   ├── vapi_webhook.py         # POST /webhook/vapi (tool execution)
│   │   ├── calls.py                # GET /api/calls (Airtable proxy)
│   │   └── health.py               # GET /health
│   ├── agents/
│   │   ├── state.py                # AgentState TypedDict
│   │   ├── graph.py                # LangGraph StateGraph
│   │   ├── supervisor.py           # Routes tool_name → agent node
│   │   ├── auth_agent.py           # Phone lookup + identity verification
│   │   ├── claims_agent.py         # Claim status retrieval
│   │   ├── faq_agent.py            # FAISS semantic search
│   │   └── escalation_agent.py     # Escalation handling + Airtable log
│   ├── integrations/
│   │   ├── google_sheets.py        # Customer/claims data (read)
│   │   └── airtable.py             # Call logs + escalations (write)
│   └── knowledge/
│       ├── faq_data.py             # 17 FAQ documents
│       ├── build_index.py          # FAISS index builder
│       ├── retriever.py            # Similarity search function
│       └── faiss_index/            # Built vector index
├── scripts/
│   └── create_vapi_assistant.py    # Vapi assistant setup/update
└── thought_process.md              # Technical decisions document
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/vapi` | Vapi tool-call webhook (handles all agent interactions) |
| GET | `/api/calls` | Retrieve call logs from Airtable |
| GET | `/health` | Health check |

## Call Flows Supported

1. **Happy path** — authenticate → check claim status → goodbye
2. **Auth failure** — wrong verification × 2 → collect info → escalate
3. **Customer not found** — phone not in system → collect info → escalate
4. **FAQ** — "What are your office hours?" → RAG retrieval → answer
5. **Immediate escalation** — "I want to speak to a person" → collect info → escalate
6. **Emergency** — escalate with emergency flag → advise to call 911

## Troubleshooting
**Phone number not matching:**
Ensure the number in Google Sheets is 10 digits without formatting (e.g., `5551234567`). The system normalizes input but needs at least 8 matching digits.

**Webhook not receiving calls:**
- Verify ngrok is running and the URL matches what you passed to `create_vapi_assistant.py`
- Check that the Vapi assistant has a phone number assigned
- Look at ngrok's web inspector at `http://127.0.0.1:4040` for incoming requests

**Airtable 422 errors:**
Verify your table names and field names match exactly (case-sensitive). The tables must be `Call Logs` and `Escalations`.
