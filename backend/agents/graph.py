from langgraph.graph import StateGraph, END
from backend.agents.state import AgentState
from backend.agents.supervisor import supervisor_node, route_from_supervisor
from backend.agents.auth_agent import auth_agent_node
from backend.agents.claims_agent import claims_agent_node
from backend.agents.faq_agent import faq_agent_node
from backend.agents.escalation_agent import escalation_agent_node


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("auth_agent", auth_agent_node)
    graph.add_node("claims_agent", claims_agent_node)
    graph.add_node("faq_agent", faq_agent_node)
    graph.add_node("escalation_agent", escalation_agent_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "auth_agent": "auth_agent",
            "claims_agent": "claims_agent",
            "faq_agent": "faq_agent",
            "escalation_agent": "escalation_agent",
            "end": END,
        },
    )

    graph.add_edge("auth_agent", END)
    graph.add_edge("claims_agent", END)
    graph.add_edge("faq_agent", END)
    graph.add_edge("escalation_agent", END)

    return graph.compile()


agent_graph = build_graph()
