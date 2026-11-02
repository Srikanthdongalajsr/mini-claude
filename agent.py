"""Step 6 · The agent loop: the part that turns a chat model into an agent.

    ask the model -> it wants tools? -> run them, show it the results -> ask again
                  -> it just answers? -> done

Everything else (gateway, tools, guardrails, hooks, memory, context) plugs in here.

Run it:   python agent.py                  (chat)
          python agent.py "make hello.py"  (one task, then exit)
"""

import json
import os
import platform
import sys

import config
import context
import gateway
import guardrails
import hooks
import memory
import skills
import tools

MAX_STEPS = 25  # a safety net so a confused model can't loop forever

SYSTEM_PROMPT = """You are mini-claude, a small coding agent.
You work in this folder: {workdir}  (operating system: {os})
For files outside it, just call the tool: the user will be asked for permission.
Look at files before you change them. After changing code, run it to check it works.
When you run something, include its actual output in your reply.
If a tool result says BLOCKED, don't try to get around it; tell the user why.
Keep your replies short.

Permission mode right now: {mode}
(read-only: only reading. ask: the user approves each write or command. auto: no approval needed.)
The mode can change during the chat, so always call the tool and let the harness
decide. Never refuse on your own because of something that was blocked earlier.

What you remember about this project (from MEMORY.md):
{memory}

Skills you can load with use_skill (load the matching one before starting a task it covers):
{skills}"""

tools.TOOLS["remember"] = (memory.remember, "Save a fact about this project for future sessions.",
                           {"note": "The fact to remember, in one sentence"})
tools.TOOLS["use_skill"] = (skills.use_skill, "Load a skill's full instructions.",
                            {"name": "The skill's name, from the list in your instructions"})


def system_prompt():
    """Rebuilt before every task, so the model always sees the current mode and memory."""
    return SYSTEM_PROMPT.format(workdir=config.WORKDIR, os=platform.system(),
                                mode=config.MODE, memory=memory.load(), skills=skills.summary())


def run_tool(call):
    """Run one tool call and return its result as text. Errors are results too:
    the model reads them and tries something else, instead of us crashing."""
    name = call["function"]["name"]
    try:
        args = json.loads(call["function"]["arguments"])
    except json.JSONDecodeError:
        return "ERROR: the arguments were not valid JSON"
    print(f"  [{name}] {json.dumps(args)[:100]}")

    if name not in tools.TOOLS:
        return f"ERROR: there is no tool called {name}"
    reason = hooks.run_before(name, args) or guardrails.check(name, args)
    if reason:
        print(f"  BLOCKED: {reason}")
        return f"BLOCKED: {reason}"

    function = tools.TOOLS[name][0]
    try:
        result = function(**args)
    except Exception as error:
        result = f"ERROR: {type(error).__name__}: {error}"
    hooks.run_after(name, args, result)
    if name == "run_command":  # show what the command printed, not just that it ran
        print("\n".join(f"    | {line}" for line in str(result).splitlines()[:20]))
    return result


def agent_loop(messages):
    """Keep calling the model until it answers without asking for a tool."""
    for _ in range(MAX_STEPS):
        context.trim_results(messages)  # a long task can outgrow the budget too
        reply = gateway.chat(messages, tools.schemas())
        messages.append(reply)

        if not reply.get("tool_calls"):
            return reply["content"]
        if reply["content"]:
            print(f"  {reply['content']}")

        for call in reply["tool_calls"]:
            result = run_tool(call)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": str(result)})
    return f"(stopped after {MAX_STEPS} steps)"


def ask(messages, task):
    """Run one task. If it fails halfway, undo it so the conversation stays valid."""
    messages[0] = {"role": "system", "content": system_prompt()}
    context.compact(messages)  # squeeze old turns if we're over the context budget
    checkpoint = len(messages)
    messages.append({"role": "user", "content": task})
    try:
        return agent_loop(messages)
    except KeyboardInterrupt:
        del messages[checkpoint:]
        return "(interrupted)"
    except Exception as error:
        del messages[checkpoint:]
        return f"(error: {error})"


MODES = ("ask", "auto", "read-only")
HELP = f"""commands:
  /status                      show provider, model and mode
  /provider {'|'.join(gateway.PROVIDERS)}
  /model NAME                  any model your provider offers
  /mode {'|'.join(MODES)}
  /context                     how full the context budget is
  /compact                     summarise old turns now
  /skills                      list skills; run one with /NAME what you want"""


def status():
    model = gateway.model_name() + ("" if config.MODEL else "  (provider default)")
    return f"provider: {config.PROVIDER}   model: {model}   mode: {config.MODE}"


def slash_command(text, messages):
    """Change settings without a restart. With no value, a command just shows
    what is selected now."""
    command, _, value = text.partition(" ")
    value = value.strip()

    if command == "/compact":
        context.compact(messages, force=True)
        return
    if command == "/context":
        print(f"~{context.estimate_tokens(messages):,} of {config.CONTEXT_TOKENS:,} tokens, "
              f"{len(context.split_turns(messages))} turns")
        return
    if command == "/help":
        print(HELP)
        return
    if command == "/skills":
        print(skills.summary())
        return
    if command[1:] in skills.find():  # /code-review app.py
        print(ask(messages, skills.task(command[1:], value)))
        return
    if command not in ("/status", "/provider", "/model", "/mode"):
        print(f"unknown command {command}\n{HELP}")
        return

    if command == "/provider" and value:
        if value not in gateway.PROVIDERS:
            print(f"unknown provider '{value}'. Choose one of: {', '.join(gateway.PROVIDERS)}")
            return
        config.PROVIDER, config.MODEL = value, None  # a new provider starts on its default model
    elif command == "/model" and value:
        config.MODEL = value
    elif command == "/mode" and value:
        if value not in MODES:
            print(f"unknown mode '{value}'. Choose one of: {', '.join(MODES)}")
            return
        config.MODE = value
    print(status())


def main():
    os.makedirs(config.WORKDIR, exist_ok=True)
    messages = [{"role": "system", "content": system_prompt()}]

    if len(sys.argv) > 1:  # one task from the command line, then exit
        print(ask(messages, " ".join(sys.argv[1:])))
        return

    print("mini-claude")
    print(status())
    print(f"sandbox: {config.WORKDIR}")
    print("Type a task, /status, or /help for commands. 'exit' quits.")
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text in ("exit", "quit"):
            break
        if text.startswith("/"):
            slash_command(text, messages)
        elif text:
            print(ask(messages, text))


if __name__ == "__main__":
    main()
