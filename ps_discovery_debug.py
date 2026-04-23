#!/usr/bin/env python3
"""
Debug version of ps_discovery.py with verbose logging
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from tools import TOOL_SCHEMAS, TOOL_DISPATCH

load_dotenv(override=True)

NOUS_API_KEY = os.environ.get("NOUS_API_KEY", "")
NOUS_BASE_URL = os.environ.get("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "moonshotai/kimi-k2.6")

HISTORY_FILE = Path(__file__).parent / "ps_discovery_history.json"

SYSTEM_PROMPT = """\
You are a GEO (Generative Engine Optimization) prospecting agent for MadTech Growth.

YOUR TASK: Find and analyze EXACTLY 3 professional services firms in NYC metro.

CRITICAL RULES:
1. Do ONE web_search, then IMMEDIATELY pick 3 firms from those results
2. Do NOT do multiple searches - use the first result
3. For EACH firm: call analyze_site_geo, then extract_contacts
4. After 3 firms have extract_contacts called, output final report

WORKFLOW (MANDATORY):
- Turn 1: web_search
- Turn 2-7: analyze_site_geo + extract_contacts for firm 1, 2, 3 (2 turns each)
- Turn 8: final_answer

STATE TRACKING:
- firms_analyzed = count of extract_contacts calls completed
- When firms_analyzed == 3, call final_answer immediately

AVAILABLE TOOLS:
- web_search: Search for firms (USE ONCE ONLY)
- analyze_site_geo: Check AI visibility
- extract_contacts: Get contact info
- final_answer: Output final report

OUTPUT FORMAT:
**Professional Services GEO Prospects — {date}**

### 1. [Company Name](URL)
**Score:** X/5 | **Category:** Law Firm/Accounting/etc.
**Gaps:** bullet list
**Contacts:** email, LinkedIn
"""

# Add final_answer tool
FINAL_ANSWER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "final_answer",
        "description": "Output the final report when you have analyzed exactly 3 firms",
        "parameters": {
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "description": "The complete markdown report with all 3 firms analyzed"
                }
            },
            "required": ["report"]
        }
    }
}


def run_agent_debug(user_query: str, max_turns: int = 10) -> str:
    """Debug version with verbose logging."""
    client = OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)
    
    # Combine tools
    all_tools = TOOL_SCHEMAS + [FINAL_ANSWER_SCHEMA]
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]
    
    tool_call_count = 0
    firms_analyzed = 0
    
    for turn in range(max_turns):
        print(f"\n[Turn {turn + 1}/{max_turns}]", flush=True)
        print(f"  State: {firms_analyzed}/3 firms analyzed, {tool_call_count} tool calls", flush=True)
        
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            messages=messages,
            tools=all_tools,
        )
        
        assistant_msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        
        print(f"  Finish reason: {finish_reason}", flush=True)
        
        if finish_reason == "tool_calls":
            tool_calls = assistant_msg.tool_calls
            print(f"  Tool calls: {len(tool_calls)}", flush=True)
            
            for tc in tool_calls:
                print(f"    - {tc.function.name}", flush=True)
                tool_call_count += 1
            
            # Check for final_answer
            for tc in tool_calls:
                if tc.function.name == "final_answer":
                    args = json.loads(tc.function.arguments)
                    return args.get("report", "No report provided")
            
            # Add assistant message - use model_dump to get all fields including reasoning_content
            assistant_dict = assistant_msg.model_dump()
            assistant_dict = {k: v for k, v in assistant_dict.items() if v is not None}
            messages.append(assistant_dict)
            
            # Execute tools and add results
            for tc in tool_calls:
                handler = TOOL_DISPATCH.get(tc.function.name)
                if handler:
                    try:
                        args = json.loads(tc.function.arguments)
                        result = handler(args)
                        result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                        if len(result_str) > 500:
                            result_str = result_str[:500] + "... [truncated]"
                    except Exception as e:
                        result_str = f"Error: {e}"
                else:
                    result_str = f"Unknown tool: {tc.function.name}"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })
                print(f"    Result length: {len(result_str)} chars", flush=True)
                
                # Count firms analyzed
                if tc.function.name == "extract_contacts":
                    firms_analyzed += 1
                    print(f"    [Firm {firms_analyzed}/3 analyzed]", flush=True)
            
            # HARD STOP: if we've analyzed 3 firms, force completion
            if firms_analyzed >= 3:
                print(f"\n  [!] 3 firms analyzed, forcing final_answer...", flush=True)
                messages.append({
                    "role": "user", 
                    "content": "You have analyzed 3 firms. Call final_answer now with your complete markdown report."
                })
                continue
            
            # HARD STOP: max tool calls
            if tool_call_count >= 8:
                print(f"\n  [!] Max tool calls ({tool_call_count}), forcing completion...", flush=True)
                messages.append({
                    "role": "user", 
                    "content": "STOP. Call final_answer with your report on the firms you've analyzed so far."
                })
                continue
        
        elif finish_reason == "stop":
            content = assistant_msg.content or ""
            print(f"\n  [Complete] Output length: {len(content)} chars", flush=True)
            return content
        
        else:
            print(f"  [!] Unexpected finish reason: {finish_reason}", flush=True)
            return assistant_msg.content or ""
    
    return "Agent reached maximum turns."


if __name__ == "__main__":
    print("=" * 60)
    print("DEBUG: Professional Services GEO Discovery")
    print(f"Date: {date.today().strftime('%B %d, %Y')}")
    print(f"Model: {DEFAULT_MODEL}")
    print("=" * 60)
    
    prompt = (
        f"Today is {date.today().strftime('%B %d, %Y')}. "
        "Do ONE web_search for 'NYC law firms'. "
        "Pick 3 actual law firm websites from the first search result. "
        "Analyze each with analyze_site_geo then extract_contacts. "
        "Do NOT search again. Output markdown report."
    )
    
    report = run_agent_debug(prompt)
    
    print("\n" + "=" * 60)
    print("FINAL REPORT:")
    print("=" * 60)
    print(report)
