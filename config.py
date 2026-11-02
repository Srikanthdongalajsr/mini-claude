"""Settings, all in one place.

Everything comes from environment variables, or from a .env file sitting next
to this one. A variable already set in your shell always wins over the file.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(path):
    """A tiny .env reader: one KEY=value per line, # starts a comment."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_dotenv(os.path.join(HERE, ".env"))

PROVIDER = os.environ.get("PROVIDER", "groq")  # groq | openrouter | nvidia | ollama
MODEL = os.environ.get("MODEL")                # empty = the provider's default
MODE = os.environ.get("MODE", "ask")           # ask | auto | read-only

# Context: once the conversation is bigger than CONTEXT_TOKENS, everything except
# the last KEEP_TURNS turns is squeezed into a summary. (A turn = one task you
# typed, plus everything the agent did for it.)
CONTEXT_TOKENS = int(os.environ.get("CONTEXT_TOKENS", "16000"))
KEEP_TURNS = max(1, int(os.environ.get("KEEP_TURNS", "3")))

# The sandbox: the agent can only touch files inside this folder.
WORKDIR = os.path.realpath(os.environ.get("WORKDIR") or os.path.join(HERE, "workspace"))
