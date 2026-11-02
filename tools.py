"""Step 2 · Tools: the agent's hands, kept inside a sandbox.

A tool is just a Python function. The model never runs anything itself: it asks
for a tool by name, with arguments, and we run it. The sandbox has two rules:
  1. Every path is resolved inside WORKDIR, so "../" can never escape it.
  2. Shell commands run inside WORKDIR, with a timeout and without our API keys.
"""

import os
import subprocess

import config

MAX_OUTPUT = 10_000  # characters; a huge output would flood the model's context

# Paths outside WORKDIR that the user has said yes to (see guardrails.py).
APPROVED = set()

#sandbox
def resolve(path):
    """Turn a path (relative to WORKDIR, or absolute) into a clean absolute one."""
    return os.path.realpath(os.path.join(config.WORKDIR, path))


def is_under(full, folder):
    try:
        return os.path.commonpath([full, folder]) == folder
    except ValueError:  # e.g. a different drive on Windows
        return False


def is_allowed(path):
    """Inside the sandbox, or inside something the user approved."""
    full = resolve(path)
    return any(is_under(full, folder) for folder in [config.WORKDIR, *APPROVED])


def inside_sandbox(path):
    """The last line of defence: refuse any path that isn't allowed."""
    if not is_allowed(path):
        raise PermissionError(f"'{path}' is outside the sandbox")
    return resolve(path)

#file tools
def read_file(path):
    with open(inside_sandbox(path), encoding="utf-8", errors="replace") as f:
        return f.read()[:MAX_OUTPUT]

def write_file(path, content):
    full = inside_sandbox(path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return f"wrote {len(content)} characters to {path}"


def edit_file(path, old, new):
    """Replace one exact snippet. It must match once, so the edit is never a guess."""
    full = inside_sandbox(path)
    with open(full, encoding="utf-8") as f:
        text = f.read()
    count = text.count(old)
    if count != 1:
        return f"ERROR: that snippet appears {count} times; it must appear exactly once"
    with open(full, "w", encoding="utf-8") as f:
        f.write(text.replace(old, new))
    return f"edited {path}"


def list_files(path="."):
    root = inside_sandbox(path)
    found = []
    for folder, subfolders, files in os.walk(root):
        subfolders[:] = [d for d in subfolders if not d.startswith(".")]  # skip .git, .venv
        for name in files:
            found.append(os.path.relpath(os.path.join(folder, name), config.WORKDIR))
    return "\n".join(sorted(found)[:200]) or "(empty folder)"

# running commands
def run_command(command):
    result = subprocess.run(
        command, shell=True, cwd=config.WORKDIR, timeout=60,
        capture_output=True, text=True, errors="replace",
        env=environment_without_secrets(),
    )
    output = (result.stdout + result.stderr).strip()
    return f"exit code {result.returncode}\n{output[-MAX_OUTPUT:]}"


def environment_without_secrets():
    """A copy of our environment minus anything that looks like a credential,
    so `echo $GROQ_API_KEY` inside a command prints nothing."""
    secret_words = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    return {name: value for name, value in os.environ.items()
            if not any(word in name.upper() for word in secret_words)}


# name -> (function, what it does, {argument: what it means})
TOOLS = {
    "read_file":   (read_file, "Read a text file.",
                    {"path": "File path, relative to the project"}),
    "write_file":  (write_file, "Create a file, or overwrite it completely.",
                    {"path": "File path, relative to the project",
                     "content": "The full content of the file"}),
    "edit_file":   (edit_file, "Replace one exact snippet of text in a file.",
                    {"path": "File path, relative to the project",
                     "old": "The exact text to find (must appear once)",
                     "new": "The text to put in its place"}),
    "list_files":  (list_files, "List every file under a folder.",
                    {"path": "Folder path; use . for the project root"}),
    "run_command": (run_command, "Run a shell command in the project folder (60s limit).",
                    {"command": "The command to run"}),
}


def schemas():
    """Describe every tool in the JSON shape the OpenAI format expects."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {arg: {"type": "string", "description": meaning}
                                   for arg, meaning in arguments.items()},
                    "required": list(arguments),
                },
            },
        }
        for name, (_, description, arguments) in TOOLS.items()
    ]
