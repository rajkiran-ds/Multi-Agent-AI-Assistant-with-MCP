"""
MCP tool server for the multi-agent assistant.

Exposes three tools over stdio transport:
  - get_knowledge : small built-in knowledge base lookup
  - calculate     : safe arithmetic evaluation (AST-based, no eval())
  - send_email    : sends a REAL email via SMTP

Run standalone for a quick manual check:
    python mcp_server.py
(it will just sit waiting on stdio - that's expected, it's meant to be
launched by an MCP client, not run interactively)
"""

import ast
import operator
import os
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agent-tools")


# --------------------------------------------------------------------------
# Knowledge tool
# --------------------------------------------------------------------------

@mcp.tool()
def get_knowledge(query: str) -> str:
    """
    Answer a general knowledge question using a small built-in knowledge base.
    """
    knowledge_base = {
        "python": "Python is a popular high-level programming language known for readability.",
        "langgraph": "LangGraph is a library for building stateful, multi-agent applications with LLMs.",
        "ai": "AI (Artificial Intelligence) refers to machines simulating human intelligence.",
        "mcp": "MCP (Model Context Protocol) is an open standard that lets AI applications connect to external tools and data sources in a consistent way.",
        "streamlit": "Streamlit is a Python framework for turning data scripts into shareable web apps.",
        "smtp": "SMTP (Simple Mail Transfer Protocol) is the standard protocol used to send email over the internet.",
    }

    query_lower = query.lower()
    for key, value in knowledge_base.items():
        if key in query_lower:
            return value

    return "Sorry, I don't have information on that topic yet."


# --------------------------------------------------------------------------
# Calculator tool (safe - no eval())
# --------------------------------------------------------------------------

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed.")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported or unsafe expression.")


@mcp.tool()
def calculate(expression: str) -> str:
    """
    Evaluate a basic arithmetic expression containing numbers and
    + - * / % ( ). Uses a restricted AST evaluator (no eval()) so it
    cannot execute arbitrary code.
    """
    clean_expr = re.sub(r"[^0-9+\-*/().% ]", "", expression)

    if not clean_expr.strip():
        return "Could not calculate that expression."

    try:
        tree = ast.parse(clean_expr, mode="eval")
        result = _safe_eval(tree)
        return f"The answer is {result}"
    except ZeroDivisionError:
        return "Could not calculate that expression: division by zero."
    except Exception:
        return "Could not calculate that expression."


# --------------------------------------------------------------------------
# Email tool - sends a REAL email via SMTP
# --------------------------------------------------------------------------

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@mcp.tool()
def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str = "",
    from_password: str = "",
) -> str:
    """
    Send a real email via SMTP.

    Sender credentials can be supplied two ways:
      1. Passed directly as from_email / from_password (e.g. typed into the
         Streamlit UI by whoever is using the app - lets each user send from
         their own address).
      2. Falls back to the EMAIL_ADDRESS / EMAIL_APP_PASSWORD environment
         variables if from_email / from_password are not provided (useful
         for a personal deployment with one fixed sender).

    SMTP_SERVER and SMTP_PORT env vars control the server (default: Gmail).
    """
    sender = from_email.strip() if from_email else os.getenv("EMAIL_ADDRESS", "")
    password = from_password.strip() if from_password else os.getenv("EMAIL_APP_PASSWORD", "")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))

    if not sender or not password:
        return (
            "Email not sent: no sender credentials available. Enter your "
            "email + app password in the UI, or set EMAIL_ADDRESS / "
            "EMAIL_APP_PASSWORD in your .env file / Streamlit secrets."
        )

    if not to or not _EMAIL_REGEX.match(to.strip()):
        return f"Email not sent: '{to}' is not a valid recipient email address."

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject or "(no subject)"
    msg.attach(MIMEText(body or "", "plain"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, to, msg.as_string())
        return f"Email sent successfully to {to} with subject '{subject}'."
    except smtplib.SMTPAuthenticationError:
        return (
            "Email not sent: SMTP authentication failed. Double-check "
            "EMAIL_ADDRESS and EMAIL_APP_PASSWORD (Gmail requires an App "
            "Password, not your normal login password)."
        )
    except Exception as exc:  # noqa: BLE001 - surface any SMTP error to the caller
        return f"Email not sent due to an error: {exc}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
