"""
Unified history management — deduplicates prospects across all verticals.
"""

import json
from datetime import datetime
from pathlib import Path

from shared.base import Prospect


class UnifiedHistory:
    """
    Manages discovery history across all verticals.
    Stores by domain to prevent cross-vertical duplicates.
    """
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()
    
    def _load(self) -> dict:
        """Load history from disk."""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1,
            "urls": [],  # All discovered URLs
            "by_vertical": {},  # {vertical_key: [urls]}
            "prospects": [],  # Full prospect records
            "last_updated": datetime.now().isoformat(),
        }
    
    def _save(self) -> None:
        """Save history to disk."""
        self._data["last_updated"] = datetime.now().isoformat()
        self.history_file.write_text(json.dumps(self._data, indent=2))
    
    def get_all_urls(self) -> list[str]:
        """Get all previously discovered URLs (across all verticals)."""
        return self._data.get("urls", [])
    
    def get_urls_for_vertical(self, vertical: str) -> list[str]:
        """Get URLs discovered for a specific vertical."""
        return self._data.get("by_vertical", {}).get(vertical, [])
    
    def is_discovered(self, url: str) -> bool:
        """Check if a URL has been discovered."""
        # Normalize URL
        url = url.rstrip("/").replace("www.", "")
        return any(
            url in discovered or discovered in url
            for discovered in self._data.get("urls", [])
        )
    
    def add_urls(self, vertical: str, urls: list[str]) -> None:
        """Add discovered URLs to history without full prospect records.
        
        Used by standalone discovery scripts that only track URLs.
        """
        # Update global URL list
        existing_urls = set(self._data.get("urls", []))
        existing_urls.update(urls)
        self._data["urls"] = list(existing_urls)[-500:]
        
        # Update per-vertical list
        if vertical not in self._data.get("by_vertical", {}):
            self._data.setdefault("by_vertical", {})[vertical] = []
        
        vertical_urls = set(self._data["by_vertical"][vertical])
        vertical_urls.update(urls)
        self._data["by_vertical"][vertical] = list(vertical_urls)[-200:]
        
        self._save()

    def add_prospects(self, vertical: str, prospects: list[Prospect]) -> None:
        """Add discovered prospects to history."""
        # Update URL lists
        urls = [p.url for p in prospects]
        
        # Global dedup list
        existing_urls = set(self._data.get("urls", []))
        existing_urls.update(urls)
        self._data["urls"] = list(existing_urls)[-500:]  # Keep last 500
        
        # Per-vertical list
        if vertical not in self._data.get("by_vertical", {}):
            self._data.setdefault("by_vertical", {})[vertical] = []
        
        vertical_urls = set(self._data["by_vertical"][vertical])
        vertical_urls.update(urls)
        self._data["by_vertical"][vertical] = list(vertical_urls)[-200:]
        
        # Store full prospect records
        prospect_records = self._data.get("prospects", [])
        for p in prospects:
            record = p.to_dict()
            record["_history_added"] = datetime.now().isoformat()
            prospect_records.append(record)
        
        # Keep last 1000 prospects
        self._data["prospects"] = prospect_records[-1000:]
        
        self._save()
    
    def get_recent_prospects(self, limit: int = 50) -> list[dict]:
        """Get most recently discovered prospects."""
        prospects = self._data.get("prospects", [])
        return prospects[-limit:]
    
    def get_stats(self) -> dict:
        """Get discovery statistics."""
        return {
            "total_urls": len(self._data.get("urls", [])),
            "by_vertical": {
                v: len(urls) for v, urls in self._data.get("by_vertical", {}).items()
            },
            "total_prospects": len(self._data.get("prospects", [])),
            "last_updated": self._data.get("last_updated"),
        }
