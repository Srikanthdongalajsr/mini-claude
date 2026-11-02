"""Step 4 · Hooks: your own code that runs before and after every tool call.

Guardrails are the agent's built-in rules. Hooks are *your* rules, added without
touching the agent loop. A "before_tool" hook can block a call by returning a
reason; an "after_tool" hook sees the result (good for logs, formatters, alerts).

(Claude Code does the same with shell commands configured in settings.json,
on events like PreToolUse and PostToolUse.)
"""

import json
import os
import time

import config

HOOKS = {"before_tool": [], "after_tool": []}


def hook(event):
    """Decorator that registers a function for an event."""
    def register(function):
        HOOKS[event].append(function)
        return function
    return register


def run_before(name, args):
    for function in HOOKS["before_tool"]:
        reason = function(name, args)
        if reason:
            return reason
    return None


def run_after(name, args, result):
    for function in HOOKS["after_tool"]:
        function(name, args, result)


# ---- Two example hooks. Write your own the same way. ----

@hook("before_tool")
def protect_secrets(name, args):
    """Never let the agent read or write a .env file."""
    if any(".env" in str(value) for value in args.values()):
        return "a hook protects .env files"


@hook("after_tool")
def audit_log(name, args, result):
    """Keep a record of every tool call. The log lives outside the sandbox,
    so the agent can't edit its own history."""
    entry = {"time": time.strftime("%H:%M:%S"), "tool": name, "args": args,
             "result": str(result)[:200]}
    with open(os.path.join(config.HERE, "audit.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
