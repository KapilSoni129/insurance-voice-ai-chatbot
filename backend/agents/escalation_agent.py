import logging
from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


def escalation_agent_node(state: AgentState) -> dict:
    params = state.get("tool_params", {})
    reason = params.get("reason", "Customer requested representative")
    is_emergency = params.get("is_emergency", False)
    caller_name = params.get("caller_name", "")
    phone = params.get("phone", "")

    if is_emergency:
        reason = f"EMERGENCY: {reason}"

    logger.info(f"[ESCALATION] {caller_name} ({phone}) - {reason}")
    return {
        "escalation_reason": reason,
        "resolution": "escalated",
        "customer_name": caller_name or state.get("customer_name"),
        "caller_phone": phone or state.get("caller_phone"),
    }
