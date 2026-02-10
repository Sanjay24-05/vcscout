# VC Scout 🔍

**Autonomous Market Validator with Multi-Agent Debate Analysis**

A multi-agent system that takes a startup idea, validates the input, performs deep market research, analyzes competitors, and runs a **Bull vs Bear debate** to provide a balanced, data-backed investment verdict. Features input validation to save API costs on invalid inputs.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [Screenshots](#-screenshots)
- [Tech Stack](#️-tech-stack)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Example Output](#-example-output)
- [Configuration](#️-configuration)
- [Project Structure](#-project-structure)
- [Testing](#-testing)
- [Problems Faced & Solutions](#-problems-faced--solutions)
- [Future Enhancements](#-future-enhancements)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

---

## ✨ Key Features

- **🛡️ Input Validation Gate**: Rejects gibberish, off-topic, or overly vague inputs early to save API costs
- **⚔️ Bull vs Bear Debate**: Multi-agent debate panel (Bull, Bear, Synthesizer) provides balanced analysis instead of single-pass evaluation
- **💡 Collaborative Pivoting**: Debate can suggest refined pivots based on market realities — single pass, no loops
- **📊 Two Report Types**:
  - **Investment Memo** 🟢 — For ideas that pass validation
  - **Market Reality Report** 🔴 — Constructive analysis explaining why the market is challenging
- **💾 Persistent State**: Uses Neon Postgres to save research history for async workflows
- **🧠 Transparent AI Reasoning**: "Thought Trace" shows debate transcript and decision reasoning
- **⚡ Rate-Limited API Calls**: Built-in rate limiting to respect API quotas
- **🔄 Legacy Pivot Mode**: Optional autonomous pivoting loop (configurable via `ENABLE_DEBATE_MODE`)

## 📸 Screenshots
### Input Validation
![Screenshot 1](docs/screenshots/Screenshot%202026-02-08%20151209.png)
### Successful Investment Memo Generation
![Screenshot 2](docs/screenshots/Screenshot%202026-02-08%20151241.png)

![Screenshot 3](docs/screenshots/Screenshot%202026-02-08%20151254.png)

![Screenshot 4](docs/screenshots/Screenshot%202026-02-08%20151306.png)

![Screenshot 5](docs/screenshots/Screenshot%202026-02-08%20151315.png)
### Successful Market Analysis Report Generation
![Screenshot 6](docs/screenshots/Screenshot%202026-02-08%20151413.png)

![Screenshot 7](docs/screenshots/Screenshot%202026-02-08%20151423.png)

![Screenshot 8](docs/screenshots/Screenshot%202026-02-08%20151435.png)

![Screenshot 9](docs/screenshots/Screenshot%202026-02-08%20151450.png)

![Screenshot 10](docs/screenshots/Screenshot%202026-02-08%20151504.png)
### Current Bottleneck Due To Free Tier LLMs
![Screenshot 11](docs/screenshots/Screenshot%202026-02-08%20151529.png)

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Orchestration | **LangGraph** | Cyclic state machine with conditional logic |
| Multi-Agent | **pyautogen** | Agent conversation framework for debate simulation |
| LLM | **Groq (Llama 3.3 70B)** | Fast inference, generous free tier (30 RPM) |
| Database | **Neon Postgres** | Serverless, persistent state with connection pooling |
| Search | **DuckDuckGo** | Free web search API |
| Scraper | **Crawl4AI** | HTML → Markdown conversion |
| Frontend | **Streamlit** | Real-time UI with execution timeline |
| Validation | **Pydantic 2** | Structured LLM outputs with validators |

> **Note**: Originally built with Gemini 1.5 Flash, but switched to Groq due to rate limiting issues with Gemini's free tier (15 RPM vs Groq's 30 RPM).

### AutoGen Integration

The debate panel uses **pyautogen** (Microsoft's multi-agent framework) configured with Groq as the LLM backend:

```python
# src/llm/autogen_config.py
config_list = [{
    "model": "llama-3.3-70b-versatile",
    "api_key": settings.groq_api_key,
    "base_url": "https://api.groq.com/openai/v1",
}]
```

Three agents participate in the debate:
- **Bull Agent** 🐂 — Argues the investment thesis, highlights opportunities
- **Bear Agent** 🐻 — Plays devil's advocate, identifies risks and challenges  
- **Synthesizer Agent** ⚖️ — Moderates debate, produces balanced conclusion with potential pivot

## 🚀 Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/vcscout.git
cd vcscout
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get API Keys

1. **Groq API Key** (Required): https://console.groq.com/keys
2. **Neon Database** (Required): https://neon.tech - Create a free project

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required
GROQ_API_KEY=gsk_your_groq_api_key
NEON_DATABASE_URL=postgresql://user:pass@host/db?sslmode=require

# Optional - Model selection
LLM_MODEL=llama-3.3-70b-versatile  # or qwen-qwq-32b, mixtral-8x7b-32768

# Optional - Tuning
PIVOT_THRESHOLD=5          # Score threshold for pivoting (1-10)
MAX_PIVOT_ATTEMPTS=3       # Max pivots before giving up
```

### 4. Run

```bash
.venv/bin/streamlit run app.py
```

Or if venv is activated:
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## 📐 Architecture

### Debate Mode (Default)

```
                    ┌─────────────────────────────────────────────────────┐
                    │              LangGraph Orchestrator                  │
                    │                                                      │
START ──► Input_Validator ──►[valid?]──► Market_Researcher ──► Competitor_Analyst
                              │                                      │
                              │                                      ▼
                        [invalid]                            Debate_Panel (⚔️)
                              │                              Bull │ Bear │ Synth
                              ▼                                      │
                        handle_invalid                               ▼
                              │                                   Writer ──► END
                              ▼
                             END
```

### Legacy Pivot Mode (Optional)

```
                    ┌─────────────────────────────────────────┐
                    │         LangGraph Orchestrator          │
                    │                                         │
START ──► Market_Researcher ──► Competitor_Analyst ──► Devils_Advocate
                    ▲                                         │
                    │                                         ▼
                    │                               [Conditional Edge]
                    │                              /      |       \
                    │                         pivot  success   failure
                    │                           │       │         │
                    └──── apply_pivot ◄─────────┘       ▼         ▼
                                                      Writer ──► END
```

### Agent Descriptions

| Agent | Role | Output |
|-------|------|--------|
| **Input Validator** 🛡️ | Validates input is a real startup idea (rejects gibberish/off-topic) | `InputValidationResult` |
| **Market Researcher** 🔍 | Analyzes TAM, SAM, SOM, growth trends, market maturity | `MarketResearchResult` |
| **Competitor Analyst** 📊 | Identifies competitors, saturation level, barriers to entry | `CompetitorAnalysisResult` |
| **Debate Panel** ⚔️ | Bull argues investment thesis, Bear argues risks, Synthesizer concludes | `DebateResult` |
| **Devil's Advocate** 😈 | (Legacy mode) Scores viability (1-10), identifies risks, suggests pivots | `DevilsAdvocateFeedback` |
| **Writer** ✍️ | Generates Investment Memo or Market Reality Report | Markdown report |

### Conditional Edge Logic

**Debate Mode:**
```python
# After Input Validation
if is_valid:
    return "valid"      # → Proceed to research
else:
    return "invalid"    # → Handle rejection, end

# After Debate Panel
if score > PASS_THRESHOLD:
    return "write_success"      # → Investment Memo
else:
    return "write_failure"      # → Market Reality Report
```

**Legacy Pivot Mode:**
```python
if score > PIVOT_THRESHOLD:
    return "write_success"      # → Investment Memo
elif pivot_attempts < MAX_PIVOT_ATTEMPTS:
    return "pivot"              # → Apply pivot, loop back
else:
    return "write_failure"      # → Market Reality Report
```

## 📊 Example Output

### Debate Mode Flow

```
Input: "AI-powered legal assistant for small businesses"

🛡️ Input Validation: ✅ Valid startup idea

🔍 Market Research: $50B TAM, 12% CAGR
📊 Competitor Analysis: 15 competitors, medium saturation

⚔️ Debate Panel (5 rounds):
├── 🐂 Bull: "Large underserved SMB market, AI adoption accelerating..."
├── 🐻 Bear: "Crowded space with LegalZoom, Rocket Lawyer, compliance risks..."
└── ⚖️ Synthesizer: "Viable with vertical focus. Suggest: immigration law niche."

Final Score: 7/10 ✅
└── Result: Investment Memo generated with debate insights
```

### Input Validation Rejection

```
Input: "asdfghjkl qwerty"

🛡️ Input Validation: ❌ Rejected
└── Reason: "Input appears to be random text without business context"
└── No API calls wasted on research!
```

### Legacy Pivot Flow

```
Input: "A to-do app"

Pivot #0 (Score: 4/10)
├── Before: A to-do app
├── After: Task management tool for freelancers integrating with Upwork/Fiverr
└── Reason: Market oversaturated, need differentiation

Pivot #1 (Score: 6/10) ✅
└── Result: Investment Memo generated
```

### Generated Reports

- **🟢 Investment Memo**: Executive summary, market opportunity, competitive advantage, debate highlights (bull/bear cases), risks & mitigations, investment recommendation
- **🔴 Market Reality Report**: Why the market is challenging, lessons learned, alternative directions

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | Groq API key (required) |
| `NEON_DATABASE_URL` | - | Postgres connection string (required) |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model: llama-3.3-70b, qwen-qwq-32b, mixtral-8x7b |
| `ENABLE_DEBATE_MODE` | `true` | Use debate panel instead of pivot loop |
| `DEBATE_MAX_ROUNDS` | `6` | Number of debate rounds (Bull → Bear → Bull → ...) |
| `PASS_THRESHOLD` | `5` | Score threshold for Investment Memo (debate mode) |
| `MAX_PIVOT_ATTEMPTS` | `3` | Maximum pivots before Market Reality Report (legacy) |
| `PIVOT_THRESHOLD` | `5` | Score threshold for triggering pivots (legacy) |
| `AGENT_TIMEOUT` | `60` | Timeout per agent in seconds |
| `SEARCH_NUM_RESULTS` | `10` | DuckDuckGo results per query |
| `MAX_COMPETITORS_TO_SCRAPE` | `5` | Max competitor sites to scrape |

## 📁 Project Structure

```
vcscout/
├── app.py                     # Streamlit entry point
├── requirements.txt           # Dependencies
├── .env.example               # Environment template
├── docs/
│   └── screenshots/           # Screenshot placeholders
├── src/
│   ├── config.py              # Pydantic settings
│   ├── runner.py              # Job execution logic
│   ├── graph/
│   │   ├── state.py           # AgentState TypedDict + Pydantic models
│   │   ├── nodes.py           # Node wrappers with persistence
│   │   ├── edges.py           # Conditional edge logic (validation, debate, pivot)
│   │   └── builder.py         # LangGraph compilation (debate + legacy modes)
│   ├── agents/
│   │   ├── input_validator.py # 🛡️ Input validation gate
│   │   ├── debate_panel.py    # ⚔️ Bull vs Bear vs Synthesizer debate
│   │   ├── market_researcher.py
│   │   ├── competitor_analyst.py
│   │   ├── devils_advocate.py # Legacy pivot mode
│   │   └── writer.py
│   ├── tools/
│   │   ├── search.py          # DuckDuckGo wrapper
│   │   └── scraper.py         # Crawl4AI wrapper
│   ├── db/
│   │   ├── connection.py      # Async SQLAlchemy with SSL handling
│   │   ├── models.py          # ORM models
│   │   └── repository.py      # CRUD operations
│   ├── llm/
│   │   ├── gemini.py          # Gemini client (legacy)
│   │   ├── groq_client.py     # Groq client (active)
│   │   └── autogen_config.py  # AutoGen/Groq config (reserved)
│   └── ui/
│       └── __init__.py        # Streamlit helpers (status badges, debate transcript)
└── tests/
    ├── conftest.py            # Test fixtures
    └── test_graph.py          # Unit tests (23 tests)
```

## 🧪 Testing

```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run with coverage
.venv/bin/python -m pytest tests/ -v --cov=src
```

## 🐛 Problems Faced & Solutions

### 1. Gemini API Rate Limiting (ResourceExhausted)
**Problem**: Gemini's free tier has strict rate limits (15 RPM), causing failures with 4+ agent calls per analysis.

**Solution**: Switched to Groq which offers 30 RPM on free tier. Added rate limiter class to space out requests.

### 2. Asyncpg SSL Connection Errors
**Problem**: Neon requires SSL but `asyncpg` had issues parsing URL query parameters.

**Solution**: Strip query params from URL and pass SSL config via `connect_args`:
```python
connect_args={"ssl": "require"}
```

### 3. Streamlit Event Loop Conflicts
**Problem**: Streamlit's `asyncio.run()` creates new event loops, causing "attached to different loop" errors with SQLAlchemy async engine.

**Solution**: Track event loop ID and reset engine when loop changes:
```python
if id(asyncio.get_running_loop()) != _loop_id:
    _reset_engine()
```

### 4. LLM Validation Errors
**Problem**: LLMs sometimes return scores outside 1-10 range or non-standard verdicts, causing Pydantic validation failures.

**Solution**: Added `@field_validator` decorators to clamp scores and normalize verdicts:
```python
@field_validator('score', mode='before')
def clamp_score(cls, v):
    return max(1, min(10, int(v)))
```

### 5. NoneType Errors in State Access
**Problem**: `state.get("key", {})` returns `None` if key exists with `None` value.

**Solution**: Use `state.get("key") or {}` pattern throughout codebase.

### 6. datetime.utcnow() Deprecation
**Problem**: Python 3.12 deprecates `datetime.utcnow()`.

**Solution**: Migrated to `datetime.now(timezone.utc)`.

## 🚀 Future Enhancements

### Completed ✅
- [x] **Input Validation Gate**: Reject invalid/off-topic inputs before expensive API calls
- [x] **Multi-Agent Debate Panel**: Bull vs Bear debate for balanced analysis
- [x] **Collaborative Pivoting**: Single-pass pivot suggestions from debate synthesis

### Short-term
- [ ] **Session History View**: Browse and compare past analyses
- [ ] **PDF Export**: Download reports as formatted PDFs
- [ ] **Real Competitor Scraping**: Use Crawl4AI to fetch actual competitor data
- [ ] **Caching Layer**: Cache search results to reduce API calls

### Medium-term
- [ ] **Webhook/API Endpoint**: Programmatic access for integrations
- [ ] **Multi-Pivot Visualization**: Graph showing the full pivot decision tree
- [ ] **Confidence Intervals**: Show uncertainty in market size estimates
- [ ] **User Authentication**: Secure multi-user access with Neon Auth

### Long-term
- [ ] **Fine-tuned Models**: Custom model for market analysis
- [ ] **Real-time Data Sources**: Integrate Crunchbase, PitchBook APIs
- [ ] **Collaborative Mode**: Team annotations and comments on reports
- [ ] **Automated Follow-ups**: Monitor market changes and re-analyze

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) for the state machine framework  
- [AutoGen](https://github.com/microsoft/autogen) for multi-agent collaboration and orchestration  
- [Groq](https://groq.com/) for fast, free LLM inference  
- [Neon](https://neon.tech/) for serverless Postgres  
- [Streamlit](https://streamlit.io/) for rapid UI development  
