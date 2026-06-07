# Thought Process: Technical Decisions & Discussion

## 1. System Design Decisions

### Architecture Overview

```
Caller dials phone number
  → Vapi (Deepgram STT) → GPT-5.4 (hosted by Vapi) → decides to call a tool
  → POST tool call to our FastAPI webhook
  → LangGraph (supervisor → specialized agent node) → returns result
  → GPT-5.4 interprets result → Vapi (ElevenLabs TTS) → Caller hears response
```

**Core design principle:** Vapi owns the conversation (STT/TTS/LLM). Our backend only activates on business logic (tool calls). This gives optimal latency — conversational turns without tools have zero backend latency.

### Why Vapi

| Option | Verdict |
|--------|---------|
| Vapi | **Chosen** — real phone number, built-in LLM hosting, tool-calling via webhooks, fast setup |
| Retell | Similar capabilities but smaller community, no clear advantage |
| LiveKit + Pipecat | Full control but 3-5x setup time, requires managing STT/TTS separately |

Key insight: The evaluator cares about a working agent and design thinking, not manual WebRTC configuration. Vapi gets to "live demo on a real phone number" fastest, freeing time for the multi-agent orchestration and integrations.

### Why LangGraph with Supervisor Pattern

```
StateGraph:  Entry → [Supervisor: routes by tool_name] → [Auth | Claims | FAQ | Escalation] → End
```

- **Supervisor pattern** gives a single deterministic routing point — since Vapi's GPT-5.4 already decides *which* tool to call, the supervisor simply maps `tool_name → agent_node`. No second LLM needed for routing.
- **State management** is built-in via TypedDict flowing through nodes.
- **Extensible** — adding a new agent is: write node function, add to graph, add routing edge.
- **Each agent is independently testable** with mock state.

Why not sequential chain: the conversation isn't linear (caller might ask FAQ mid-claims flow). Why not peer-to-peer: harder to debug, no clear control point.

### Integration Strategy: Two Distinct Systems

- **Google Sheets (read)** — customer + claims data. Zero infrastructure, visually demoable, easy to populate test data. Uses `gspread` with service account (read-only scope).
- **Airtable (write)** — post-call logs + escalation queue. Rich field types, built-in views serve as a free "admin dashboard", REST API with bearer token.

Using two different systems (not just Sheets for both) demonstrates breadth across different API paradigms and authentication models.

### Knowledge Base: FAISS RAG

FAQ documents embedded with `text-embedding-3-small`, stored in a local FAISS index, retrieved via similarity search.

Why RAG over stuffing FAQs into the system prompt:
- Demonstrates the knowledge base integration pattern
- Shows understanding of production patterns (a real FAQ would have hundreds of entries)
- Enables semantic search (caller doesn't need exact phrasing)
- Cleaner architecture — FAQ content is separate from agent logic

Why FAISS over Pinecone/ChromaDB: zero external dependencies, runs in-process, microsecond retrieval for ~10 documents.

### Call Flow UX Decisions

- **Caller ID confirmation** — Agent sees incoming number via `{{customer.number}}` and asks "Is this the number on your account?" Eliminates the STT digit-capture problem for most callers.
- **Silence timeout via Vapi hooks** — Used `customer.speech.timeout` hook (platform-level, not LLM-dependent) with `timeoutSeconds: 15` and `triggerMaxCount: 2`. After 15s silence, Vapi says "Are you still there?" without going through GPT. After 2 unanswered prompts, call ends automatically. This required using the raw Vapi API (dot-notation `"customer.speech.timeout"`) since the SDK serializes the `on` field incorrectly.
- **endCall tool** — Added Vapi's built-in `endCall` tool type so the LLM can programmatically hang up when the conversation is naturally concluded (caller says goodbye, confirms no more questions, or after escalation).
- **End-call phrases** — "goodbye", "bye", "that's all" as backup auto-detection.
- **Max duration (10 min)** — Hard safety cap.
- **Pre-escalation data collection** — Before escalating, agent collects name, phone, and issue description. After successful escalation, agent tells caller "Our escalation team will reach out to you shortly" then ends the call — no misleading "transferring now, please stay on the line."
- **Escalation response design** — The tool result message says the escalation is logged and the team will call back, not that a live transfer is happening. This sets correct expectations since we don't have a real transfer destination.

### State Management

In-memory Python dict mapping `call_id → AgentState`. Appropriate for a single-server demo — zero latency, simple debugging.

---

## 2. Debugging Approach

### Problem: Phone Number Mismatch (discovered during live testing)

**Symptom:** Caller says their phone number, agent responds "I'm having trouble accessing the verification system."

**Investigation:**
1. Added structured logging to trace the full tool-call flow
2. Identified that GPT-5.4 sent `phone_number: "55134567"` (8 digits) but DB has `"5551234567"` (10 digits)
3. Root cause: STT captures spoken digits with spaces ("5 5 1 3 4 5 6 7"), LLM concatenates them, but caller only said 8 of 10 digits

**Fix (three layers):**
1. System prompt explicitly asks for "full 10-digit number including area code" and asks to repeat if fewer detected
2. Caller ID confirmation — use the number they're calling from, no dictation needed
3. Suffix matching fallback (8+ digits) — handles STT dropping leading digits

### Problem: OpenAI API Key Not Found in FAQ Agent

**Symptom:** `OpenAIError: Missing credentials` when `search_faq` tool fires.

**Investigation:** The `OpenAIEmbeddings()` constructor wasn't finding `OPENAI_API_KEY` in the process environment. `load_dotenv()` was called in main.py but the embeddings module loaded lazily later.

**Fix:** Pass API key explicitly from pydantic settings: `OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.openai_api_key)`

### Problem: Vapi SDK Model Validation Error

**Symptom:** `ApiError: model.model must be one of the following values` when creating assistant with `gpt-5.5`.

**Investigation:** Checked Vapi's supported model list — GPT-5.5 wasn't available yet on their platform.

**Fix:** Downgraded to `gpt-5.4` which is supported and still excellent for tool-calling.

### Problem: Call Duration Not Logging to Airtable

**Symptom:** Duration field always shows 0 in Airtable records.

**Investigation:** Original code used `call.get("duration", 0)` but Vapi's end-of-call-report doesn't put duration under that key.

**Fix:** Check multiple possible locations (`message.durationSeconds`, `call.durationSeconds`, `artifact.durationSeconds`) with a fallback that computes duration from `call.startedAt` / `call.endedAt` timestamps.

### Problem: Vapi Hooks SDK Serialization Mismatch

**Symptom:** `400 Bad Request: "each value in hooks.property do should not exist"` when passing hooks via the Vapi Python SDK.

**Investigation:**
1. The SDK types (`CallHookCustomerSpeechTimeout`) serialize the `on` field as `"customer-speech-timeout"` (dashes)
2. The Vapi API actually expects `"customer.speech.timeout"` (dots)
3. The SDK also serializes `null` fields in the `do` array items, which the API rejects

**Fix:** Bypass the SDK for hooks and use a raw `httpx.patch()` call to the Vapi REST API with the correct dot-notation format. Applied as a separate step after the main assistant create/update.

### Problem: Silent Call Hangup Without Warning

**Symptom:** Call ends after ~40s of silence with no "Are you still there?" prompt — just disconnects.

**Investigation:** Vapi has a built-in idle timeout that fires at the platform level. Initially tried `silence_timeout_seconds` param (doesn't exist in SDK), then tried `end_call_phrases` (only triggers on speech, not silence). The correct mechanism is the `hooks` array with `customer.speech.timeout` event.

**Fix:** Added hook via raw API: `timeoutSeconds: 15`, `triggerMaxCount: 2`, action: `say "Are you still there?"`. This fires at the platform level (not LLM), so it always triggers regardless of GPT state.

### Debugging Methodology

1. **Structured logging at boundaries** — log what came in (tool name + params), what happened (auth result), what went back (formatted response). 3-4 lines per tool call, not 30.
2. **Trace the data** — when something fails, follow the exact value through each transformation (raw STT → LLM interpretation → tool param → normalization → DB comparison).
3. **Test in isolation** — verify each layer independently (can the function find the phone in the sheet? does the normalization work? is the webhook receiving the right format?).
4. **SDK vs API divergence** — when SDK calls fail with cryptic errors, make the raw HTTP request directly to see what the API actually expects. SDKs can lag behind API changes.

---

## 3. Production Considerations

### What's demo-appropriate vs. what I'd change for production:

| Concern | Current (Demo) | Production |
|---------|---------------|------------|
| State storage | In-memory dict | Redis with TTL (horizontal scaling, persistence across deploys) |
| Authentication | Trust Vapi's POST | Verify webhook signatures (HMAC) |
| Rate limiting | None | Per-IP and per-call-ID rate limits on webhook |
| Phone normalization | Suffix matching | E.164 format enforcement + libphonenumber validation |
| Error handling | Log + return empty | Dead letter queue, retry with backoff, alerting |
| Secrets | .env file | Vault/SSM, rotated credentials |
| Monitoring | Console logs | Structured JSON logs → Datadog/CloudWatch, latency metrics, error rate dashboards |
| PII | Minimal logging | Phone number masking, encrypted state, audit trail |
| Deployment | Local + ngrok | Container on Railway/Render, health checks, auto-restart |

### Security in Production

- Vapi webhook signature verification (HMAC validation on every request)
- Rate limiting to prevent abuse of tool-call endpoint
- Encrypted state storage for PII (customer names, phone numbers)
- Audit logging for every data access
- Service account with minimal scopes (Sheets: read-only, Airtable: write-only to specific tables)
- Max verification attempts (2) already prevents brute force

### Reliability

- Airtable write failures shouldn't break the call — the escalation log uses try/except so tool execution still returns to Vapi
- FAISS index loaded lazily on first FAQ query, cached in memory for subsequent calls
- Graceful degradation: if Google Sheets is unavailable, return "not_found" rather than crashing the entire call

---

## 4. Scalability Considerations

### Current Bottlenecks

1. **In-memory state** — single process, lost on restart. Fix: Redis with call_id keys and 30-min TTL.
2. **Google Sheets API** — rate limited at 60 req/min. Fix: cache customer lookups in Redis (invalidate on sheet edit webhook), or migrate to PostgreSQL.
3. **FAISS in-memory** — fine for 10 documents, won't scale to 10,000. Fix: Pinecone or pgvector for large knowledge bases.
4. **Single webhook server** — one process handles all calls. Fix: Kubernetes with HPA, load balanced behind ALB.

### Scaling Path

```
Phase 1 (current): Single FastAPI process, in-memory state, local FAISS
  → Handles: ~10 concurrent calls

Phase 2: Redis state, connection pooling for Sheets API, containerized
  → Handles: ~100 concurrent calls

Phase 3: PostgreSQL for customers/claims, Pinecone for FAQ, K8s autoscaling, async workers for Airtable writes
  → Handles: ~10,000+ concurrent calls
```

### Architecture Decisions That Already Support Scale

- **Stateless tool execution** — each tool call is self-contained (state is injected, not assumed). Moving state to Redis requires no logic changes.
- **Async Airtable writes** — already using `httpx.AsyncClient`, won't block the webhook response.
- **Supervisor routing is O(1)** — dictionary lookup, not LLM inference. Adding agents doesn't increase routing latency.
- **FAISS is loaded once** — not re-built per request. Swap to any vector DB with the same `similarity_search` interface.

---

## 5. What I Would Improve With More Time

### RAG & Knowledge Base Improvements

- **Dynamic FAQ ingestion** — instead of a static Python list, pull FAQ content from a CMS or Google Doc so non-engineers can update answers without code changes or redeployment
- **Chunking strategy** — for longer policy documents, implement overlap-based chunking with metadata filtering (by policy type, topic category) for more precise retrieval
- **Hybrid search** — combine FAISS vector similarity with BM25 keyword matching for better recall on exact terms (policy numbers, specific dollar amounts)
- **Confidence thresholds** — if similarity score is below a threshold, admit "I don't have specific information on that" rather than returning a low-relevance answer
- **RAG evaluation** — build a test set of question/expected-answer pairs, measure retrieval accuracy, and tune chunk size + k parameter
- **Source attribution** — return which FAQ document the answer came from so the agent can say "According to our claims process guide..."

### New Claim Filing Flow

- **Add a `file_new_claim` tool** — allow the agent to initiate a claim on behalf of the caller during the call itself, writing to a "New Claims" sheet/table with policy number, incident date, description, and claim type
- **Policy lookup integration** — verify the caller's policy is active and covers the incident type before filing
- **Claim number generation** — assign a claim number immediately so the caller has a reference before hanging up
- **Document checklist** — after filing, tell the caller exactly which documents they'll need to submit based on claim type (auto → photos + police report, home → photos + repair estimate)
- **Confirmation SMS/email** — trigger a confirmation with claim number and next steps after the call

### Agent Quality & Reliability

- **Webhook signature verification** — validate Vapi HMAC on every request (security hardening)
- **LLM-powered sentiment analysis** — run GPT on the transcript at end-of-call instead of keyword matching, for nuanced sentiment detection
- **Call recording storage** — save Vapi recordings to S3, link from Airtable for QA review
- **Automated test suite** — pytest fixtures that replay captured Vapi webhook payloads through the full LangGraph pipeline
- **Conversation memory** — allow the agent to reference prior calls from the same customer ("I see you called last week about claim #1234")

**Guardrails:**
- **Input validation** — sanitize and validate all tool parameters before executing (reject SQL/injection patterns in phone numbers, cap string lengths)
- **PII redaction** — automatically strip SSN, DOB, and full phone numbers from logs and transcripts before writing to Airtable
- **Topic boundaries** — if the caller asks about unrelated topics (politics, medical advice, legal guidance), the agent should politely decline and redirect to claim-related help or escalate
- **Hallucination prevention** — the agent should never fabricate claim statuses, policy details, or dollar amounts. If data isn't in the tool response, say "I don't have that information" rather than guessing
- **Max tool call limit per call** — cap at 10 tool invocations per call to prevent infinite loops or runaway LLM behavior
- **Cost guardrails** — set per-call token budget on the Vapi assistant to prevent a single stuck call from consuming excessive LLM tokens

**Observability:**
- **Structured JSON logging** — replace plain text logs with structured JSON (call_id, tool_name, latency_ms, status) for easy parsing in Datadog/CloudWatch
- **Latency tracking** — measure time from webhook received → LangGraph invoke → response sent. Alert if tool execution exceeds 3s (voice calls are latency-sensitive)
- **Error rate dashboards** — track auth failures, Sheets API errors, Airtable write failures, and FAISS retrieval misses as separate metrics
- **Call flow tracing** — OpenTelemetry spans across supervisor → agent → integration, so each call has a full trace viewable in Jaeger/Tempo
- **LLM token usage** — log prompt/completion tokens per tool call to monitor cost and detect anomalies (e.g., a tool call suddenly consuming 10x tokens)
- **Alerting** — PagerDuty alerts for: webhook error rate > 5%, average latency > 5s, Airtable write failures, or zero successful calls in 30 minutes

### Infrastructure & Operations

- **Deployment pipeline** — Dockerized backend on Railway with GitHub Actions CI/CD, ngrok replaced by a stable URL
- **Multi-language support** — Vapi supports language detection; add Spanish prompts and bilingual FAQ
- **Analytics dashboard** — call volume trends, average resolution time, escalation rate, sentiment distribution over time
- **Proactive follow-up** — if a claim status changes in Sheets, trigger an outbound call to notify the customer

---

## Summary

Every decision optimizes for three things: **working demo in 6-10 hours, explainable in a technical discussion, and architecturally sound for production extension.** The stack is deliberately practical — Vapi for fast telephony, LangGraph for demonstrable multi-agent orchestration, Google Sheets + Airtable for distinct integration breadth, FAISS for zero-infrastructure RAG. The debugging section shows real problems encountered and solved during development, not theoretical issues.
