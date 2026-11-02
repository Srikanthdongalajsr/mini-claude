"""Step 8 · Skills: know-how the agent loads only when it needs it.

A skill is a folder with a SKILL.md file: a short header, then instructions.

    skills/commit-message/SKILL.md
        ---
        name: commit-message
        description: Write a git commit message for the current changes.
        ---
        1. Run `git diff` ...

Only the one-line descriptions go into the system prompt, so ten skills cost
ten lines of context. When a task matches one, the model calls `use_skill` and
the full instructions arrive as a tool result. You can also run one yourself
with /<name>.

(Claude Code does the same: skills are folders with a SKILL.md, and only their
descriptions are loaded until one is used.)
"""

import os

import config

SKILLS_DIR = os.path.join(config.HERE, "skills")


def read(path):
    """Split a SKILL.md into its header (as a dict) and its instructions."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    header, body = {}, text
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        for line in front.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip()] = value.strip()
    return header, body.strip()


def find():
    """name -> (description, path) for every skills/<folder>/SKILL.md.
    Scanned each time, so a new skill works without a restart."""
    found = {}
    if not os.path.isdir(SKILLS_DIR):
        return found
    for folder in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, folder, "SKILL.md")
        if os.path.exists(path):
            header, _ = read(path)
            found[header.get("name", folder)] = (header.get("description", ""), path)
    return found


def summary():
    """One line per skill, for the system prompt and for /skills."""
    lines = [f"- {name}: {description}" for name, (description, _) in find().items()]
    return "\n".join(lines) or "(none)"


def use_skill(name):
    """The tool: hand the model a skill's full instructions."""
    skills = find()
    if name not in skills:
        return f"ERROR: there is no skill called {name}. Skills: {', '.join(skills) or 'none'}"
    return read(skills[name][1])[1]


def task(name, request):
    """What /<name> sends: the skill's instructions, then what you asked for."""
    return f"Follow the '{name}' skill below.\n\n{use_skill(name)}\n\nRequest: {request or '(none)'}"
