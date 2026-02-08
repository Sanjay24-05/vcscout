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
    InputValidationResult,
    DebateMessage,
    DebateResult,
)
from src.graph.edges import (
    should_pivot_or_proceed,
    apply_pivot,
    should_proceed_after_validation,
    should_proceed_after_debate,
    handle_invalid_input,
)


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


class TestInputValidation:
    """Tests for input validation functionality"""
    
    def test_input_validation_result_valid(self):
        """Test InputValidationResult for valid input"""
        result = InputValidationResult(
            is_valid=True,
            rejection_reason=None,
            suggested_reframe="AI-powered legal assistant for small businesses",
        )
        assert result.is_valid is True
        assert result.rejection_reason is None
        assert result.suggested_reframe is not None
    
    def test_input_validation_result_invalid(self):
        """Test InputValidationResult for invalid input"""
        result = InputValidationResult(
            is_valid=False,
            rejection_reason="Input appears to be random text without business context",
            suggested_reframe=None,
        )
        assert result.is_valid is False
        assert result.rejection_reason is not None
    
    def test_should_proceed_after_validation_valid(self):
        """Test that valid input proceeds to research"""
        state: AgentState = {
            "input_validation": {
                "is_valid": True,
                "rejection_reason": None,
            }
        }
        
        result = should_proceed_after_validation(state)
        assert result == "valid"
    
    def test_should_proceed_after_validation_invalid(self):
        """Test that invalid input rejects"""
        state: AgentState = {
            "input_validation": {
                "is_valid": False,
                "rejection_reason": "Not a business idea",
            }
        }
        
        result = should_proceed_after_validation(state)
        assert result == "invalid"
    
    def test_should_proceed_after_validation_missing(self):
        """Test that missing validation defaults to valid (proceed)"""
        state: AgentState = {}
        
        result = should_proceed_after_validation(state)
        assert result == "valid"
    
    def test_handle_invalid_input(self):
        """Test handle_invalid_input updates state correctly"""
        state: AgentState = {
            "input_validation": {
                "is_valid": False,
                "rejection_reason": "Input is gibberish",
            }
        }
        
        result = handle_invalid_input(state)
        
        assert result["status"] == "failed"
        assert "gibberish" in result["error"].lower()


class TestDebateFunctionality:
    """Tests for the debate panel functionality"""
    
    def test_debate_message_model(self):
        """Test DebateMessage model"""
        msg = DebateMessage(
            speaker="Bull",
            content="This is a compelling opportunity because...",
            timestamp="2024-01-01T00:00:00Z",
        )
        assert msg.speaker == "Bull"
        assert msg.timestamp == "2024-01-01T00:00:00Z"
    
    def test_debate_result_model_no_pivot(self):
        """Test DebateResult when no pivot is suggested"""
        result = DebateResult(
            score=7,
            verdict="conditional_invest",
            debate_transcript=[
                {"speaker": "Bull", "content": "Strong market", "timestamp": ""},
                {"speaker": "Bear", "content": "High competition", "timestamp": ""},
            ],
            bull_case="Large TAM with growing demand",
            bear_case="Crowded market with established players",
            synthesis="Proceed with differentiation focus",
            idea_was_pivoted=False,
            final_idea="AI-powered legal assistant",
        )
        assert result.idea_was_pivoted is False
        assert len(result.debate_transcript) == 2
        assert result.score == 7
    
    def test_debate_result_model_with_pivot(self):
        """Test DebateResult when pivot is suggested"""
        result = DebateResult(
            score=6,
            verdict="conditional_invest",
            debate_transcript=[],
            bull_case="Potential in niche",
            bear_case="Generic approach fails",
            synthesis="Pivot to vertical",
            idea_was_pivoted=True,
            final_idea="Legal assistant for immigration lawyers",
        )
        assert result.idea_was_pivoted is True
        assert "immigration" in result.final_idea.lower()
    
    @patch("src.graph.edges.get_settings")
    def test_should_proceed_after_debate_success(self, mock_settings):
        """Test proceeding after successful debate with high score"""
        mock_settings.return_value.pass_threshold = 5
        
        state: AgentState = {
            "debate_result": {
                "score": 7,  # Above threshold
                "idea_was_pivoted": False,
                "final_idea": "Original idea",
            }
        }
        
        result = should_proceed_after_debate(state)
        assert result == "write_success"
    
    @patch("src.graph.edges.get_settings")
    def test_should_proceed_after_debate_failure(self, mock_settings):
        """Test write_failure when debate score is too low"""
        mock_settings.return_value.pass_threshold = 5
        
        state: AgentState = {
            "debate_result": {
                "score": 4,  # Below threshold
                "idea_was_pivoted": True,
                "final_idea": "Pivoted idea for vertical market",
            }
        }
        
        result = should_proceed_after_debate(state)
        assert result == "write_failure"
    
    @patch("src.graph.edges.get_settings")
    def test_should_proceed_after_debate_missing(self, mock_settings):
        """Test fallback when debate result is missing"""
        mock_settings.return_value.pass_threshold = 5
        
        state: AgentState = {}
        
        result = should_proceed_after_debate(state)
        # No debate result means score=0 which is below threshold
        assert result == "write_failure"


class TestInitialStateEnhancements:
    """Tests for enhanced initial state"""
    
    def test_create_initial_state_has_validation_fields(self):
        """Test that initial state includes new validation/debate fields"""
        state = create_initial_state(
            job_id="job-123",
            session_id="session-456",
            idea="Test idea",
        )
        
        # Should have input_validation and debate_result as None initially
        assert state.get("input_validation") is None
        assert state.get("debate_result") is None
