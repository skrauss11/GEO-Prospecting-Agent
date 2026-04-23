"""
Cross-vertical scoring normalization.

Different verticals may use different scoring scales (1-5 vs 1-10).
This module normalizes all scores to a 0.0-1.0 scale for comparison.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Dict


@dataclass
class ScoringConfig:
    """Configuration for a vertical's scoring system."""
    min_score: int = 1
    max_score: int = 5
    invert: bool = False  # If True, lower raw scores are better


class ScoringNormalizer:
    """
    Normalizes scores across different verticals to a common 0.0-1.0 scale.
    
    This allows comparison:
    - PS law firm scoring 5/5 = 1.0 (terrible GEO, high priority)
    - DTC brand scoring 4/5 = 0.8 (also bad GEO, slightly lower priority)
    """
    
    # Default configs by vertical
    VERTICAL_CONFIGS: Dict[str, ScoringConfig] = {
        "ps": ScoringConfig(min_score=1, max_score=5, invert=False),
        "dtc": ScoringConfig(min_score=1, max_score=5, invert=False),
    }
    
    def __init__(self, custom_configs: Optional[Dict[str, ScoringConfig]] = None):
        self.configs = {**self.VERTICAL_CONFIGS, **(custom_configs or {})}
    
    def normalize(
        self,
        score: int,
        vertical: str,
        max_score: Optional[int] = None,
    ) -> float:
        """
        Normalize a score to 0.0-1.0 scale.
        
        Args:
            score: Raw score from the vertical
            vertical: Vertical key (ps, dtc, etc.)
            max_score: Optional override for max score
            
        Returns:
            Normalized score between 0.0 and 1.0
        """
        config = self.configs.get(vertical, ScoringConfig())
        
        max_val = max_score or config.max_score
        min_val = config.min_score
        
        # Clamp score to valid range
        score = max(min_val, min(score, max_val))
        
        # Normalize to 0-1
        normalized = (score - min_val) / (max_val - min_val) if max_val > min_val else 0.5
        
        # Invert if needed (for scales where lower is better)
        if config.invert:
            normalized = 1.0 - normalized
        
        return round(normalized, 2)
    
    def get_priority_tier(self, normalized_score: float) -> str:
        """
        Get priority tier based on normalized score.
        
        Returns:
            'hot', 'warm', or 'cold'
        """
        if normalized_score >= 0.8:
            return "hot"
        elif normalized_score >= 0.5:
            return "warm"
        else:
            return "cold"
    
    def compare_across_verticals(
        self,
        prospects: list[tuple[str, int, str]],  # (name, score, vertical)
    ) -> list[tuple[str, float, str]]:
        """
        Compare prospects across different verticals.
        
        Returns list of (name, normalized_score, priority_tier) sorted by score.
        """
        normalized = []
        for name, score, vertical in prospects:
            norm = self.normalize(score, vertical)
            tier = self.get_priority_tier(norm)
            normalized.append((name, norm, tier))
        
        # Sort by normalized score descending
        return sorted(normalized, key=lambda x: x[1], reverse=True)
