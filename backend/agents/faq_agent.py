import logging
from backend.agents.state import AgentState
from backend.knowledge.retriever import search_faq

logger = logging.getLogger(__name__)


def faq_agent_node(state: AgentState) -> dict:
    params = state.get("tool_params", {})
    question = params.get("question", "")

    logger.info(f"[FAQ AGENT] Searching for: '{question}'")

    answer = search_faq(question)

    logger.info(f"[FAQ AGENT] Answer: '{answer[:200]}'")
    return {"faq_answer": answer}
