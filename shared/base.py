"""
Base vertical class and shared data structures for GEO discovery.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union


@dataclass
class Prospect:
    """Structured prospect data — unified across all verticals."""
    
    # Identity
    name: str
    url: str
    vertical: str  # 'ps', 'dtc', etc.
    
    # Discovery metadata
    discovered_at: datetime = field(default_factory=datetime.now)
    source_query: str = ""
    
    # Scoring (vertical-specific)
    raw_score: int = 0  # 1-5 or 1-10 depending on vertical
    max_score: int = 5
    normalized_score: float = 0.0  # 0.0-1.0 normalized
    
    # GEO analysis
    geo_gaps: list[str] = field(default_factory=list)
    geo_strengths: list[str] = field(default_factory=list)
    
    # Contact info
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    linkedin: str = ""
    contact_page: str = ""
    
    # Vertical-specific attributes
    category: str = ""  # e.g., "Law Firm", "DTC Beauty"
    location: str = ""  # e.g., "NYC", "National"
    revenue_indicator: str = ""  # e.g., "$100M+", "$10M+"
    
    # Recommendation
    recommended_action: str = ""
    
    # Raw data for debugging
    _raw_analysis: dict = field(default_factory=dict, repr=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "url": self.url,
            "vertical": self.vertical,
            "discovered_at": self.discovered_at.isoformat(),
            "source_query": self.source_query,
            "scoring": {
                "raw_score": self.raw_score,
                "max_score": self.max_score,
                "normalized_score": round(self.normalized_score, 2),
            },
            "geo_analysis": {
                "gaps": self.geo_gaps,
                "strengths": self.geo_strengths,
            },
            "contacts": {
                "emails": self.emails,
                "phones": self.phones,
                "linkedin": self.linkedin,
                "contact_page": self.contact_page,
            },
            "attributes": {
                "category": self.category,
                "location": self.location,
                "revenue_indicator": self.revenue_indicator,
            },
            "recommended_action": self.recommended_action,
        }
    
    @property
    def score_emoji(self) -> str:
        """Get emoji based on normalized score."""
        if self.normalized_score >= 0.8:
            return "🔴"  # High priority
        elif self.normalized_score >= 0.6:
            return "🟡"  # Medium
        else:
            return "🟢"  # Low
    
    @property
    def domain(self) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        return parsed.netloc.replace("www.", "")


class BaseVertical(ABC):
    """Abstract base class for vertical discovery implementations."""
    
    # Override in subclass
    key: str = ""  # Short identifier: 'ps', 'dtc'
    name: str = ""  # Display name
    max_score: int = 5  # Maximum raw score for this vertical
    
    # Target criteria
    target_criteria: list[str] = field(default_factory=list)
    
    @abstractmethod
    def discover(
        self,
        count: int = 5,
        exclude_urls: Optional[list[str]] = None,
        test_mode: bool = False,
    ) -> list[Prospect]:
        """
        Discover prospects for this vertical.
        
        Args:
            count: Number of prospects to find
            exclude_urls: URLs to exclude (already discovered)
            test_mode: If True, use mock/simulated data
            
        Returns:
            List of Prospect objects
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self, exclude_urls: list[str], count: int = 3) -> str:
        """Get the system prompt for the LLM agent."""
        pass
    
    @abstractmethod
    def parse_agent_output(self, output: str) -> list[Prospect]:
        """Parse LLM agent output into structured Prospect objects."""
        pass
    
    def get_search_queries(self) -> list[str]:
        """Get list of search queries to use for discovery."""
        return []
