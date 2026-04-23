"""
Professional Services vertical discovery implementation.
"""

import json
import os
from datetime import date
from typing import Optional

from openai import OpenAI

from shared.base import BaseVertical, Prospect
from tools import TOOL_SCHEMAS, TOOL_DISPATCH

# Add final_answer tool for hard stop
FINAL_ANSWER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "final_answer",
        "description": "Output the final JSON report when you have analyzed exactly 3 firms",
        "parameters": {
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "description": "The complete JSON report with all 3 firms analyzed"
                }
            },
            "required": ["report"]
        }
    }
}


class ProfessionalServicesVertical(BaseVertical):
    """Professional Services vertical: law firms, accounting, consulting, finance."""
    
    key = "ps"
    name = "Professional Services"
    icon = "🔍"
    max_score = 5
    
    # Nous API config
    NOUS_API_KEY = os.environ.get("NOUS_API_KEY", "")
    NOUS_BASE_URL = os.environ.get("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1")
    DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "moonshotai/kimi-k2.6")
    
    def __init__(self):
        self.client = OpenAI(base_url=self.NOUS_BASE_URL, api_key=self.NOUS_API_KEY)
    
    def get_system_prompt(self, exclude_urls: list[str]) -> str:
        """Generate system prompt for PS discovery."""
        history_str = "\n".join(f"- {u}" for u in exclude_urls[-50:]) if exclude_urls else "None yet."
        
        return f"""\
You are a GEO (Generative Engine Optimization) prospecting agent for MadTech Growth.

YOUR TASK: Find and analyze EXACTLY 5 professional services firms in NYC metro.

CRITICAL RULES:
1. Do ONE web_search, then IMMEDIATELY pick 5 firms from those results
2. Do NOT do multiple searches - use the first result
3. For EACH firm: call analyze_site_geo, then extract_contacts
4. After 5 firms have extract_contacts called, call final_answer with JSON

WORKFLOW (MANDATORY):
- Turn 1: web_search
- Turn 2-11: analyze_site_geo + extract_contacts for firms 1-5 (2 turns each)
- Turn 12: final_answer

STATE TRACKING:
- Count extract_contacts calls
- When count == 5, call final_answer immediately

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
        import re
        
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
        
        # Build prompt
        system_prompt = self.get_system_prompt(exclude_urls)
        user_prompt = (
            f"Today is {date.today().strftime('%B %d, %Y')}. "
            f"Find {count} professional services firms in NYC metro. "
            f"Do ONE web_search, pick 3 firms, analyze each, output JSON."
        )
        
        # Combine tools
        all_tools = TOOL_SCHEMAS + [FINAL_ANSWER_SCHEMA]
        
        # Run agent
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        print(f"  [Running agent with tools...]", flush=True)
        
        firms_analyzed = 0
        tool_call_count = 0
        
        for turn in range(12):
            print(f"    [turn {turn + 1}] firms={firms_analyzed}/3 tools={tool_call_count}", flush=True)
            
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                max_tokens=8096,
                messages=messages,
                tools=all_tools,
            )
            
            assistant_msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            
            if finish_reason == "tool_calls":
                tool_calls = assistant_msg.tool_calls
                tool_call_count += len(tool_calls)
                
                # Check for final_answer
                for tc in tool_calls:
                    if tc.function.name == "final_answer":
                        args = json.loads(tc.function.arguments)
                        output = args.get("report", "")
                        prospects = self.parse_agent_output(output)
                        filtered = [p for p in prospects if not any(ex in p.url or p.url in ex for ex in exclude_urls)]
                        return filtered[:count]
                
                # Add assistant message with model_dump for Kimi 2.6 reasoning_content
                assistant_dict = assistant_msg.model_dump()
                assistant_dict = {k: v for k, v in assistant_dict.items() if v is not None}
                messages.append(assistant_dict)
                
                # Execute tools
                for tc in tool_calls:
                    handler = TOOL_DISPATCH.get(tc.function.name)
                    if handler:
                        result = handler(json.loads(tc.function.arguments))
                        tool_content = json.dumps(result) if isinstance(result, dict) else str(result)
                    else:
                        tool_content = f"Unknown tool: {tc.function.name}"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_content,
                    })
                    
                    # Count firms analyzed
                    if tc.function.name == "extract_contacts":
                        firms_analyzed += 1
                        print(f"      [Firm {firms_analyzed}/5 analyzed]", flush=True)
                
                # HARD STOP: 5 firms analyzed
                if firms_analyzed >= 5:
                    print(f"    [!] 5 firms analyzed, forcing final_answer...", flush=True)
                    messages.append({
                        "role": "user",
                        "content": "You have analyzed 5 firms. Call final_answer now with your complete JSON report."
                    })
                    continue
                
                # HARD STOP: max tool calls
                if tool_call_count >= 10:
                    print(f"    [!] Max tool calls ({tool_call_count}), forcing completion...", flush=True)
                    messages.append({
                        "role": "user",
                        "content": "STOP. Call final_answer with your JSON report on the firms analyzed so far."
                    })
                    continue
            
            else:
                # Agent finished without final_answer
                output = assistant_msg.content or ""
                prospects = self.parse_agent_output(output)
                filtered = [p for p in prospects if not any(ex in p.url or p.url in ex for ex in exclude_urls)]
                return filtered[:count]
        
        return []
