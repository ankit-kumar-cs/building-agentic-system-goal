# SDLC Phase-Aware Agent

A command-line agent that takes feature requests, works out which SDLC phase each one belongs to, and writes a starter document for that phase.

```
Observe -> Reason -> Act -> Adapt
```

| Step | What happens |
|---|---|
| Observe | Reads the request and recalls the previous one (short-term memory) |
| Reason | Asks the LLM for the phase and a confidence score |
| Act | Gives phase-specific advice and writes a document to `artifacts/<project>/<phase>/` |
| Adapt | If confidence is below 70%, you confirm or correct the phase. Corrections are saved and used as examples in future prompts |

## Setup

Requires Python 3.10+.

```bash
cd sdlc-phase-agent
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY`. Any OpenAI-compatible provider works; `.env.example` has settings for Groq (free), Gemini (free), Ollama (local) and OpenAI. Never commit `.env`.

## Usage

```bash
python3 main.py
```

| Option | Description |
|---|---|
| 1 | Submit a feature request (runs the full agent loop) |
| 2 | List stored requests with phase and confidence |
| 3 | Classify requests that were saved without a phase |
| 4 | Ask about the last request, e.g. "why that phase?" |
| 5 | Keyword analytics and bar chart (`data/keyword_chart.png`) |
| 6 | Agent statistics: success rate, response time, phases, recent errors |
| 7 / h | Help |
| 8 / q | Exit |

Other commands:

```bash
python3 -m unittest discover tests   # offline tests, no API key needed
python3 evaluate_prompts.py          # compare legacy vs improved prompt on data/labeled_requests.json
```

## Project layout

```
main.py                  CLI
evaluate_prompts.py      prompt accuracy comparison
src/agent.py             Observe -> Reason -> Act -> Adapt loop and memory
src/phase_detector.py    LangChain prompts, LLM call, response parsing
src/artifact_generator.py  fills templates/ with LLM-written sections
src/security.py          validation, sanitization, rate limiting, session limits
src/learning.py          stores user corrections as prompt examples
src/monitoring.py        interaction/error logs and statistics
src/storage.py           JSON persistence
src/analytics.py         pandas keyword analytics and chart
templates/               one markdown template per phase
data/                    requests, labeled samples, corrections, evaluation report
logs/                    interactions.log (JSON lines), errors.log
artifacts/               generated documents
```

## Security measures

- Description 10-500 characters, client/project up to 100; raw input over 2000 characters is rejected outright.
- Control characters and `< > { } ` $ \ |` are stripped; file names use only `[a-z0-9-]`, so input cannot write outside `artifacts/`.
- Obvious prompt-injection phrases ("ignore previous instructions", ...) are rejected.
- All LLM calls share a rate limit (`RATE_LIMIT_PER_MINUTE`, default 20).
- Per-session cap (`MAX_REQUESTS_PER_SESSION`, default 50) and duplicate-request rejection.
- API failures never crash the CLI: the request is saved as unclassified, the error is logged, and option 3 can retry it.

## Troubleshooting

| Problem | Fix |
|---|---|
| `OPENAI_API_KEY is not set` | Create `.env` from `.env.example` |
| `model_not_found` | Your provider renamed the model; update `OPENAI_MODEL` |
| `Rate limit reached` | Wait a minute or raise `RATE_LIMIT_PER_MINUTE` |
| Empty or unrecognized replies | Reasoning models need a token budget; it is set to 512 in `build_llm()` |
| Anything else | Check `logs/errors.log` or option 6 |
