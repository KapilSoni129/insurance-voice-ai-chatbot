from fastapi import APIRouter
from backend.integrations.airtable import get_call_logs

router = APIRouter()


@router.get("/calls")
async def list_calls():
    records = await get_call_logs(max_records=50)
    return {"calls": [format_record(r) for r in records]}


@router.get("/calls/{call_id}")
async def get_call(call_id: str):
    records = await get_call_logs(max_records=100)
    for r in records:
        if r.get("fields", {}).get("call_id") == call_id:
            return {"call": format_record(r)}
    return {"error": "Call not found"}


def format_record(record: dict) -> dict:
    fields = record.get("fields", {})
    return {
        "id": record.get("id", ""),
        "caller_name": fields.get("caller_name", ""),
        "phone": fields.get("phone", ""),
        "call_summary": fields.get("call_summary", ""),
        "sentiment": fields.get("sentiment", "neutral"),
        "timestamp": fields.get("timestamp", ""),
        "resolution": fields.get("resolution", ""),
        "agent_types_used": fields.get("agent_types_used", ""),
        "call_id": fields.get("call_id", ""),
        "duration_seconds": fields.get("duration_seconds", 0),
    }
