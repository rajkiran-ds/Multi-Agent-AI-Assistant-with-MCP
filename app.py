import os

import streamlit as st

from agent_graph import run_query
from config import sync_streamlit_secrets_to_env

sync_streamlit_secrets_to_env()

st.set_page_config(page_title="Multi-Agent MCP Assistant", page_icon="🤖", layout="centered")

st.title("🤖 Multi-Agent Assistant")
st.caption(
    "A LangGraph router dispatches your request to a Knowledge, Calculator, "
    "or Email agent — each backed by a real tool exposed over the Model "
    "Context Protocol (MCP)."
)

# --------------------------------------------------------------------------
# Sidebar: live configuration status (nice for demos / debugging)
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration status")

    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    st.write(f"**LLM provider:** `{provider}`")

    key_by_provider = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}
    needed_key = key_by_provider.get(provider)
    if needed_key:
        st.write(f"**{needed_key}:** {'✅ set' if os.getenv(needed_key) else '❌ missing'}")
    else:
        st.write("**Ollama:** requires a local Ollama server running")

    default_email_ready = bool(os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_APP_PASSWORD"))
    st.write(
        f"**Default email sender configured:** "
        f"{'✅ (fallback if you leave the fields below blank)' if default_email_ready else '❌ none — enter your own below'}"
    )

    st.divider()
    st.markdown("### Available agents")
    st.markdown(
        "- 📚 **Knowledge agent** — general Q&A\n"
        "- 🧮 **Calculator agent** — arithmetic\n"
        "- 📧 **Email agent** — sends a real email via SMTP"
    )
    st.divider()
    st.caption("See README.md for setup instructions.")

# --------------------------------------------------------------------------
# Sender credentials (bring-your-own email) - only needed for email requests
# --------------------------------------------------------------------------
with st.expander("📧 Send from your own email (optional, needed for email requests)"):
    st.caption(
        "Enter the Gmail address you want to send from and its **App "
        "Password** (not your normal Gmail password — generate one at "
        "[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), "
        "requires 2-Step Verification). Nothing here is stored — it's only "
        "used for this request."
    )
    sender_email = st.text_input("Your email address", key="sender_email")
    sender_password = st.text_input(
        "Your app password", type="password", key="sender_password"
    )

# --------------------------------------------------------------------------
# Main interaction
# --------------------------------------------------------------------------
query = st.text_area(
    "What would you like the multi-agent system to do?",
    placeholder=(
        "e.g. \"Email jane@example.com to reschedule tomorrow's meeting\"\n"
        "or \"What is 45 * 12?\"\nor \"What is MCP?\""
    ),
    height=100,
)

recipient = st.text_input(
    "Recipient email (optional — only used for email requests, and only "
    "needed if you didn't type the address above)"
)

run_clicked = st.button("Run", type="primary")

if run_clicked:
    if not query.strip():
        st.warning("Please enter a query.")
    else:
        with st.spinner("Routing to the right agent and executing..."):
            try:
                output = run_query(query, recipient, sender_email, sender_password)
                agent_used = output.get("agent_used", "unknown")
                st.success(f"Handled by: **{agent_used}**")
                st.write(output["result"])
            except Exception as exc:  # noqa: BLE001
                st.error(f"Something went wrong: {exc}")

st.divider()
st.caption("Built with LangGraph, the Model Context Protocol (MCP), and Streamlit.")
