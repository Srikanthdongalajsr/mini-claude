"""Step 5 · Memory: what the agent knows when it starts.

Short-term memory is simply the `messages` list in agent.py: the whole
conversation is sent to the model every turn.

Long-term memory is a file. Claude Code reads CLAUDE.md when it starts; we read
MEMORY.md from the project folder and put it in the system prompt. The
`remember` tool lets the agent add a line to it for next time.
"""

import os

import config


def memory_file():
    return os.path.join(config.WORKDIR, "MEMORY.md")


def load():
    if not os.path.exists(memory_file()):
        return "(nothing yet)"
    with open(memory_file(), encoding="utf-8") as f:
        return f.read()


def remember(note):
    with open(memory_file(), "a", encoding="utf-8") as f:
        f.write(f"- {note.strip()}\n")
    return "saved to MEMORY.md"
