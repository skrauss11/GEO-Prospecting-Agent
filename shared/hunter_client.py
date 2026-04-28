"""
Hunter.io API client for MadTech Growth lead enrichment.

Thin wrapper around the Hunter v2 REST API.  Handles domain search,
email finder, and basic response parsing.  No verification — we trust
Hunter’s confidence score at low volume.

Environment:
    HUNTER_API_KEY — your Hunter.io API key
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

import httpx

API_BASE = "https://api.hunter.io/v2"


def _api_key() -> str:
    key = os.environ.get("HUNTER_API_KEY", "")
    if not key:
        raise RuntimeError("HUNTER_API_KEY not set in environment")
    return key


@dataclass
class HunterContact:
    """Normalised contact from Hunter domain search."""

    email: str
    first_name: str = ""
    last_name: str = ""
    position: str = ""          # raw job title
    seniority: str = ""         # executive | senior | junior
    department: str = ""        # marketing | executive | finance | ...
    confidence: int = 0         # 0-100
    email_type: str = ""        # personal | generic
    linkedin: str = ""
    verification_status: str = ""  # valid | invalid | unverifiable | null
    sources: list[dict] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email.split("@")[0]

    @property
    def is_personal(self) -> bool:
        return self.email_type == "personal"

    @property
    def is_verified_or_unknown(self) -> bool:
        """Accept valid, null, or missing verification. Reject only explicit invalid."""
        return self.verification_status in ("valid", "", "null", None)


@dataclass
class HunterResult:
    """Result of a domain search with metadata."""

    domain: str
    pattern: str = ""           # e.g. "{first}"
    organization: str = ""
    contacts: list[HunterContact] = field(default_factory=list)
    credits_used: float = 0.0


class HunterClient:
    """Minimal Hunter.io API client."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or _api_key()
        self._http = httpx.Client(timeout=20)

    def domain_search(
        self,
        domain: str,
        *,
        limit: int = 10,
        seniority: Optional[str] = None,
        department: Optional[str] = None,
    ) -> HunterResult:
        """Search all contacts for a domain."""
        params = {
            "domain": domain,
            "api_key": self.api_key,
            "limit": limit,
        }
        if seniority:
            params["seniority"] = seniority
        if department:
            params["department"] = department

        resp = self._http.get(f"{API_BASE}/domain-search", params=params)
        resp.raise_for_status()
        payload = resp.json()

        data = payload.get("data", {})
        result = HunterResult(
            domain=data.get("domain", domain),
            pattern=data.get("pattern", ""),
            organization=data.get("organization", ""),
            contacts=[],
        )

        for raw in data.get("emails", []):
            ver = raw.get("verification") or {}
            result.contacts.append(
                HunterContact(
                    email=raw.get("value", ""),
                    first_name=raw.get("first_name") or "",
                    last_name=raw.get("last_name") or "",
                    position=raw.get("position") or raw.get("position_raw") or "",
                    seniority=raw.get("seniority") or "",
                    department=raw.get("department") or "",
                    confidence=raw.get("confidence", 0),
                    email_type=raw.get("type", ""),
                    linkedin=raw.get("linkedin") or "",
                    verification_status=ver.get("status") or "",
                    sources=raw.get("sources", []),
                )
            )

        # Approximate credit usage: Hunter charges ~1 credit per domain search
        result.credits_used = 1.0
        return result

    def email_finder(
        self,
        *,
        domain: str,
        first_name: str = "",
        last_name: str = "",
        full_name: str = "",
    ) -> Optional[HunterContact]:
        """Find a specific person’s email by name + domain."""
        params: dict[str, str] = {"domain": domain, "api_key": self.api_key}
        if full_name:
            params["full_name"] = full_name
        else:
            if first_name:
                params["first_name"] = first_name
            if last_name:
                params["last_name"] = last_name

        resp = self._http.get(f"{API_BASE}/email-finder", params=params)
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data")
        if not data:
            return None

        ver = data.get("verification") or {}
        return HunterContact(
            email=data.get("email", ""),
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
            position=data.get("position") or "",
            confidence=data.get("score", 0),
            linkedin=data.get("linkedin_url") or "",
            verification_status=ver.get("status") or "",
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):  # noqa: D105
        return self

    def __exit__(self, *args):  # noqa: D105
        self.close()
