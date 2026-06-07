import logging
from backend.agents.state import AgentState
from backend.integrations.google_sheets import get_claims_for_account

logger = logging.getLogger(__name__)


def claims_agent_node(state: AgentState) -> dict:
    params = state.get("tool_params", {})
    account_id = params.get("account_id", "") or state.get("account_id", "")

    logger.info(f"[CLAIMS AGENT] Looking up claims for account: '{account_id}'")

    claims = get_claims_for_account(account_id)

    if not claims:
        logger.info(f"[CLAIMS AGENT] Result: NO CLAIMS FOUND")
        return {
            "claim_status": "no_claims_found",
            "claim_details": {"message": "No claims found for this account."},
        }

    if len(claims) == 1:
        logger.info(f"[CLAIMS AGENT] Result: Single claim - {claims[0]['claim_id']} ({claims[0]['status']})")
        return {
            "claim_status": claims[0]["status"],
            "claim_details": claims[0],
        }

    logger.info(f"[CLAIMS AGENT] Result: {len(claims)} claims found")
    return {
        "claim_status": "multiple_claims",
        "claim_details": {"claims": claims, "count": len(claims)},
    }
