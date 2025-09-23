import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from decimal import Decimal


def test_cost_tracker_initialization():
    """Test CostTracker initialization and pricing models"""
    from cost_manager import CostTracker

    tracker = CostTracker(":memory:")  # Use in-memory DB for testing
    assert tracker.pricing_models is not None
    assert "openai" in tracker.pricing_models
    assert "claude" in tracker.pricing_models
    assert "gemini" in tracker.pricing_models


def test_calculate_cost_openai_gpt4():
    """Test cost calculation for OpenAI GPT-4"""
    from cost_manager import CostTracker

    tracker = CostTracker(":memory:")
    input_cost, output_cost, total_cost = tracker.calculate_cost(
        "openai", "gpt-4", 1000, 500
    )

    # GPT-4 pricing: $0.03 input, $0.06 output per 1K tokens
    expected_input = Decimal('0.03')  # 1000 tokens * $0.03 / 1000
    expected_output = Decimal('0.03')  # 500 tokens * $0.06 / 1000
    expected_total = expected_input + expected_output

    assert input_cost == expected_input
    assert output_cost == expected_output
    assert total_cost == expected_total


def test_calculate_cost_unknown_service():
    """Test cost calculation for unknown service returns zero"""
    from cost_manager import CostTracker

    tracker = CostTracker(":memory:")
    input_cost, output_cost, total_cost = tracker.calculate_cost(
        "unknown_service", "unknown_model", 1000, 500
    )

    assert input_cost == Decimal('0.00')
    assert output_cost == Decimal('0.00')
    assert total_cost == Decimal('0.00')


def test_calculate_cost_unknown_model():
    """Test cost calculation for unknown model returns zero"""
    from cost_manager import CostTracker

    tracker = CostTracker(":memory:")
    input_cost, output_cost, total_cost = tracker.calculate_cost(
        "openai", "unknown_model", 1000, 500
    )

    assert input_cost == Decimal('0.00')
    assert output_cost == Decimal('0.00')
    assert total_cost == Decimal('0.00')


def test_track_usage_basic():
    """Test basic usage tracking"""
    from cost_manager import CostTracker

    tracker = CostTracker(":memory:")
    event = tracker.track_usage(
        service="openai",
        model="gpt-4",
        operation_type="chat_completion",
        input_tokens=1000,
        output_tokens=500,
        user_id="test_user",
        conversation_id="test_conv"
    )

    assert event.service == "openai"
    assert event.model == "gpt-4"
    assert event.input_tokens == 1000
    assert event.output_tokens == 500
    assert event.total_tokens == 1500
    assert event.user_id == "test_user"
    assert event.conversation_id == "test_conv"
    assert isinstance(event.total_cost_usd, Decimal)
    assert event.total_cost_usd > 0


def test_track_llm_usage_function():
    """Test the convenience function track_llm_usage"""
    from cost_manager import track_llm_usage

    event = track_llm_usage(
        service="openai",
        model="gpt-3.5-turbo",
        input_tokens=1000,
        output_tokens=500,
        user_id="test_user"
    )

    assert event.service == "openai"
    assert event.model == "gpt-3.5-turbo"
    assert event.operation_type == "chat_completion"
    assert event.input_tokens == 1000
    assert event.output_tokens == 500
    assert event.user_id == "test_user"


def test_get_current_costs():
    """Test getting current costs"""
    from cost_manager import CostTracker, get_current_costs

    tracker = CostTracker(":memory:")

    # Add some usage first
    tracker.track_usage("openai", "gpt-4", "chat_completion", 1000, 500)

    # Get current costs
    stats = get_current_costs("daily")

    assert hasattr(stats, 'total_cost_usd')
    assert hasattr(stats, 'total_tokens')
    assert stats.total_cost_usd >= 0


def test_create_daily_budget():
    """Test creating a daily budget"""
    from cost_manager import create_daily_budget

    budget = create_daily_budget("test_budget", Decimal('10.00'), ["openai"])

    assert budget.name == "test_budget"
    assert budget.limit_type == "daily"
    assert budget.amount_usd == Decimal('10.00')
    assert budget.services == ["openai"]


def test_create_monthly_budget():
    """Test creating a monthly budget"""
    from cost_manager import create_monthly_budget

    budget = create_monthly_budget("monthly_budget", Decimal('100.00'))

    assert budget.name == "monthly_budget"
    assert budget.limit_type == "monthly"
    assert budget.amount_usd == Decimal('100.00')
