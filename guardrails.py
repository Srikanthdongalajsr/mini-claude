"""Step 3 · Guardrails: should this tool call be allowed to run?

Three layers, checked in order:
  1. A deny-list of commands that are never OK, whatever the mode.
  2. Files outside the project folder: always ask you first, even in auto mode.
  3. The permission mode:
       read-only  only reading tools may run
       ask        reading is free; anything that writes or runs asks you first
       auto       everything runs (still subject to layers 1 and 2)
"""

import re

import config
import tools

SAFE_TOOLS = {"read_file", "list_files", "remember", "use_skill"}

NEVER_ALLOWED = [
    r"\brm\s+-\w*r\w*f?\s+(/|~|\*)",  # rm -rf /   rm -rf ~   rm -rf *
    r"\bsudo\b",
    r"\bmkfs\b|\bdd\s+if=",            # wiping disks
    r"\b(shutdown|reboot)\b",
    r"(curl|wget)[^|]*\|\s*(ba)?sh",   # piping the internet into a shell
    r"git\s+push\s+.*--force",
    r"\bformat\s+[a-z]:",              # Windows: format a drive
    r"\b(del|rd|rmdir)\s+/[sq]",       # Windows: recursive delete
]


def check(name, args):
    """Return None to allow the call, or a sentence explaining why it's blocked."""
    if name == "run_command":
        for pattern in NEVER_ALLOWED:
            if re.search(pattern, args.get("command", ""), re.IGNORECASE):
                return "this command is on the deny-list"

    if config.MODE == "read-only" and name not in SAFE_TOOLS:
        return "the agent is in read-only mode"

    if "path" in args and not tools.is_allowed(args["path"]):
        full = tools.resolve(args["path"])
        print(f"  {full} is outside the project folder ({config.WORKDIR}).")
        if not confirm("Would you still like the agent to access it?"):
            return "that path is outside the project folder and the user said no"
        tools.APPROVED.add(full)  # yes once = yes for the rest of this session

    if name in SAFE_TOOLS or config.MODE == "auto":
        return None
    return None if confirm(f"Allow {name}?") else "the user said no"


def confirm(question):
    return input(f"  {question} [y/N] ").strip().lower() in ("y", "yes")
