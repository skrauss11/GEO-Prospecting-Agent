"""
Shared OpenAI agent loop runner for vertical discovery.

Handles the full tool-calling lifecycle:
  - final_answer tool injection
  - turn counting + hard stops
  - model_dump() for Kimi 2.6 compatibility
  - tool execution via TOOL_DISPATCH
  - JSON parsing with fallback
  - exclude-URL dedup filtering

Each vertical only provides:
  - system_prompt
  - user_prompt
  - parse_agent_output(output) -> list[Prospect]
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from openai import OpenAI

from shared.base import Prospect
from shared.config import NOUS_API_KEY, NOUS_BASE_URL, DEFAULT_MODEL, call_with_retry
from tools import TOOL_SCHEMAS, TOOL_DISPATCH


TRACES_DIR = Path(__file__).resolve().parent.parent / "data" / "traces"


def _persist_trace(label: str, messages: list, exit_reason: str, prospect_count: int) -> None:
    """Save the agent message log to data/traces/ for debugging."""
    try:
        TRACES_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_label = label.replace("/", "_").replace(" ", "_")
        path = TRACES_DIR / f"{safe_label}_{ts}.json"
        path.write_text(json.dumps({
            "label": label,
            "exit_reason": exit_reason,
            "prospect_count": prospect_count,
            "saved_at": datetime.now().isoformat(),
            "messages": messages,
        }, indent=2, default=str))
        print(f"    [trace] saved: {path}", flush=True)
    except Exception as e:
        print(f"    [trace] save failed: {e}", flush=True)


def _normalize_domain(url: str) -> str:
    """Strip scheme, www., and trailing slashes — return bare netloc lowercased."""
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc

# ── final_answer tool for clean agent termination ───────────────────────────

FINAL_ANSWER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "final_answer",
        "description": "Output the final JSON report when analysis is complete",
        "parameters": {
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "description": "The complete JSON report with all firms/brands analyzed",
                }
            },
            "required": ["report"],
        },
    },
}

# ── Defaults ──────────────────────────────────────────────────────────────────────────

DEFAULT_MAX_TURNS = 12
DEFAULT_MAX_TOOLS = 10
DEFAULT_TARGET_COUNT = 3  # firms/brands per run


def run_discovery_agent(
    system_prompt: str,
    user_prompt: str,
    parse_fn: Callable[[str], list[Prospect]],
    exclude_urls: Optional[list[str]] = None,
    count: int = DEFAULT_TARGET_COUNT,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_tool_calls: int = DEFAULT_MAX_TOOLS,
    model: str = DEFAULT_MODEL,
    trace_label: Optional[str] = None,
) -> list[Prospect]:
    """
    Run the OpenAI tool-calling agent loop for discovery.

    Args:
        system_prompt: Full system prompt for the LLM.
        user_prompt: Full user prompt for the LLM.
        parse_fn: Callable that converts agent JSON/text output into list[Prospect].
        exclude_urls: URLs to filter out from results.
        count: Number of prospects to return (after dedup filtering).
        max_turns: Hard stop after N LLM turns.
        max_tool_calls: Hard stop after N total tool calls.
        model: Model name override.

    Returns:
        Filtered + deduped list of Prospect objects (max `count`).
    """
    exclude_urls = exclude_urls or []
    trace_label = trace_label or "agent"

    client = OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)
    all_tools = TOOL_SCHEMAS + [FINAL_ANSWER_SCHEMA]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    firms_analyzed = 0
    tool_call_count = 0

    def _finish(prospects: list[Prospect], exit_reason: str) -> list[Prospect]:
        filtered = _filter_and_dedup(prospects, exclude_urls, count)
        _persist_trace(trace_label, messages, exit_reason, len(filtered))
        return filtered

    for turn in range(max_turns):
        print(f"    [turn {turn + 1}] firms={firms_analyzed}/{count} tools={tool_call_count}", flush=True)

        response = call_with_retry(
            lambda: client.chat.completions.create(
                model=model,
                max_tokens=8096,
                messages=messages,
                tools=all_tools,
            ),
            label=f"agent_runner turn={turn + 1}",
        )

        assistant_msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "tool_calls":
            tool_calls = assistant_msg.tool_calls
            tool_call_count += len(tool_calls)

            # Check for final_answer first
            for tc in tool_calls:
                if tc.function.name == "final_answer":
                    args = json.loads(tc.function.arguments)
                    output = args.get("report", "")
                    prospects = parse_fn(output)
                    return _finish(prospects, "final_answer")

            # Append assistant message (model_dump preserves reasoning_content)
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

                if tc.function.name == "extract_contacts":
                    firms_analyzed += 1
                    print(f"      [Firm {firms_analyzed}/{count} analyzed]", flush=True)

            # HARD STOP: target count reached
            if firms_analyzed >= count:
                print(f"    [!] {count} firms analyzed, forcing final_answer...", flush=True)
                messages.append({
                    "role": "user",
                    "content": f"You have analyzed {count} firms. Call final_answer now with your complete JSON report.",
                })
                continue

            # HARD STOP: max tool calls
            if tool_call_count >= max_tool_calls:
                print(f"    [!] Max tool calls ({tool_call_count}), forcing completion...", flush=True)
                messages.append({
                    "role": "user",
                    "content": "STOP. Call final_answer with your JSON report on the firms analyzed so far.",
                })
                continue

        else:
            # Agent finished without final_answer
            output = assistant_msg.content or ""
            prospects = parse_fn(output)
            return _finish(prospects, "no_final_answer")

    # Max turns exhausted
    print("    [!] Max turns reached, returning empty.", flush=True)
    return _finish([], "max_turns_exceeded")


def _filter_and_dedup(
    prospects: list[Prospect],
    exclude_urls: list[str],
    count: int,
) -> list[Prospect]:
    """Filter out excluded URLs (by normalized domain) and limit to `count` prospects."""
    excluded_domains = {_normalize_domain(ex) for ex in exclude_urls if ex}
    filtered = [
        p for p in prospects
        if _normalize_domain(p.url) not in excluded_domains
    ]
    return filtered[:count]
