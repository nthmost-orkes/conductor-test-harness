# Providers & local-LLM config for agentspan testing

Keeps the API keys and local-LLM endpoints used to exercise `conductor agent` against
real providers — Claude, ChatGPT, LiteLLM routers, and local Ollama on loki/spartacus.

## Files

| File | Committed? | Purpose |
|---|---|---|
| `models.yaml` | ✅ | Catalog of test targets — logical name → agentspan `model:` string + which endpoint it needs. No secrets. |
| `secrets.env.example` | ✅ | Template for the secrets file. |
| `secrets.env` | ❌ **gitignored** | Real keys + endpoint URLs. Sourced by the start script. `chmod 600`. |

## Setup

```bash
cp providers/secrets.env.example providers/secrets.env
$EDITOR providers/secrets.env          # fill in keys + endpoints
```

`secrets.env` is git-ignored (see repo `.gitignore`) and must never be committed.
(Canonical long-term storage for these keys is `~/projects/nthmost-systems/.secrets/`;
this file is the local working copy the harness reads.)

## How it plugs in

The Conductor server dials providers from **its own** environment/config at startup
(a client shell's key means nothing to it). `scripts/start-test-server.sh` sources
`secrets.env` and launches a server wired with:

| Provider | Wired via | Source var |
|---|---|---|
| Claude (Anthropic) | env `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| ChatGPT (OpenAI) | env `OPENAI_API_KEY` | `OPENAI_API_KEY` |
| Ollama (one host) | `conductor.ai.ollama.baseURL` | `OLLAMA_BASE_URL` |
| LiteLLM router (one) | `conductor.ai.litellm.baseURL` / `.apiKey` | `LITELLM_BASE_URL` / `LITELLM_API_KEY` |

The server binds **one** ollama baseURL and **one** litellm baseURL at a time. Since the
LiteLLM routers already federate loki + spartacus (+ cloud), pointing `LITELLM_BASE_URL` at
the **spartacus** router (the superset — includes `gpt4`, `heavy/*`, `loki/*`, `local/*`)
reaches the most models through `litellm/*`. Use `OLLAMA_BASE_URL` for direct `ollama/*`
against a single host.

### loki / spartacus reachability

Endpoints work over mDNS (`*.local`), WireGuard, or Tailscale. If the server host can't
resolve `.local`, set the WG IP or Tailscale MagicDNS name in `secrets.env`
(examples are in `secrets.env.example`). Verified reachable 2026-08-10 over `.local`:
Ollama `:11434` and LiteLLM `:4000` on both loki and spartacus.

## Usage

```bash
# 1. start a server wired to all providers (downloads the jar to .run/ on first run)
scripts/start-test-server.sh --port 7010

# 2. run the provider matrix — a trivial agent per model, PASS/FAIL
CONDUCTOR_SERVER=http://localhost:7010 CLI=/path/to/conductor scripts/agent-matrix.sh

# or target specific models
CONDUCTOR_SERVER=http://localhost:7010 scripts/agent-matrix.sh litellm/gpt4 ollama/gemma3:12b

# 3. stop the server when done
scripts/stop-test-server.sh --port 7010
```

## Notes

- **ChatGPT:** verified green with a dedicated harness key (`openai/gpt-4o` → PING7).
  If you swap in a project key without `gpt-4o` access you'll get an HTTP 403 `model_not_found`
  (and the same via `litellm/gpt4`, since that router group routes to OpenAI).
- On-LAN LiteLLM routers need no auth; `LITELLM_API_KEY` is a placeholder some builds require.
- The model string is parsed by splitting on the **first** `/`, so `litellm/heavy/reasoning`
  and `ollama/llama3.1:8b` both work.
