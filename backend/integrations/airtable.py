import httpx
from datetime import datetime, timezone
from backend.config import settings


def _get_base_url() -> str:
    return f"https://api.airtable.com/v0/{settings.airtable_base_id}/{settings.airtable_table_name}"


def _get_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.airtable_api_key}",
        "Content-Type": "application/json",
    }


async def write_call_log(
    caller_name: str,
    phone: str,
    call_summary: str,
    sentiment: str,
    resolution: str,
    agent_types_used: list[str],
    call_id: str = "",
    duration_seconds: int = 0,
) -> dict:
    payload = {
        "records": [
            {
                "fields": {
                    "caller_name": caller_name,
                    "phone": phone,
                    "call_summary": call_summary,
                    "sentiment": sentiment,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "resolution": resolution,
                    "agent_types_used": ", ".join(agent_types_used),
                    "call_id": call_id,
                    "duration_seconds": duration_seconds,
                }
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(_get_base_url(), json=payload, headers=_get_headers())
        response.raise_for_status()
        return response.json()


async def write_escalation_log(
    caller_name: str,
    phone: str,
    reason: str,
    is_emergency: bool = False,
    call_id: str = "",
) -> dict:
    url = f"https://api.airtable.com/v0/{settings.airtable_base_id}/Escalations"
    payload = {
        "records": [
            {
                "fields": {
                    "caller_name": caller_name,
                    "phone": phone,
                    "escalation_reason": reason,
                    "is_emergency": is_emergency,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "call_id": call_id,
                }
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=_get_headers())
        response.raise_for_status()
        return response.json()


async def get_call_logs(max_records: int = 50) -> list[dict]:
    params = {
        "maxRecords": max_records,
        "sort[0][field]": "timestamp",
        "sort[0][direction]": "desc",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(_get_base_url(), headers=_get_headers(), params=params)
        response.raise_for_status()
        return response.json().get("records", [])
