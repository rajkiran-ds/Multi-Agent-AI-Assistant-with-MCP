"""
Multi-agent LangGraph workflow.

A router node uses the LLM to decide which specialist agent should handle
the query, then that agent calls the corresponding tool on the MCP server
(mcp_server.py) over stdio.

    router --> knowledge_node  --> get_knowledge  MCP tool
           --> calculator_node --> calculate      MCP tool
           --> email_node      --> send_email     MCP tool (real SMTP send)
"""

import asyncio
import os
import re
import sys
from typing import Optional, TypedDict

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, StateGraph

from config import get_llm

MCP_SERVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


class AgentState(TypedDict):
    query: str
    result: str
    recipient: Optional[str]
    sender_email: Optional[str]
    sender_password: Optional[str]
    agent_used: Optional[str]


def _extract_text(tool_result) -> str:
    """Convert an MCP tool result (list of content blocks) into a plain string."""
    if isinstance(tool_result, list):
        return " ".join(
            block.get("text", "") for block in tool_result if isinstance(block, dict)
        )
    return str(tool_result)


async def build_app():
    """Spins up the MCP client (which launches mcp_server.py as a subprocess),
    discovers its tools, and compiles the LangGraph workflow."""
    llm = get_llm()

    client = MultiServerMCPClient(
        {
            "agent_tools": {
                "command": sys.executable,
                "args": [MCP_SERVER_PATH],
                "transport": "stdio",
                "env": dict(os.environ),
            }
        }
    )

    tools = await client.get_tools()
    tools_by_name = {tool.name: tool for tool in tools}

    knowledge_tool = tools_by_name["get_knowledge"]
    calculator_tool = tools_by_name["calculate"]
    email_tool = tools_by_name["send_email"]

    async def router(state: AgentState):
        query = state["query"]
        prompt = f"""
You are a router for a multi-agent system. Decide which single agent
should handle the user's query.

Agents:
- calculator_node for math calculations / arithmetic
- email_node for drafting or sending emails/messages
- knowledge_node for general knowledge questions

Query: "{query}"

Respond with ONLY one word, exactly one of:
calculator_node, email_node, knowledge_node
"""
        response = await llm.ainvoke(prompt)
        decision = response.content.strip().lower()

        if "calculator" in decision:
            return "calculator_node"
        elif "email" in decision:
            return "email_node"
        return "knowledge_node"

    async def knowledge_node(state: AgentState):
        result = await knowledge_tool.ainvoke({"query": state["query"]})
        state["result"] = _extract_text(result)
        state["agent_used"] = "knowledge_node"
        return state

    async def calculator_node(state: AgentState):
        query = state["query"]
        prompt = f"""
Extract only the arithmetic expression from this text, using digits
and the symbols + - * / ( ) only. Return ONLY the expression,
nothing else.

Text: {query}
"""
        response = await llm.ainvoke(prompt)
        expression = response.content.strip()

        result = await calculator_tool.ainvoke({"expression": expression})
        state["result"] = _extract_text(result)
        state["agent_used"] = "calculator_node"
        return state

    async def email_node(state: AgentState):
        query = state["query"]
        prompt = f"""
Draft a short, professional email based on this request.

Request: "{query}"

Respond in exactly this format:
Subject: <subject>
Body: <body>
"""
        response = await llm.ainvoke(prompt)
        content = response.content

        subject_match = re.search(r"Subject:\s*(.*)", content)
        body_match = re.search(r"Body:\s*(.*)", content, re.DOTALL)

        subject = subject_match.group(1).strip() if subject_match else "Message from Multi-Agent System"
        body = body_match.group(1).strip() if body_match else content.strip()

        # Prefer an email address explicitly typed in the recipient field;
        # fall back to one mentioned inside the query text itself.
        recipient = (state.get("recipient") or "").strip()
        if not recipient:
            found = _EMAIL_REGEX.search(query)
            if found:
                recipient = found.group(0)

        if not recipient:
            state["result"] = (
                "Email not sent: no recipient address was provided. "
                "Type one in the 'Recipient email' field or include it in your request."
            )
            state["agent_used"] = "email_node"
            return state

        result = await email_tool.ainvoke(
            {
                "to": recipient,
                "subject": subject,
                "body": body,
                "from_email": state.get("sender_email") or "",
                "from_password": state.get("sender_password") or "",
            }
        )
        state["result"] = _extract_text(result)
        state["agent_used"] = "email_node"
        return state

    workflow = StateGraph(AgentState)
    workflow.add_node("knowledge_node", knowledge_node)
    workflow.add_node("calculator_node", calculator_node)
    workflow.add_node("email_node", email_node)

    workflow.set_conditional_entry_point(
        router,
        {
            "knowledge_node": "knowledge_node",
            "calculator_node": "calculator_node",
            "email_node": "email_node",
        },
    )

    workflow.add_edge("knowledge_node", END)
    workflow.add_edge("calculator_node", END)
    workflow.add_edge("email_node", END)

    return workflow.compile()


async def run_query_async(
    query: str,
    recipient: str = "",
    sender_email: str = "",
    sender_password: str = "",
) -> dict:
    app = await build_app()
    return await app.ainvoke(
        {
            "query": query,
            "result": "",
            "recipient": recipient,
            "sender_email": sender_email,
            "sender_password": sender_password,
            "agent_used": "",
        }
    )


def run_query(
    query: str,
    recipient: str = "",
    sender_email: str = "",
    sender_password: str = "",
) -> dict:
    """Synchronous entry point - safe to call from Streamlit."""
    return asyncio.run(run_query_async(query, recipient, sender_email, sender_password))