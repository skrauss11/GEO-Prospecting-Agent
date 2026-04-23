# Web Research Agent

A simple agentic loop built with the Anthropic Python SDK. The agent can search the web and read pages to answer research questions.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
```

## Usage

```bash
# Pass a question as an argument
python agent.py "What are the latest developments in fusion energy?"

# Or run interactively
python agent.py
```

## How it works

1. You ask a research question
2. The agent sends it to Claude with two tools: `web_search` and `fetch_page`
3. Claude decides which tools to call, searches the web, reads pages
4. The agent executes the tool calls and feeds results back to Claude
5. Steps 3-4 repeat until Claude has enough information
6. Claude synthesizes a final answer with sources

## Adding custom tools

Add a new tool in three steps:

1. Define the schema in `TOOLS` (JSON Schema for Claude)
2. Implement the function
3. Register it in `TOOL_DISPATCH`
