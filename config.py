"""
Configuration helpers: reads settings from Streamlit secrets (when running
under Streamlit / deployed on Streamlit Cloud) or from environment variables
/ a local .env file (when running scripts directly).
"""

import os

try:
    import streamlit as st

    _HAS_STREAMLIT = True
except ImportError:  # config.py may be imported outside of Streamlit (e.g. tests)
    _HAS_STREAMLIT = False

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _get(key: str, default=None):
    if _HAS_STREAMLIT:
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
    return os.getenv(key, default)


def sync_streamlit_secrets_to_env() -> None:
    """
    The MCP server runs as a separate subprocess and only inherits real
    environment variables (not st.secrets). Call this once at app startup
    so that anything set in Streamlit Cloud's "Secrets" panel is also
    visible to that subprocess.
    """
    if not _HAS_STREAMLIT:
        return
    try:
        for key, value in st.secrets.items():
            os.environ.setdefault(key, str(value))
    except Exception:
        pass


def get_llm():
    """
    Returns a LangChain chat model based on the LLM_PROVIDER setting.
    Supported: "groq" (default, cloud, free tier), "openai", "ollama" (local).
    """
    provider = (_get("LLM_PROVIDER", "groq") or "groq").lower()

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=_get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0,
            api_key=_get("GROQ_API_KEY"),
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=_get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=_get("OPENAI_API_KEY"),
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=_get("OLLAMA_MODEL", "llama3.1"),
            temperature=0,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Use one of: groq, openai, ollama."
    )
