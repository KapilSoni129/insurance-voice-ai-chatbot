import json
import logging
import traceback
from fastapi import APIRouter, Request
from backend.agents.graph import agent_graph
from backend.integrations.airtable import write_call_log, write_escalation_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory call state (use Redis in production)
call_states: dict[str, dict] = {}


@router.post("/vapi")
async def handle_vapi_webhook(request: Request):
    try:
        payload = await request.json()
        message = payload.get("message", payload)
        event_type = message.get("type")

        if event_type == "tool-calls":
            return await handle_tool_calls(message)
        elif event_type == "end-of-call-report":
            await handle_end_of_call(message)
            return {"status": "ok"}
        elif event_type == "status-update":
            status = message.get("status")
            logger.info(f"Call status: {status}")
            return {"status": "ok"}

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"WEBHOOK ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


async def handle_tool_calls(message: dict):
    """Vapi sends tool calls here. We run them through LangGraph and return results."""
    try:
        call = message.get("call", {})
        call_id = call.get("id", "unknown")
        tool_calls = message.get("toolCallList", [])

        results = []
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_params = tc["function"].get("arguments", {})
            if isinstance(tool_params, str):
                tool_params = json.loads(tool_params)
            tool_call_id = tc["id"]

            logger.info(f"[TOOL] {tool_name} | params={tool_params}")

            # Get or initialize state for this call
            state = call_states.get(call_id, {
                "call_id": call_id,
                "caller_phone": None,
                "auth_status": "pending",
                "auth_attempts": 0,
                "customer_name": None,
                "account_id": None,
                "claim_status": None,
                "claim_details": None,
                "current_agent": "supervisor",
                "tool_name": None,
                "tool_params": None,
                "faq_answer": None,
                "escalation_reason": None,
                "resolution": None,
                "agents_used": [],
            })

            state["tool_name"] = tool_name
            state["tool_params"] = tool_params

            # Track agents used
            agent_map = {
                "authenticate_customer": "auth",
                "get_claim_status": "claims",
                "search_faq": "faq",
                "escalate_call": "escalation",
            }
            agent_type = agent_map.get(tool_name)
            if agent_type and agent_type not in state.get("agents_used", []):
                state["agents_used"].append(agent_type)

            result_state = agent_graph.invoke(state)
            call_states[call_id] = result_state

            # Log escalation to Airtable
            if tool_name == "escalate_call":
                try:
                    await write_escalation_log(
                        caller_name=result_state.get("customer_name") or "Unknown",
                        phone=result_state.get("caller_phone") or call.get("customer", {}).get("number", ""),
                        reason=result_state.get("escalation_reason", ""),
                        is_emergency=tool_params.get("is_emergency", False),
                        call_id=call_id,
                    )
                    logger.info(f"[AIRTABLE] Escalation logged")
                except Exception as esc_err:
                    logger.error(f"[AIRTABLE] Escalation log failed: {esc_err}")

            result_message = format_tool_result(tool_name, result_state)
            logger.info(f"[RESULT] {tool_name} → {result_message[:200]}")

            results.append({
                "toolCallId": tool_call_id,
                "result": result_message,
            })

        return {"results": results}

    except Exception as e:
        logger.error(f"TOOL CALL ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        return {"results": []}


async def handle_end_of_call(message: dict):
    """Write post-call log to Airtable."""
    try:
        call = message.get("call", {})
        call_id = call.get("id", "unknown")
        artifact = message.get("artifact", {})

        state = call_states.pop(call_id, {})

        transcript = artifact.get("transcript", "")
        summary = artifact.get("summary", "")
        if not summary:
            summary = transcript[:500] if transcript else "No summary available"

        sentiment = determine_sentiment(transcript)
        resolution = state.get("resolution", "resolved" if state.get("auth_status") == "authenticated" else "unresolved")

        caller_name = state.get("customer_name") or "Unknown"
        phone = state.get("caller_phone") or call.get("customer", {}).get("number", "")
        agents_used = state.get("agents_used", [])

        # Vapi sends duration in multiple possible locations
        duration = (
            message.get("durationSeconds")
            or message.get("duration_seconds")
            or call.get("durationSeconds")
            or artifact.get("durationSeconds")
            or _compute_duration(call)
            or 0
        )

        logger.info(f"[END CALL] {call_id} | {caller_name} | sentiment={sentiment} | resolution={resolution} | duration={duration}s")

        await write_call_log(
            caller_name=caller_name,
            phone=phone,
            call_summary=summary,
            sentiment=sentiment,
            resolution=resolution,
            agent_types_used=agents_used,
            call_id=call_id,
            duration_seconds=int(duration),
        )

        logger.info(f"[AIRTABLE] Call log written for {call_id}")

    except Exception as e:
        logger.error(f"END OF CALL ERROR: {str(e)}")
        logger.error(traceback.format_exc())


def _compute_duration(call: dict) -> int | None:
    """Compute duration from startedAt/endedAt ISO timestamps."""
    from datetime import datetime
    started = call.get("startedAt")
    ended = call.get("endedAt")
    if started and ended:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(ended.replace("Z", "+00:00"))
            return int((end_dt - start_dt).total_seconds())
        except (ValueError, TypeError):
            pass
    return None


def format_tool_result(tool_name: str, state: dict) -> str:
    if tool_name == "authenticate_customer":
        status = state.get("auth_status")
        if status == "authenticated":
            return json.dumps({
                "status": "authenticated",
                "customer_name": state["customer_name"],
                "account_id": state["account_id"],
                "message": f"Customer verified: {state['customer_name']}",
            })
        elif status == "not_found":
            return json.dumps({
                "status": "not_found",
                "message": "No account found with that phone number.",
            })
        elif status == "failed":
            return json.dumps({
                "status": "failed",
                "message": "Maximum verification attempts reached. Please transfer to a representative.",
            })
        else:
            remaining = 2 - state.get("auth_attempts", 0)
            return json.dumps({
                "status": "verification_failed",
                "attempts_remaining": remaining,
                "message": f"Verification failed. {remaining} attempt(s) remaining.",
            })

    elif tool_name == "get_claim_status":
        details = state.get("claim_details", {})
        if state.get("claim_status") == "no_claims_found":
            return json.dumps({"status": "no_claims_found", "message": "No claims found for this account."})
        elif state.get("claim_status") == "multiple_claims":
            claims = details.get("claims", [])
            summary = [{"claim_id": c["claim_id"], "type": c["type"], "status": c["status"], "last_updated": c["last_updated"], "documents_needed": c.get("documents_needed", "")} for c in claims]
            return json.dumps({"status": "multiple_claims", "count": len(claims), "claims": summary})
        else:
            return json.dumps({
                "status": details.get("status", "unknown"),
                "claim_id": details.get("claim_id", ""),
                "type": details.get("type", ""),
                "date_filed": details.get("date_filed", ""),
                "last_updated": details.get("last_updated", ""),
                "documents_needed": details.get("documents_needed", ""),
                "adjuster_name": details.get("adjuster_name", ""),
                "notes": details.get("notes", ""),
            })

    elif tool_name == "search_faq":
        return json.dumps({"answer": state.get("faq_answer", "I don't have information on that topic.")})

    elif tool_name == "escalate_call":
        return json.dumps({
            "status": "escalating",
            "reason": state.get("escalation_reason", ""),
            "message": "Transferring to a representative now. Please stay on the line.",
        })

    return json.dumps({"status": "ok"})


def determine_sentiment(transcript: str) -> str:
    if not transcript:
        return "neutral"
    text = transcript.lower()
    negative_words = ["frustrated", "angry", "terrible", "horrible", "unacceptable", "worst", "hate", "upset", "ridiculous"]
    positive_words = ["thank", "great", "helpful", "appreciate", "wonderful", "excellent", "happy", "pleased"]
    neg_count = sum(1 for w in negative_words if w in text)
    pos_count = sum(1 for w in positive_words if w in text)
    if neg_count > pos_count:
        return "negative"
    elif pos_count > neg_count:
        return "positive"
    return "neutral"
