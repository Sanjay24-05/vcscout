"""LangGraph state machine builder"""

from langgraph.graph import END, START, StateGraph

from src.agents.competitor_analyst import competitor_analyst
from src.agents.devils_advocate import devils_advocate
from src.agents.market_researcher import market_researcher
from src.agents.writer import writer
from src.graph.edges import apply_pivot, should_pivot_or_proceed
from src.graph.nodes import create_node_wrapper
from src.graph.state import AgentState


def build_graph() -> StateGraph:
    """
    Build the VC Scout LangGraph state machine.
    
    The graph flow:
    
    START → market_researcher → competitor_analyst → devils_advocate
                     ↑                                      │
                     │                                      ▼
                     │                            [conditional edge]
                     │                           /     |          \\
                     │                     pivot   write_success  write_failure
                     │                       │          │              │
                     └───── apply_pivot ◄────┘          ▼              ▼
                                                      writer ────► END
    """
    # Create the graph with our state type
    graph = StateGraph(AgentState)
    
    # Wrap nodes with persistence and error handling
    wrapped_market_researcher = create_node_wrapper(market_researcher, "market_researcher")
    wrapped_competitor_analyst = create_node_wrapper(competitor_analyst, "competitor_analyst")
    wrapped_devils_advocate = create_node_wrapper(devils_advocate, "devils_advocate")
    wrapped_writer = create_node_wrapper(writer, "writer")
    
    # Add nodes
    graph.add_node("market_researcher", wrapped_market_researcher)
    graph.add_node("competitor_analyst", wrapped_competitor_analyst)
    graph.add_node("devils_advocate", wrapped_devils_advocate)
    graph.add_node("apply_pivot", apply_pivot)
    graph.add_node("writer", wrapped_writer)
    
    # Add edges: linear flow to devils_advocate
    graph.add_edge(START, "market_researcher")
    graph.add_edge("market_researcher", "competitor_analyst")
    graph.add_edge("competitor_analyst", "devils_advocate")
    
    # Add conditional edge from devils_advocate
    graph.add_conditional_edges(
        "devils_advocate",
        should_pivot_or_proceed,
        {
            "pivot": "apply_pivot",
            "write_success": "writer",
            "write_failure": "writer",
        },
    )
    
    # Pivot loops back to market_researcher
    graph.add_edge("apply_pivot", "market_researcher")
    
    # Writer ends the graph
    graph.add_edge("writer", END)
    
    return graph


def compile_graph():
    """Compile the graph for execution"""
    graph = build_graph()
    return graph.compile()


# Lazy-loaded compiled graph
_compiled_graph = None


def get_compiled_graph():
    """Get the compiled graph (singleton)"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_graph()
    return _compiled_graph
