"""
Shared Pydantic models for agent communication and data contracts.
"""
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentStatus(StrEnum):
    """Agent execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentType(StrEnum):
    """Types of agents in the system."""
    MERCADO = "mercado"          # Market analysis
    CREATIVO = "creativo"        # Creative ideas
    PINTEREST = "pinterest"      # Pinterest trends
    TIENDA = "tienda"            # Store management
    ESTRATEGIA = "estrategia"    # Product strategy


class ReportStatus(StrEnum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTask(BaseModel):
    """Task assigned to an agent."""
    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    agent_type: AgentType
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)
    correlation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_at: datetime | None = None


class AgentResult(BaseModel):
    """Result from agent execution."""
    model_config = ConfigDict(use_enum_values=True)

    task_id: UUID
    agent_type: AgentType
    status: AgentStatus
    success: bool = False
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    correlation_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def set_success_from_status(self):
        if self.status == AgentStatus.COMPLETED:
            self.success = True
        return self


class AgentHealth(BaseModel):
    """Agent health status."""
    agent_type: AgentType
    status: AgentStatus
    last_run: datetime | None = None
    last_success: datetime | None = None
    last_error: str | None = None
    total_runs: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0


# ============================================================
# Market Analysis Models
# ============================================================

class TrendData(BaseModel):
    """Google Trends data point."""
    keyword: str
    interest: int
    date: datetime


class CompetitionEntry(BaseModel):
    """Competitor listing data."""
    title: str
    price: float
    favorites: int
    url: str
    shop_name: str


class MarketAnalysisReport(BaseModel):
    """Market analysis report from Agent 1."""
    model_config = ConfigDict(use_enum_values=True)

    date: datetime = Field(default_factory=datetime.utcnow)
    trends: list[TrendData] = Field(default_factory=list)
    competition: list[CompetitionEntry] = Field(default_factory=list)
    top_keywords: list[str] = Field(default_factory=list)
    price_ranges: dict[str, float] = Field(default_factory=dict)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    raw_analysis: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Creative Ideas Models
# ============================================================

class DesignConcept(BaseModel):
    """Individual design concept from creative agent."""
    name: str
    concept: str
    style: str
    primary_product: str
    additional_products: list[str] = Field(default_factory=list)
    why_it_works: str
    prompt: str
    tags: list[str] = Field(default_factory=list)


class CreativeReport(BaseModel):
    """Creative ideas report from Agent 2."""
    date: datetime = Field(default_factory=datetime.utcnow)
    designs: list[DesignConcept] = Field(default_factory=list)
    expansions: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Pinterest Trends Models
# ============================================================

class PinterestTrend(BaseModel):
    """Pinterest trend data."""
    category: str
    keywords: list[str] = Field(default_factory=list)
    visual_style: str = ""
    opportunity: str = ""


class PinterestReport(BaseModel):
    """Pinterest trends report from Agent Pinterest."""
    date: datetime = Field(default_factory=datetime.utcnow)
    visual_trends: list[PinterestTrend] = Field(default_factory=list)
    rising_topics: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    raw_analysis: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Store Management Models
# ============================================================

class ListingSummary(BaseModel):
    """Summary of an Etsy listing."""
    listing_id: str
    title: str
    price: float
    state: str
    views: int = 0
    favorites: int = 0
    sales: int = 0
    url: str = ""


# Alias for backward compatibility
ListingData = ListingSummary


class StoreReport(BaseModel):
    """Store management report from Agent 3."""
    date: datetime = Field(default_factory=datetime.utcnow)
    active_listings: list[ListingSummary] = Field(default_factory=list)
    draft_listings: list[ListingSummary] = Field(default_factory=list)
    printful_products: list[str] = Field(default_factory=list)
    market_diagnosis: str = ""
    store_status: str = ""
    launch_strategy: list[str] = Field(default_factory=list)
    weekly_actions: list[str] = Field(default_factory=list)
    immediate_action: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Strategy Models
# ============================================================

class ScoredDesign(BaseModel):
    """Design with priority score."""
    name: str
    score: float = Field(ge=0, le=10)
    primary_product: str
    additional_products: list[str] = Field(default_factory=list)
    prompt: str
    gap_match: bool = False
    action: str = "WAIT"  # HACER, TEST, ESPERAR


class GapOpportunity(BaseModel):
    """Market gap opportunity."""
    theme: str
    reason: str


class SeasonalEvent(BaseModel):
    """Seasonal calendar event."""
    week: str
    theme: str
    focus: str
    deadline_upload: str


class StrategyReport(BaseModel):
    """Strategic report from Agent 5."""
    date: datetime = Field(default_factory=datetime.utcnow)
    top_actions: list[ScoredDesign] = Field(default_factory=list)
    scorecard: list[ScoredDesign] = Field(default_factory=list)
    gaps: list[GapOpportunity] = Field(default_factory=list)
    calendar: list[SeasonalEvent] = Field(default_factory=list)
    prompts: list[ScoredDesign] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Sales/Metrics Models
# ============================================================

class SalesMetrics(BaseModel):
    """Sales metrics for reporting."""
    total_sales: int = 0
    total_revenue: float = 0.0
    total_views: int = 0
    total_favorites: int = 0
    conversion_rate: float = 0.0
    avg_order_value: float = 0.0
    top_products: list[dict[str, Any]] = Field(default_factory=list)
    period_start: datetime
    period_end: datetime
    currency: str = "USD"


# ============================================================
# Event Models (for event-driven architecture)
# ============================================================
# Email/Notification Models
# ============================================================

class EmailPayload(BaseModel):
    """Email payload for notifications."""
    to: str
    subject: str
    body: str
    html_body: str | None = None
    attachments: list[str] = Field(default_factory=list)


class DailyReportEmail(BaseModel):
    """Daily report email content."""
    date: datetime
    market_summary: str
    creative_highlights: list[str]
    store_updates: list[str]
    strategy_actions: list[str]
    metrics: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Event Models (for event-driven architecture)
# ============================================================

class EventType(StrEnum):
    """System event types."""
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    REPORT_GENERATED = "report.generated"
    EMAIL_SENT = "email.sent"
    BACKUP_COMPLETED = "backup.completed"
    HEALTH_CHECK_FAILED = "health.check.failed"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker.opened"
    BACKUP_FAILED = "backup.failed"


class SystemEvent(BaseModel):
    """System event for event-driven architecture."""
    event_type: EventType
    correlation_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# API Response Models
# ============================================================

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool = True
    data: Any | None = None
    error: str | None = None
    message: str | None = None
    correlation_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
