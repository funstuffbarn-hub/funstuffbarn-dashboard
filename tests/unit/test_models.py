"""
Unit tests for shared/models.py
"""
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from services.shared.models import (
    AgentResult,
    AgentStatus,
    AgentTask,
    AgentType,
    APIResponse,
    CompetitionEntry,
    CreativeReport,
    DailyReportEmail,
    DesignConcept,
    EmailPayload,
    EventType,
    GapOpportunity,
    ListingSummary,
    MarketAnalysisReport,
    PaginatedResponse,
    PinterestReport,
    PinterestTrend,
    ScoredDesign,
    SeasonalEvent,
    StoreReport,
    StrategyReport,
    SystemEvent,
    TrendData,
)


class TestEnums:
    """Test enum values."""

    def test_agent_type_values(self):
        assert AgentType.MERCADO == "mercado"
        assert AgentType.CREATIVO == "creativo"
        assert AgentType.PINTEREST == "pinterest"
        assert AgentType.TIENDA == "tienda"
        assert AgentType.ESTRATEGIA == "estrategia"

    def test_agent_status_values(self):
        assert AgentStatus.PENDING == "pending"
        assert AgentStatus.RUNNING == "running"
        assert AgentStatus.COMPLETED == "completed"
        assert AgentStatus.FAILED == "failed"
        assert AgentStatus.SKIPPED == "skipped"


class TestAgentTask:
    """Tests for AgentTask model."""

    def test_agent_task_creation(self):
        task = AgentTask(
            agent_type="mercado",
            payload={"keywords": ["test"]},
            priority=5,
        )
        assert task.agent_type == "mercado"
        assert task.payload == {"keywords": ["test"]}
        assert task.priority == 5
        assert isinstance(task.id, UUID)
        assert isinstance(task.correlation_id, UUID)
        assert isinstance(task.created_at, datetime)

    def test_agent_task_with_all_fields(self):
        correlation_id = uuid4()
        scheduled = datetime.utcnow()

        task = AgentTask(
            id=uuid4(),
            agent_type="creativo",
            payload={"key": "value"},
            priority=8,
            correlation_id=correlation_id,
            scheduled_at=scheduled,
        )
        assert task.correlation_id == correlation_id
        assert task.scheduled_at == scheduled


class TestAgentResult:
    """Tests for AgentResult model."""

    def test_agent_result_success(self):
        result = AgentResult(
            task_id=uuid4(),
            agent_type="mercado",
            status=AgentStatus.COMPLETED,
            result={"data": "test"},
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            duration_seconds=10.5,
            correlation_id=uuid4(),
        )
        assert result.success is True
        assert result.status == AgentStatus.COMPLETED
        assert result.result == {"data": "test"}

    def test_agent_result_failure(self):
        correlation_id = uuid4()
        started = datetime.utcnow()
        completed = datetime.utcnow()

        result = AgentResult(
            task_id=uuid4(),
            agent_type="creativo",
            status=AgentStatus.FAILED,
            error="API timeout",
            started_at=started,
            completed_at=completed,
            duration_seconds=5.0,
            correlation_id=correlation_id,
        )
        assert result.success is False
        assert result.status == AgentStatus.FAILED
        assert result.error == "API timeout"


class TestMarketModels:
    """Tests for market analysis models."""

    def test_trend_data(self):
        trend = TrendData(
            keyword="national park shirt",
            interest=75,
            date=datetime.utcnow(),
        )
        assert trend.keyword == "national park shirt"
        assert trend.interest == 75

    def test_competition_entry(self):
        entry = CompetitionEntry(
            title="National Park Shirt",
            price=29.99,
            favorites=150,
            url="https://etsy.com/listing/123",
            shop_name="TestShop",
        )
        assert entry.title == "National Park Shirt"
        assert entry.price == 29.99
        assert entry.favorites == 150

    def test_market_analysis_report(self):
        trend = TrendData(keyword="test", interest=50, date=datetime.utcnow())
        entry = CompetitionEntry(title="test", price=10.0, favorites=10, url="url", shop_name="shop")

        report = MarketAnalysisReport(
            trends=[trend],
            competition=[entry],
            top_keywords=["keyword1", "keyword2"],
            price_ranges={"min": 10.0, "max": 50.0},
            opportunities=["opportunity1"],
            threats=["threat1"],
            raw_analysis="Analysis text",
        )
        assert len(report.trends) == 1
        assert len(report.competition) == 1
        assert report.top_keywords == ["keyword1", "keyword2"]


class TestCreativeModels:
    """Tests for creative models."""

    def test_design_concept(self):
        concept = DesignConcept(
            name="TEST DESIGN",
            concept="A beautiful design",
            style="vintage",
            primary_product="polera",
            additional_products=["hoodie", "sombrero"],
            why_it_works="It works because...",
            prompt="prompt for AI",
            tags=["nature", "vintage"],
        )
        assert concept.name == "TEST DESIGN"
        assert concept.primary_product == "polera"
        assert "hoodie" in concept.additional_products

    def test_creative_report(self):
        concept = DesignConcept(
            name="TEST",
            concept="concept",
            style="style",
            primary_product="polera",
            additional_products=[],
            why_it_works="works",
            prompt="prompt",
        )
        report = CreativeReport(
            designs=[concept],
            expansions="Expansions text",
        )
        assert len(report.designs) == 1
        assert report.expansions == "Expansions text"


class TestPinterestModels:
    """Tests for Pinterest models."""

    def test_pinterest_trend(self):
        trend = PinterestTrend(
            category="visual",
            keywords=["keyword1", "keyword2"],
            visual_style="minimalist",
            opportunity="High demand",
        )
        assert trend.category == "visual"
        assert len(trend.keywords) == 2

    def test_pinterest_report(self):
        trend = PinterestTrend(category="test", keywords=["k1"])
        report = PinterestReport(
            visual_trends=[trend],
            rising_topics=["topic1"],
            opportunities=["opportunity1"],
            keywords=["kw1", "kw2"],
        )
        assert len(report.visual_trends) == 1
        assert report.rising_topics == ["topic1"]


class TestStoreModels:
    """Tests for store models."""

    def test_listing_summary(self):
        listing = ListingSummary(
            listing_id="123",
            title="Test Shirt",
            price=29.99,
            state="active",
            views=100,
            favorites=50,
            sales=10,
            url="https://etsy.com/listing/123",
        )
        assert listing.listing_id == "123"
        assert listing.price == 29.99

    def test_store_report(self):
        listing = ListingSummary(
            listing_id="123",
            title="Test",
            price=29.99,
            state="active",
        )
        report = StoreReport(
            active_listings=[listing],
            draft_listings=[],
            printful_products=["Product1"],
            market_diagnosis="Good market",
            store_status="Growing",
            launch_strategy=["Launch 1"],
            weekly_actions=["Action 1"],
            immediate_action="Action now",
        )
        assert len(report.active_listings) == 1
        assert report.store_status == "Growing"


class TestStrategyModels:
    """Tests for strategy models."""

    def test_scored_design(self):
        design = ScoredDesign(
            name="Test Design",
            score=8.5,
            primary_product="polera",
            additional_products=["hoodie"],
            prompt="prompt text",
            gap_match=True,
            action="HACER",
        )
        assert design.score == 8.5
        assert design.action == "HACER"

    def test_gap_opportunity(self):
        gap = GapOpportunity(
            theme="National Parks",
            reason="High demand, low competition",
        )
        assert gap.theme == "National Parks"

    def test_seasonal_event(self):
        event = SeasonalEvent(
            week="Week 1",
            theme="Back to School",
            focus="Teacher gifts",
            deadline_upload="Aug 1",
        )
        assert event.week == "Week 1"
        assert event.focus == "Teacher gifts"

    def test_strategy_report(self):
        ScoredDesign(
            name="Test",
            score=8.0,
            primary_product="polera",
            additional_products=[],
            prompt="prompt",
            action="HACER",
        )
        GapOpportunity(theme="Parks", reason="High demand")
        SeasonalEvent(week="Week 1", theme="Theme", focus="Focus", deadline_upload="Jan 1")

        report = StrategyReport(
            top_actions=[],
            scorecard=[ScoredDesign(name="D", score=8.0, primary_product="p", additional_products=[], prompt="p", action="HACER")],
            gaps=[GapOpportunity(theme="T", reason="R")],
            calendar=[SeasonalEvent(week="W1", theme="T", focus="F", deadline_upload="D")],
            metadata={},
        )
        assert len(report.gaps) == 1
        assert len(report.calendar) == 1


class TestEmailModels:
    """Tests for email models."""

    def test_email_payload(self):
        email = EmailPayload(
            to="test@test.com",
            subject="Test Subject",
            body="Test body",
            html_body="<p>HTML</p>",
            attachments=["file1.pdf"],
        )
        assert email.to == "test@test.com"
        assert email.attachments == ["file1.pdf"]

    def test_daily_report_email(self):
        email = DailyReportEmail(
            date=datetime.utcnow(),
            market_summary="Market good",
            creative_highlights=["Design 1"],
            store_updates=["New listing"],
            strategy_actions=["Launch product"],
            metrics={"sales": 100},
        )
        assert email.market_summary == "Market good"
        assert len(email.creative_highlights) == 1


class TestEventModels:
    """Tests for event models."""

    def test_event_type(self):
        assert EventType.AGENT_STARTED == "agent.started"
        assert EventType.AGENT_COMPLETED == "agent.completed"
        assert EventType.AGENT_FAILED == "agent.failed"
        assert EventType.REPORT_GENERATED == "report.generated"

    def test_system_event(self):
        event = SystemEvent(
            event_type=EventType.AGENT_STARTED,
            source="orchestrator",
            payload={"agent": "mercado"},
        )
        assert event.event_type == EventType.AGENT_STARTED
        assert event.source == "orchestrator"
        assert isinstance(event.correlation_id, UUID)
        assert isinstance(event.timestamp, datetime)


class TestAPIResponseModels:
    """Tests for API response models."""

    def test_api_response_success(self):
        response = APIResponse(
            success=True,
            data={"key": "value"},
            message="Success",
        )
        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.message == "Success"

    def test_api_response_error(self):
        response = APIResponse(
            success=False,
            error="Error message",
        )
        assert response.success is False
        assert response.error == "Error message"

    def test_paginated_response(self):
        response = PaginatedResponse(
            items=[1, 2, 3],
            total=100,
            page=1,
            page_size=10,
            total_pages=10,
            has_next=True,
            has_prev=False,
        )
        assert response.total == 100
        assert response.page == 1
        assert response.has_next is True
        assert response.has_prev is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
