from pydantic import BaseModel
from typing import Optional

class Customer(BaseModel):
    account_id: str
    name: str
    phone: str
    dob: str
    last4ssn: str
    email: str

class Claim(BaseModel):
    claim_id: str
    account_id: str
    status: str
    type: str
    date_filed: str
    last_updated: str
    documents_needed: str
    adjuster_name: str
    notes: str

class CallLog(BaseModel):
    caller_name: str
    phone: str
    call_summary: str
    sentiment: str
    timestamp: str
    resolution: str
    agent_types_used: list[str]
    call_id: str
    duration_seconds: Optional[int] = 0