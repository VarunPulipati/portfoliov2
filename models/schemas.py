"""
UNLOOP — API Schemas (Pydantic v2)
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any


class TrajectoryEntry(BaseModel):
    id: str = ""
    timestamp: str = ""
    url: str = ""
    domain: str = ""
    page_title: str = ""
    interaction_type: str = "view"
    interaction_weight: float = 1.0
    dwell_time_seconds: float = 0
    scroll_depth: float = 0
    is_high_signal: bool = False
    extracted_features: Dict[str, Any] = {}
    meta: Dict[str, Any] = {}


class TrajectorySync(BaseModel):
    user_id: str
    entries: List[TrajectoryEntry] = []
    feature_timeline: List[Dict[str, Any]] = []


class PathMatchRequest(BaseModel):
    user_id: str
    current_features: Dict[str, Any] = {}
    velocity_score: float = 0.5
    num_matches: int = 10
    lookahead_weeks: int = 12


class UserUpdate(BaseModel):
    name: Optional[str] = None
    interests: Optional[str] = None
    goal: Optional[str] = None


class ProductClick(BaseModel):
    user_id: str
    product_id: str
