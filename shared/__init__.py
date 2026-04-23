"""
GEO Discovery Orchestrator — Multi-vertical prospect discovery system.
"""

from shared.base import BaseVertical, Prospect
from shared.history import UnifiedHistory
from shared.scoring import ScoringNormalizer
from shared.output import DiscordFormatter, CRMFormatter

__all__ = [
    "BaseVertical",
    "Prospect",
    "UnifiedHistory",
    "ScoringNormalizer",
    "DiscordFormatter",
    "CRMFormatter",
]
