"""
Output formatters for Discord reports and CRM exports.
"""

from datetime import date
from typing import TYPE_CHECKING, Optional, List, Tuple

if TYPE_CHECKING:
    from shared.base import BaseVertical, Prospect


class DiscordFormatter:
    """Formats discovery results for Discord markdown."""
    
    @staticmethod
    def format_prospect(p: "Prospect", index: int) -> str:
        """Format a single prospect for Discord."""
        lines = [
            f"### {index}. {p.score_emoji} [{p.name}]({p.url})",
            f"**Category:** {p.category} | **Location:** {p.location}",
            f"**GEO Score:** {p.raw_score}/{p.max_score} (normalized: {p.normalized_score})",
            "",
            "**Key Gaps:**",
        ]
        
        for gap in p.geo_gaps[:3]:
            lines.append(f"• {gap}")
        
        lines.append("")
        lines.append("**Contacts:**")
        
        if p.emails:
            lines.append(f"• Email: {', '.join(p.emails[:2])}")
        if p.phones:
            lines.append(f"• Phone: {', '.join(p.phones[:2])}")
        if p.linkedin:
            lines.append(f"• LinkedIn: {p.linkedin}")
        
        if not (p.emails or p.phones or p.linkedin):
            lines.append("• No contacts found")
        
        lines.append("")
        lines.append(f"**Recommended Action:** {p.recommended_action}")
        lines.append("---")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_vertical_report(vertical: "BaseVertical", prospects: list["Prospect"]) -> str:
        """Format a full vertical report for Discord."""
        if not prospects:
            return f"_No prospects discovered for {vertical.name}_"
        
        lines = [
            f"**{vertical.icon} {vertical.name} GEO Prospects — {date.today().strftime('%B %d, %Y')}**",
            "",
            f"Found **{len(prospects)}** prospects across {len(set(p.category for p in prospects))} categories.",
            "",
            "---",
            "",
        ]
        
        for i, p in enumerate(prospects, 1):
            lines.append(DiscordFormatter.format_prospect(p, i))
        
        lines.append("")
        lines.append(f"_Scored by MadTech Growth GEO Agent · [Priority: 🔴 Hot 🟡 Warm 🟢 Cold]_")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_combined_report(
        vertical_reports: dict[str, str],
        all_prospects: list["Prospect"],
    ) -> str:
        """Format a combined multi-vertical report."""
        lines = [
            f"**🎯 Multi-Vertical GEO Discovery — {date.today().strftime('%B %d, %Y')}**",
            "",
            f"**Total Prospects:** {len(all_prospects)}",
        ]
        
        # Count by vertical
        by_vertical = {}
        for p in all_prospects:
            by_vertical[p.vertical] = by_vertical.get(p.vertical, 0) + 1
        
        for v, count in by_vertical.items():
            lines.append(f"• {v.upper()}: {count} prospects")
        
        # Hot prospects summary
        hot_prospects = [p for p in all_prospects if p.normalized_score >= 0.8]
        if hot_prospects:
            lines.append("")
            lines.append(f"**🔥 Hot Prospects ({len(hot_prospects)}):**")
            for p in hot_prospects[:5]:
                lines.append(f"• [{p.name}]({p.url}) — {p.category}")
        
        lines.append("")
        lines.append("=" * 40)
        lines.append("")
        
        # Individual vertical reports
        for vertical_key, report in vertical_reports.items():
            lines.append(report)
            lines.append("")
        
        return "\n".join(lines)


class CRMFormatter:
    """Formats prospects for CRM import (HubSpot, Airtable, etc.)."""
    
    @staticmethod
    def format_prospect(p: "Prospect") -> dict:
        """Format a prospect as CRM-ready JSON."""
        return {
            "company_name": p.name,
            "website": p.url,
            "domain": p.domain,
            "vertical": p.vertical,
            "category": p.category,
            "location": p.location,
            "revenue_indicator": p.revenue_indicator,
            "geo_score": {
                "raw": p.raw_score,
                "max": p.max_score,
                "normalized": p.normalized_score,
            },
            "priority": "hot" if p.normalized_score >= 0.8 else "warm" if p.normalized_score >= 0.5 else "cold",
            "contacts": {
                "emails": p.emails,
                "phones": p.phones,
                "linkedin": p.linkedin,
                "contact_page": p.contact_page,
            },
            "geo_analysis": {
                "gaps": p.geo_gaps,
                "strengths": p.geo_strengths,
            },
            "recommended_action": p.recommended_action,
            "discovered_at": p.discovered_at.isoformat(),
            "source_query": p.source_query,
        }
    
    @staticmethod
    def format_prospects(prospects: list["Prospect"]) -> dict:
        """Format multiple prospects as CRM-ready JSON."""
        return {
            "export_date": date.today().isoformat(),
            "total_prospects": len(prospects),
            "by_priority": {
                "hot": len([p for p in prospects if p.normalized_score >= 0.8]),
                "warm": len([p for p in prospects if 0.5 <= p.normalized_score < 0.8]),
                "cold": len([p for p in prospects if p.normalized_score < 0.5]),
            },
            "prospects": [CRMFormatter.format_prospect(p) for p in prospects],
        }
    
    @staticmethod
    def to_hubspot_csv(prospects: list["Prospect"]) -> str:
        """Generate HubSpot-compatible CSV."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Company Name", "Website", "Vertical", "Category",
            "GEO Score", "Priority", "Primary Email", "Phone",
            "LinkedIn", "Location", "Recommended Action",
        ])
        
        # Rows
        for p in prospects:
            writer.writerow([
                p.name,
                p.url,
                p.vertical,
                p.category,
                f"{p.raw_score}/{p.max_score}",
                "hot" if p.normalized_score >= 0.8 else "warm" if p.normalized_score >= 0.5 else "cold",
                p.emails[0] if p.emails else "",
                p.phones[0] if p.phones else "",
                p.linkedin,
                p.location,
                p.recommended_action,
            ])
        
        return output.getvalue()
