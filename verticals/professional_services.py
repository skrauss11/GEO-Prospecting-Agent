"""
Professional Services vertical discovery implementation.
"""

import json
import re
from datetime import date
from typing import Optional

from shared.base import BaseVertical, Prospect
from shared.agent_runner import run_discovery_agent


class ProfessionalServicesVertical(BaseVertical):
    """Professional Services vertical: law firms, accounting, consulting, finance."""

    key = "ps"
    name = "Professional Services"
    icon = "🔍"
    max_score = 5

    def get_system_prompt(self, exclude_urls: list[str], count: int = 3) -> str:
        """Generate system prompt for PS discovery."""
        history_str = "\n".join(f"- {u}" for u in exclude_urls[-50:]) if exclude_urls else "None yet."

        return f"""\
You are a GEO (Generative Engine Optimization) prospecting agent for MadTech Growth.

YOUR TASK: Find and analyze EXACTLY {count} professional services firms in NYC metro.

CRITICAL RULES:
1. Do ONE web_search, then IMMEDIATELY pick {count} firms from those results
2. Do NOT do multiple searches - use the first result
3. For EACH firm: call analyze_site_geo, then extract_contacts
4. After {count} firms have extract_contacts called, call final_answer with JSON

WORKFLOW (MANDATORY):
- Turn 1: web_search
- Subsequent turns: analyze_site_geo + extract_contacts for each firm (2 turns each)
- Final turn: final_answer

STATE TRACKING:
- Count extract_contacts calls
- When count == {count}, call final_answer immediately

PREVIOUSLY REPORTED (dedup - do not repeat):
{history_str}

OUTPUT FORMAT (JSON only):
{{"prospects": [{{"name": "...", "url": "...", "category": "Law Firm", "location": "Manhattan", "raw_score": 4, "geo_gaps": [...], "geo_strengths": [...], "emails": [...], "phones": [...], "linkedin": "...", "contact_page": "...", "recommended_action": "..."}}]}}
"""

    def parse_agent_output(self, output: str) -> list[Prospect]:
        """Parse LLM JSON output into Prospect objects."""
        prospects = []

        try:
            # Extract JSON from potential markdown code blocks
            if "```json" in output:
                json_str = output.split("```json")[1].split("```")[0].strip()
            elif "```" in output:
                json_str = output.split("```")[1].split("```")[0].strip()
            else:
                json_str = output.strip()

            data = json.loads(json_str)

            for p_data in data.get("prospects", []):
                prospect = Prospect(
                    name=p_data.get("name", "Unknown"),
                    url=p_data.get("url", ""),
                    vertical=self.key,
                    raw_score=p_data.get("raw_score", 3),
                    max_score=self.max_score,
                    geo_gaps=p_data.get("geo_gaps", []),
                    geo_strengths=p_data.get("geo_strengths", []),
                    emails=p_data.get("emails", []),
                    phones=p_data.get("phones", []),
                    linkedin=p_data.get("linkedin", ""),
                    contact_page=p_data.get("contact_page", ""),
                    category=p_data.get("category", "Professional Services"),
                    location=p_data.get("location", "NYC Metro"),
                    revenue_indicator=p_data.get("revenue_indicator", ""),
                    recommended_action=p_data.get("recommended_action", ""),
                    _raw_analysis=p_data,
                )
                prospects.append(prospect)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ⚠️ Failed to parse agent output: {e}")
            prospects = self._fallback_parse(output)

        return prospects

    def _fallback_parse(self, output: str) -> list[Prospect]:
        """Fallback parser for non-JSON output."""
        prospects = []
        url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`[\]]+')
        urls = url_pattern.findall(output)

        for url in urls[:3]:
            prospects.append(Prospect(
                name=url.split("/")[2].replace("www.", "").replace(".", " ").title(),
                url=url,
                vertical=self.key,
                raw_score=3,
                category="Unknown",
                geo_gaps=["Parse error — manual review needed"],
            ))

        return prospects

    def discover(
        self,
        count: int = 3,
        exclude_urls: Optional[list[str]] = None,
        test_mode: bool = False,
    ) -> list[Prospect]:
        """Run discovery for Professional Services."""
        if test_mode:
            return [
                Prospect(
                    name="Test Law Firm LLC",
                    url="https://testlawfirm.example.com",
                    vertical=self.key,
                    raw_score=5,
                    category="Law Firm",
                    location="Manhattan, NYC",
                    revenue_indicator="$25M+",
                    geo_gaps=["No JSON-LD", "No FAQ", "Blocks AI crawlers"],
                    emails=["contact@testlawfirm.example.com"],
                    recommended_action="Implement LegalService schema markup.",
                )
            ]

        exclude_urls = exclude_urls or []
        system_prompt = self.get_system_prompt(exclude_urls, count=count)
        user_prompt = (
            f"Today is {date.today().strftime('%B %d, %Y')}. "
            f"Find {count} professional services firms in NYC metro. "
            f"Do ONE web_search, pick {count} firms, analyze each, output JSON."
        )

        return run_discovery_agent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            parse_fn=self.parse_agent_output,
            exclude_urls=exclude_urls,
            count=count,
            trace_label=f"ps_{date.today().isoformat()}",
        )
