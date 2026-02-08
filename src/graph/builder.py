"""LangGraph state machine builder"""

from langgraph.graph import END, START, StateGraph

from src.agents.competitor_analyst import competitor_analyst
from src.agents.debate_panel import debate_panel
from src.agents.devils_advocate import devils_advocate
from src.agents.input_validator import input_validator
from src.agents.market_researcher import market_researcher
from src.agents.writer import writer
from src.config import get_settings
from src.graph.edges import (
    apply_pivot,
    handle_invalid_input,
    should_pivot_or_proceed,
    should_proceed_after_debate,
    should_proceed_after_validation,
)
from src.graph.nodes import create_node_wrapper
from src.graph.state import AgentState


def build_graph(debate_mode: bool = True) -> StateGraph:
    """
    Build the VC Scout LangGraph state machine.
    
    Args:
        debate_mode: If True (default), use debate panel for single-pass analysis.
                    If False, use legacy devil's advocate with pivot loop.
    
    Debate Mode Flow:
    
    START → input_validator → [valid?] ─── (invalid) ──→ handle_invalid → END
                                  │
                              (valid)
                                  ▼
                          market_researcher
                                  │
                                  ▼
                          competitor_analyst
                                  │
                                  ▼
                            debate_panel
                                  │
                                  ▼
                          [verdict check]
                           /           \\
                    (pass)             (fail)
                       │                  │
                       ▼                  ▼
                writer (memo)     writer (reality)
                       │                  │
                       └────────┬─────────┘
                                ▼
                               END
    
    Legacy Mode Flow (debate_mode=False):
    
    START → input_validator → [valid?] ─── (invalid) ──→ handle_invalid → END
                                  │
                              (valid)
                                  ▼
                          market_researcher ◄─────────┐
                                  │                   │
                                  ▼                   │
                          competitor_analyst          │
                                  │                   │
                                  ▼                   │
                          devils_advocate             │
                                  │                   │
                                  ▼                   │
                          [conditional edge]          │
                         /     |          \\         │
                   pivot   success    failure        │
                     │        │          │           │
                     │        ▼          ▼           │
                     │      writer ──► END           │
                     │                               │
                     └───── apply_pivot ─────────────┘
    """
    # Create the graph with our state type
    graph = StateGraph(AgentState)
    
    # Wrap nodes with persistence and error handling
    wrapped_input_validator = create_node_wrapper(input_validator, "input_validator")
    wrapped_market_researcher = create_node_wrapper(market_researcher, "market_researcher")
    wrapped_competitor_analyst = create_node_wrapper(competitor_analyst, "competitor_analyst")
    wrapped_writer = create_node_wrapper(writer, "writer")
    
    # Add common nodes
    graph.add_node("input_validator", wrapped_input_validator)
    graph.add_node("handle_invalid", handle_invalid_input)
    graph.add_node("market_researcher", wrapped_market_researcher)
    graph.add_node("competitor_analyst", wrapped_competitor_analyst)
    graph.add_node("writer", wrapped_writer)
    
    # Start with input validation
    graph.add_edge(START, "input_validator")
    
    # Conditional edge after validation
    graph.add_conditional_edges(
        "input_validator",
        should_proceed_after_validation,
        {
            "valid": "market_researcher",
            "invalid": "handle_invalid",
        },
    )
    
    # Invalid input ends immediately
    graph.add_edge("handle_invalid", END)
    
    # Research flow
    graph.add_edge("market_researcher", "competitor_analyst")
    
    if debate_mode:
        # Debate mode: single-pass analysis with Bull/Bear/Synthesizer
        wrapped_debate_panel = create_node_wrapper(debate_panel, "debate_panel")
        graph.add_node("debate_panel", wrapped_debate_panel)
        
        graph.add_edge("competitor_analyst", "debate_panel")
        
        # Conditional edge after debate
        graph.add_conditional_edges(
            "debate_panel",
            should_proceed_after_debate,
            {
                "write_success": "writer",
                "write_failure": "writer",
            },
        )
    else:
        # Legacy mode: devil's advocate with pivot loop
        wrapped_devils_advocate = create_node_wrapper(devils_advocate, "devils_advocate")
        graph.add_node("devils_advocate", wrapped_devils_advocate)
        graph.add_node("apply_pivot", apply_pivot)
        
        graph.add_edge("competitor_analyst", "devils_advocate")
        
        # Conditional edge from devils_advocate
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


def compile_graph(debate_mode: bool | None = None):
    """
    Compile the graph for execution.
    
    Args:
        debate_mode: Override the debate mode setting. If None, uses config.
    """
    if debate_mode is None:
        settings = get_settings()
        debate_mode = settings.enable_debate_mode
    
    graph = build_graph(debate_mode=debate_mode)
    return graph.compile()


# Lazy-loaded compiled graph
_compiled_graph = None
_compiled_debate_mode = None


def get_compiled_graph():
    """Get the compiled graph (singleton, respects config)"""
    global _compiled_graph, _compiled_debate_mode
    
    settings = get_settings()
    current_debate_mode = settings.enable_debate_mode
    
    # Recompile if debate mode changed
    if _compiled_graph is None or _compiled_debate_mode != current_debate_mode:
        _compiled_graph = compile_graph(debate_mode=current_debate_mode)
        _compiled_debate_mode = current_debate_mode
    
    return _compiled_graph
