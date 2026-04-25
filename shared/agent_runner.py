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
from typing import Callable, Optional

from openai import OpenAI

from shared.base import Prospect
from shared.config import NOUS_API_KEY, NOUS_BASE_URL, DEFAULT_MODEL
from tools import TOOL_SCHEMAS, TOOL_DISPATCH

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

    client = OpenAI(base_url=NOUS_BASE_URL, api_key=NOUS_API_KEY)
    all_tools = TOOL_SCHEMAS + [FINAL_ANSWER_SCHEMA]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    firms_analyzed = 0
    tool_call_count = 0

    for turn in range(max_turns):
        print(f"    [turn {turn + 1}] firms={firms_analyzed}/{count} tools={tool_call_count}", flush=True)

        response = client.chat.completions.create(
            model=model,
            max_tokens=8096,
            messages=messages,
            tools=all_tools,
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
                    return _filter_and_dedup(prospects, exclude_urls, count)

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
            return _filter_and_dedup(prospects, exclude_urls, count)

    # Max turns exhausted
    print("    [!] Max turns reached, returning empty.", flush=True)
    return []


def _filter_and_dedup(
    prospects: list[Prospect],
    exclude_urls: list[str],
    count: int,
) -> list[Prospect]:
    """Filter out excluded URLs and limit to `count` prospects."""
    filtered = [
        p for p in prospects
        if not any(ex in p.url or p.url in ex for ex in exclude_urls)
    ]
    return filtered[:count]
