# mini-claude

Build your own Claude Code in plain Python.

No pip install, no framework: only the standard library. It works with **any
provider that speaks the OpenAI chat format**. Groq, OpenRouter, NVIDIA and a
local Ollama are already set up, and adding another is one line.

```
you ──> agent.py ──> gateway.py ──> Groq / OpenRouter / NVIDIA / Ollama
           │
           ├── tools.py       read, write, edit, list files, run commands (sandboxed)
           ├── guardrails.py  deny-list + permission modes (ask / auto / read-only)
           ├── hooks.py       your own code before / after every tool call
           ├── memory.py      MEMORY.md, loaded into the prompt at startup
           ├── context.py     summarise old turns when the conversation gets too big
           └── skills.py      skills/*/SKILL.md, loaded only when a task needs one
```

## Setup (2 minutes)

```bash
cd mini-claude
cp .env.example .env        # then paste in your API key
python agent.py
```

Python 3.10+ only. Free keys:
[Groq](https://console.groq.com/keys) ·
[OpenRouter](https://openrouter.ai/keys) ·
[NVIDIA](https://build.nvidia.com).

**Fully local, no key:** install [Ollama](https://ollama.com), run
`ollama pull qwen3:4b`, and set `PROVIDER=ollama`. The model must support
tool calling (qwen3, llama3.1 and gpt-oss do; gemma3 doesn't).

The agent works inside `mini-claude/workspace/`, which is created on first run.
Point it at another folder with `WORKDIR=/path/to/project`.

## Using it

```text
> create fib.py that prints the first 10 Fibonacci numbers, then run it
> /status                     which provider, model and mode are active
> /help                       list every command
> /provider nvidia            switch provider, the conversation carries on
> /model openai/gpt-oss-20b   pick a model
> /mode auto                  ask | auto | read-only
> /provider ollama            run on your own machine
> /context                    how full the context budget is
> /compact                    summarise old turns now
> /skills                     list skills (add your own in skills/NAME/SKILL.md)
> /code-review fib.py         run a skill yourself
> exit
```

To run one task and exit: `python agent.py "add a test for fib.py"`

## What real Claude Code adds

| mini-claude | Claude Code |
|---|---|
| Path jail + no secrets in env | OS-level sandbox (filesystem + network isolation) |
| `ask / auto / read-only` | Permission modes plus allow/deny rules per tool and command |
| Python-function hooks | Shell-command hooks in settings.json (PreToolUse, PostToolUse, Stop…) |
| `MEMORY.md` | CLAUDE.md files at user, project and folder level |
| Summary of old turns + trimmed tool outputs (`context.py`) | Auto-compaction + `/compact` |
| `skills/*/SKILL.md` + `use_skill` tool | Skills, plus bundled scripts and plugins |
| One agent | Sub-agents, MCP servers, streaming, prompt caching, resumable sessions |

## Notes

- Use a model that supports **tool calling**. The cloud defaults (gpt-oss) and
  the Ollama default (qwen3:4b) do. If a provider renames a model, set `MODEL=` in `.env`.
- The sandbox is for teaching, not for running untrusted code. A command can
  still read files outside the folder with an absolute path. Real isolation
  means a container or the OS sandbox Claude Code uses.
- Rate limits: on a 429 the gateway waits as long as the provider's
  `Retry-After` header says (at most 60s) and tells you it's waiting.
- Every tool call is logged to `audit.log` next to the code, outside the
  agent's reach.
