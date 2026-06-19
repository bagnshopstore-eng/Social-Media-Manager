"""Pydantic models + Mongo helpers for BagnShop Social Manager."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
import uuid


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


PostStatus = Literal[
    "draft", "pending_approval", "approved", "rejected",
    "needs_edit", "published", "expired",
]
Platform = Literal["instagram", "facebook", "linkedin"]
PostFormat = Literal["single_image", "carousel", "reel_script"]


class BaseDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


# ---------- Brand & Settings ----------
class BrandProfile(BaseDoc):
    brand_name: str = "BagnShop"
    website: str = "https://bagnshop.com"
    entity: str = "MuseMeh"
    positioning: str = "Smart Utility Lifestyle Brand"
    voice_rules: List[str] = Field(default_factory=lambda: [
        "smart", "useful", "honest", "no hype", "problem-first",
    ])
    banned_claims: List[str] = Field(default_factory=lambda: [
        "cures", "guaranteed", "best in India", "#1", "miracle",
        "doctor recommended", "clinically proven",
    ])
    content_pillars: List[str] = Field(default_factory=lambda: [
        "problem-solution product demos",
        "practical tips and education",
        "gifting and occasions",
        "behind the brand / founder",
        "social proof / UGC",
        "trend-jacking",
    ])
    cadence: dict = Field(default_factory=lambda: {
        "instagram": 5, "facebook": 4, "linkedin": 3,
    })
    linkedin_angle: str = (
        "corporate / B2B gifting + founder-led building-a-D2C-brand storytelling"
    )
    benchmarks: List[str] = Field(default_factory=lambda: ["boAt", "DailyObjects"])
    notification_emails: List[str] = Field(default_factory=lambda: [
        "mehull.bhatnagar@gmail.com", "bagnshopstore@gmail.com",
    ])
    telegram_chat_id: Optional[str] = None
    handles: dict = Field(default_factory=lambda: {
        "instagram": "https://www.instagram.com/bagnshop_official/",
        "facebook": "https://www.facebook.com/bagnshopofficial",
        "linkedin": "https://www.linkedin.com/company/bagnshop/",
    })


class Competitor(BaseDoc):
    name: str
    handles: dict  # {instagram, facebook, linkedin, website}
    last_scraped_at: Optional[datetime] = None


class CompetitorContent(BaseDoc):
    competitor_id: str
    competitor_name: str
    platform: Platform
    caption: str
    hook: str
    format: PostFormat
    hashtags: List[str] = Field(default_factory=list)
    likes: int = 0
    comments: int = 0
    engagement_rate: float = 0.0
    detected_hook_pattern: Optional[str] = None
    theme: Optional[str] = None
    scraped_at: datetime = Field(default_factory=now_utc)


class MyAnalyticsSnapshot(BaseDoc):
    platform: Platform
    followers: int
    avg_engagement_rate: float
    top_posts: List[dict] = Field(default_factory=list)
    peak_hours: List[int] = Field(default_factory=list)  # 0-23, top engagement hours
    peak_days: List[str] = Field(default_factory=list)  # Mon..Sun
    heatmap: List[List[float]] = Field(default_factory=list)  # 7x24 engagement by day/hour


class CalendarSlot(BaseDoc):
    date: str  # YYYY-MM-DD
    platform: Platform
    pillar: str
    format: PostFormat
    hook: str
    caption_angle: str
    cta: str
    hashtags: List[str] = Field(default_factory=list)
    scheduled_datetime: datetime
    status: Literal["planned", "creative_generated", "skipped"] = "planned"
    topic: str = ""


class Post(BaseDoc):
    calendar_slot_id: Optional[str] = None
    platform: Platform
    format: PostFormat
    caption: str
    image_urls: List[str] = Field(default_factory=list)  # served via /uploads
    hook: str = ""
    pillar: str = ""
    cta: str = ""
    hashtags: List[str] = Field(default_factory=list)
    scheduled_datetime: datetime
    status: PostStatus = "draft"
    approval_timestamp: Optional[datetime] = None
    published_id: Optional[str] = None
    published_at: Optional[datetime] = None
    performance: dict = Field(default_factory=dict)
    guardrail_issues: List[str] = Field(default_factory=list)
    product_id: Optional[str] = None  # if product post
    product_snapshot: Optional[dict] = None  # name, price, image at time of creation
    is_product_post: bool = False


class HookPattern(BaseModel):
    pattern: str
    description: str
    example: Optional[str] = None


class ContentGap(BaseModel):
    title: str
    description: str


class StrategistReport(BaseDoc):
    hook_patterns: List[HookPattern] = Field(default_factory=list)
    content_gaps: List[ContentGap] = Field(default_factory=list)
    pillars: List[str] = Field(default_factory=list)
    calendar_slots: List[str] = Field(default_factory=list)  # CalendarSlot ids
    notes: str = ""


class Learning(BaseDoc):
    period_start: datetime
    period_end: datetime
    top_hooks: List[dict] = Field(default_factory=list)
    top_formats: List[dict] = Field(default_factory=list)
    top_pillars: List[dict] = Field(default_factory=list)
    best_times: dict = Field(default_factory=dict)  # per platform
    notes: str = ""


# Mongo serialization helpers
def to_mongo(doc: BaseModel) -> dict:
    d = doc.model_dump()
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def from_mongo(doc: dict | None) -> dict | None:
    if not doc:
        return None
    doc.pop("_id", None)
    for k, v in list(doc.items()):
        if isinstance(v, str) and k.endswith(("_at", "_datetime")) and len(v) >= 19:
            try:
                doc[k] = datetime.fromisoformat(v)
            except Exception:
                pass
    return doc
