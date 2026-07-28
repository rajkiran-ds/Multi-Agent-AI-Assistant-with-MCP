# 🤖 Multi-Agent Assistant — LangGraph + MCP + Streamlit

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-4B32C3?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

A multi-agent system built with **LangGraph** where a router agent dispatches
natural-language requests to one of three specialist agents. Each agent calls
a real tool exposed by an **MCP (Model Context Protocol)** server over stdio,
rather than calling any logic directly — the LLM only *decides*, the MCP
server *acts*. The whole thing is wrapped in a **Streamlit** UI and is
deployable straight from GitHub to Streamlit Community Cloud.

```
                     ┌───────────────┐
   user query ─────► │  router node  │  (LLM decides which agent)
                     └───────┬───────┘
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      knowledge_node   calculator_node   email_node
              │              │              │
              ▼              ▼              ▼
        ┌─────────────────────────────────────────┐
        │        MCP server (mcp_server.py)        │
        │  get_knowledge   calculate   send_email  │
        └─────────────────────────────────────────┘
                                            │
                                            ▼
                                   real SMTP email sent
```

## Features

- **Real email sending, bring-your-own account** — the `send_email` MCP tool
  sends an actual email over SMTP. Anyone using the app can type their own
  Gmail address + App Password into the UI to send from their own account;
  nothing is stored server-side. If left blank, it falls back to a fixed
  `EMAIL_ADDRESS` / `EMAIL_APP_PASSWORD` set by the deployer (optional).
  This is the piece the original prototype only simulated.
- **Multi-agent routing** — a LangGraph `StateGraph` with a conditional entry
  point lets the LLM pick the right specialist agent per request.
- **Tools live behind MCP, not in-process** — the agents never call Python
  functions directly. They call MCP tools over a stdio transport, exactly
  the same way they would call tools on a remote MCP server. This keeps the
  "brain" (LangGraph + LLM) and the "hands" (tool execution) cleanly
  separated, which is the whole point of MCP.
- **Swappable LLM backend** — `LLM_PROVIDER` env var switches between Groq
  (cloud, free tier, works on Streamlit Cloud), OpenAI, or a local Ollama
  model, with no code changes.
- **Safe calculator** — arithmetic is evaluated with a restricted AST walker
  instead of Python's `eval()`.
- **Streamlit UI** with a live sidebar showing which env vars are configured
  — useful both for local debugging and for demoing the project.

## Tech stack

Python · LangGraph · LangChain · MCP (`mcp`, `langchain-mcp-adapters`) ·
Streamlit · Groq / OpenAI / Ollama · smtplib (SMTP)

## Project structure

```
.
├── app.py                 # Streamlit UI (entry point)
├── agent_graph.py          # LangGraph workflow: router + 3 agent nodes
├── mcp_server.py            # MCP tool server (get_knowledge, calculate, send_email)
├── config.py                # LLM provider selection + secrets loading
├── requirements.txt
├── .env.example
├── notebooks/                # original prototyping notebook (kept for reference)
└── README.md
```

## Setup (local)

**1. Clone and enter the repo**

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

**2. Create a virtual environment and install dependencies**

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure environment variables**

```bash
cp .env.example .env
```

Then edit `.env`:

- Get a free **Groq API key**: https://console.groq.com/keys
- Set `GROQ_API_KEY` in `.env`.
- For email, set `EMAIL_ADDRESS` to a Gmail address and `EMAIL_APP_PASSWORD`
  to an **App Password** (not your regular Gmail password) — generate one at
  https://myaccount.google.com/apppasswords (requires 2‑Step Verification to
  be turned on for the account).

**4. Run it**

```bash
streamlit run app.py
```

Streamlit will open at `http://localhost:8501`.

### Try it

- `What is MCP?` → routed to the knowledge agent
- `What is 128 * 47 + 9?` → routed to the calculator agent
- `Email jane@example.com to confirm tomorrow's 3pm meeting` → routed to the
  email agent, which drafts a subject/body and actually sends it via SMTP

## Deploying to GitHub + Streamlit Community Cloud

**1. Push to GitHub**

```bash
git init
git add .
git commit -m "Multi-agent MCP assistant with LangGraph and Streamlit"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

`.env` is already in `.gitignore` — double check it did **not** get
committed (`git status` should not show it).

**2. Deploy on Streamlit Community Cloud**

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **"New app"**, pick your repo/branch, and set the main file to
   `app.py`.
3. Before (or after) deploying, open **"Advanced settings" → Secrets** and
   paste in the same key/value pairs from your `.env` file, e.g.:

   ```toml
   LLM_PROVIDER = "groq"
   GROQ_API_KEY = "your_groq_api_key_here"
   GROQ_MODEL = "llama-3.3-70b-versatile"
   EMAIL_ADDRESS = "your_email@gmail.com"
   EMAIL_APP_PASSWORD = "your_16_char_app_password"
   SMTP_SERVER = "smtp.gmail.com"
   SMTP_PORT = "465"
   ```

4. Deploy. `app.py` copies these secrets into environment variables at
   startup (`config.sync_streamlit_secrets_to_env`) so the MCP server
   subprocess — which only sees real env vars, not `st.secrets` — can read
   them too.

> **Note on Ollama:** Streamlit Community Cloud cannot run a local Ollama
> model server, so use `LLM_PROVIDER=groq` (or `openai`) for any hosted
> deployment. Ollama is only for running everything on your own machine.

## Security notes

- Never commit `.env` or `.streamlit/secrets.toml`.
- Use an **App Password** for email, never your real account password.
- The calculator tool uses a restricted AST evaluator, not `eval()`, so it
  cannot execute arbitrary code.
- The email tool validates the recipient address format before sending and
  fails closed (returns an error string) if no sender credentials are
  available (neither typed into the UI nor set as env vars).
- Sender credentials typed into the UI go straight from the Streamlit
  widgets into the MCP tool call as plain function arguments — they are
  never inserted into an LLM prompt, logged, or persisted anywhere. That
  said, the standard caveats of a "bring your own credentials" web app
  apply: only use App Passwords (never a real account password, and Gmail
  App Passwords can be revoked independently at any time), and be mindful
  that anyone with access to a public deployment's URL can use it to send
  email *from whatever account they type in* — this is intended for
  personal/demo use, not as a trusted mail-relay service for strangers.

## Possible extensions

- Add more MCP tools (web search, calendar, Slack) — the router prompt and
  graph both scale easily to more nodes.
- Stream intermediate agent/tool steps to the UI instead of only the final
  result.
- Add automated tests for `agent_graph.py` using a mocked MCP client.

## Credits

Originally prototyped in a Jupyter notebook (see `notebooks/`) using
LangGraph + `langchain-mcp-adapters` + a local Ollama model, with a
simulated (non-functional) email tool. This version replaces the simulated
tool with real SMTP sending and restructures the code for deployment.
