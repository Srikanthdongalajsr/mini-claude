"""Step 7 · Context: keeping the conversation small enough to send.

Every call sends the whole conversation, and it grows with every tool result.
Left alone it hits the model's context limit (or a free tier's tokens-per-minute
limit). So we keep the recent past word for word and squeeze the older past:

  between tasks   compact()      the last KEEP_TURNS turns stay as they are;
                                 everything older becomes one short summary
  during a task   trim_results() shorten old tool outputs, the bulkiest part

(Claude Code does the same: it auto-compacts when the context fills up, and you
can run /compact yourself.)
"""

import json

import config
import gateway

SUMMARY_PROMPT = """Summarise this conversation between a user and a coding agent.
Keep what's needed to carry on: the user's goals, decisions made, files created or
changed (with names), commands run and their results, and anything left unfinished.
Use short bullet points."""


def estimate_tokens(messages):
    """A rough count: about 4 characters per token. Good enough for a budget."""
    return len(json.dumps(messages)) // 4


def split_turns(messages):
    """Split the history (after the system prompt) into turns. Each turn starts
    with a user message, so a tool call and its result always stay together."""
    turns = []
    for message in messages[1:]:
        if message["role"] == "user" or not turns:
            turns.append([])
        turns[-1].append(message)
    return turns


def compact(messages, force=False):
    """Summarise everything older than the last KEEP_TURNS turns, if we're over budget."""
    if not force and estimate_tokens(messages) <= config.CONTEXT_TOKENS:
        return
    turns = split_turns(messages)
    old, recent = turns[:-config.KEEP_TURNS], turns[-config.KEEP_TURNS:]
    if not old:
        print("  (nothing old enough to compact)")
        return

    before = estimate_tokens(messages)
    summary = summarise([m for turn in old for m in turn])
    # A user/assistant pair keeps the roles alternating, which every provider accepts.
    messages[1:] = [
        {"role": "user", "content": f"[Summary of our earlier conversation]\n{summary}"},
        {"role": "assistant", "content": "Got it, I'll keep that in mind."},
        *[m for turn in recent for m in turn],
    ]
    print(f"  (compacted {len(old)} old turns: ~{before:,} -> ~{estimate_tokens(messages):,} tokens)")


def summarise(old_messages):
    """Ask the model to summarise. If that fails, fall back to a plain note."""
    lines = []
    for m in old_messages:
        text = m.get("content") or ""
        for call in m.get("tool_calls", []):
            text += f" [called {call['function']['name']} {call['function']['arguments'][:200]}]"
        lines.append(f"{m['role']}: {text[:2000]}")
    try:
        reply = gateway.chat([{"role": "system", "content": SUMMARY_PROMPT},
                              {"role": "user", "content": "\n".join(lines)}], [])
        return reply["content"]
    except Exception as error:
        return f"(the earlier conversation was dropped; summarising failed: {error})"


def trim_results(messages, keep_last=4, limit=1000):
    """If a long task pushes us over budget, shorten all but the newest tool outputs.
    Only the text changes, never the number of messages, so nothing breaks."""
    if estimate_tokens(messages) <= config.CONTEXT_TOKENS:
        return
    for message in messages[:-keep_last]:
        if message["role"] == "tool" and len(message["content"]) > limit:
            message["content"] = message["content"][:limit] + "\n...(trimmed to save context)"
