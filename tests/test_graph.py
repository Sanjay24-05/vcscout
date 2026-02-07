"""Tests for the LangGraph state machine logic"""

import pytest
from unittest.mock import MagicMock, patch

from src.graph.state import (
    AgentState,
    create_initial_state,
    merge_pivot_history,
    MarketResearchResult,
    CompetitorAnalysisResult,
    DevilsAdvocateFeedback,
)
from src.graph.edges import should_pivot_or_proceed, apply_pivot


class TestAgentState:
    """Tests for AgentState and related functions"""
    
    def test_create_initial_state(self):
        """Test initial state creation"""
        state = create_initial_state(
            job_id="job-123",
            session_id="session-456",
            idea="AI-powered dog walking app",
        )
        
        assert state["job_id"] == "job-123"
        assert state["session_id"] == "session-456"
        assert state["original_idea"] == "AI-powered dog walking app"
        assert state["current_idea"] == "AI-powered dog walking app"
        assert state["pivot_attempts"] == 0
        assert state["pivot_history"] == []
        assert state["status"] == "started"
        assert state["error"] is None
    
    def test_merge_pivot_history(self):
        """Test pivot history merging"""
        existing = [{"attempt_num": 1, "idea": "original"}]
        new = [{"attempt_num": 2, "idea": "pivoted"}]
        
        result = merge_pivot_history(existing, new)
        
        assert len(result) == 2
        assert result[0]["attempt_num"] == 1
        assert result[1]["attempt_num"] == 2
    
    def test_merge_pivot_history_with_none(self):
        """Test pivot history merging with None values"""
        assert merge_pivot_history(None, None) == []
        assert merge_pivot_history([{"a": 1}], None) == [{"a": 1}]
        assert merge_pivot_history(None, [{"b": 2}]) == [{"b": 2}]


class TestConditionalEdges:
    """Tests for conditional edge logic"""
    
    @patch("src.graph.edges.get_settings")
    def test_should_proceed_to_writer_on_high_score(self, mock_settings):
        """Test that high scores proceed to writer"""
        mock_settings.return_value.pivot_threshold = 5
        mock_settings.return_value.max_pivot_attempts = 3
        
        state: AgentState = {
            "devils_advocate_feedback": {"score": 7},
            "pivot_attempts": 0,
        }
        
        result = should_pivot_or_proceed(state)
        assert result == "write_success"
    
    @patch("src.graph.edges.get_settings")
    def test_should_pivot_on_low_score_with_attempts_remaining(self, mock_settings):
        """Test that low scores trigger pivot when attempts remain"""
        mock_settings.return_value.pivot_threshold = 5
        mock_settings.return_value.max_pivot_attempts = 3
        
        state: AgentState = {
            "devils_advocate_feedback": {"score": 4},
            "pivot_attempts": 1,
        }
        
        result = should_pivot_or_proceed(state)
        assert result == "pivot"
    
    @patch("src.graph.edges.get_settings")
    def test_should_write_failure_when_pivots_exhausted(self, mock_settings):
        """Test that exhausted pivots lead to market reality report"""
        mock_settings.return_value.pivot_threshold = 5
        mock_settings.return_value.max_pivot_attempts = 3
        
        state: AgentState = {
            "devils_advocate_feedback": {"score": 3},
            "pivot_attempts": 3,
        }
        
        result = should_pivot_or_proceed(state)
        assert result == "write_failure"
    
    @patch("src.graph.edges.get_settings")
    def test_apply_pivot_updates_state(self, mock_settings):
        """Test that apply_pivot correctly updates state"""
        mock_settings.return_value.pivot_threshold = 5
        mock_settings.return_value.max_pivot_attempts = 3
        
        state: AgentState = {
            "current_idea": "Generic todo app",
            "pivot_attempts": 1,
            "devils_advocate_feedback": {
                "score": 4,
                "suggested_pivot": "Todo app for remote teams with async standup features",
                "reason": "Market too crowded",
            },
        }
        
        result = apply_pivot(state)
        
        assert result["current_idea"] == "Todo app for remote teams with async standup features"
        assert result["pivot_attempts"] == 2
        assert len(result["pivot_history"]) == 1
        assert result["pivot_history"][0]["attempt_num"] == 2
        assert result["pivot_history"][0]["original_idea"] == "Generic todo app"
        assert result["status"] == "pivoting"


class TestPydanticModels:
    """Tests for Pydantic model validation"""
    
    def test_market_research_result_validation(self):
        """Test MarketResearchResult model"""
        data = {
            "market_size_estimate": "$50B TAM",
            "growth_rate": "15% CAGR",
            "key_trends": ["AI adoption", "Remote work"],
            "target_demographics": "SMBs in tech",
            "market_maturity": "growing",
            "data_sources": ["https://example.com"],
            "summary": "Growing market with strong trends.",
        }
        
        result = MarketResearchResult(**data)
        assert result.market_size_estimate == "$50B TAM"
        assert result.market_maturity == "growing"
    
    def test_devils_advocate_feedback_validation(self):
        """Test DevilsAdvocateFeedback model with score bounds"""
        data = {
            "score": 7,
            "verdict": "invest",
            "reason": "Strong market opportunity",
            "key_risks": ["Competition"],
            "key_opportunities": ["First mover"],
            "suggested_pivot": None,
            "pivot_rationale": None,
        }
        
        result = DevilsAdvocateFeedback(**data)
        assert result.score == 7
        assert result.verdict == "invest"
    
    def test_devils_advocate_feedback_score_bounds(self):
        """Test that score validation clamps to 1-10 range"""
        # Score 11 should be clamped to 10
        result = DevilsAdvocateFeedback(
            score=11,
            verdict="invest",
            reason="Test",
            key_risks=[],
            key_opportunities=[],
        )
        assert result.score == 10
        
        # Score 0 should be clamped to 1
        result = DevilsAdvocateFeedback(
            score=0,
            verdict="invest",
            reason="Test",
            key_risks=[],
            key_opportunities=[],
        )
        assert result.score == 1
        
        # String score should be converted
        result = DevilsAdvocateFeedback(
            score="8",
            verdict="invest",
            reason="Test",
        )
        assert result.score == 8
