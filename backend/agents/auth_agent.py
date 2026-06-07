import logging
from backend.agents.state import AgentState
from backend.integrations.google_sheets import (
    lookup_customer_by_phone,
    verify_customer_identity,
)

logger = logging.getLogger(__name__)


def auth_agent_node(state: AgentState) -> dict:
    params = state.get("tool_params", {})
    phone = params.get("phone_number", "")
    verification_value = params.get("verification_value", "")

    customer = lookup_customer_by_phone(phone)

    if not customer:
        logger.info(f"[AUTH] Not found: {phone}")
        return {"auth_status": "not_found", "caller_phone": phone}

    if verify_customer_identity(customer, verification_value):
        logger.info(f"[AUTH] Authenticated: {customer['name']}")
        return {
            "auth_status": "authenticated",
            "customer_name": customer["name"],
            "account_id": customer["account_id"],
            "caller_phone": phone,
        }

    attempts = state.get("auth_attempts", 0) + 1
    if attempts >= 2:
        logger.info(f"[AUTH] Failed after {attempts} attempts")
        return {"auth_status": "failed", "auth_attempts": attempts, "caller_phone": phone}

    logger.info(f"[AUTH] Verification failed, attempt {attempts}/2")
    return {"auth_status": "pending", "auth_attempts": attempts, "caller_phone": phone}
