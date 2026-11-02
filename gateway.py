"""Step 1 · The gateway: one function that can talk to any model.

Groq, OpenRouter, NVIDIA and a local Ollama all accept the same OpenAI "chat
completions" request. So switching provider changes only three things: the URL,
the API key and the model name. The rest of mini-claude calls chat() and never
knows who is answering on the other end.
"""

import json
import os
import time
import urllib.error
import urllib.request

import config

#   name           base URL                                API key variable      default model
PROVIDERS = {
    "groq":       ("https://api.groq.com/openai/v1",      "GROQ_API_KEY",       "openai/gpt-oss-120b"),
    "openrouter": ("https://openrouter.ai/api/v1",        "OPENROUTER_API_KEY", "openai/gpt-oss-20b:free"),
    "nvidia":     ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY",     "openai/gpt-oss-120b"),
    "ollama":     ("http://localhost:11434/v1",           None,                 "qwen3:4b"),  # local, no key
}


def model_name():
    return config.MODEL or PROVIDERS[config.PROVIDER][2]


def chat(messages, tools):
    """Send the whole conversation and return the model's next message."""
    base_url, key_variable, _ = PROVIDERS[config.PROVIDER]
    headers = {"Content-Type": "application/json",
               "User-Agent": "mini-claude"}  # some gateways block Python's default one
    if key_variable:  # cloud providers need a key; a local Ollama doesn't
        api_key = os.environ.get(key_variable)
        if not api_key:
            raise RuntimeError(f"set {key_variable} in your .env to use {config.PROVIDER}")
        headers["Authorization"] = f"Bearer {api_key}"

    body = {"model": model_name(), "messages": messages}
    if tools:  # some providers reject an empty tools list
        body["tools"] = tools
    request = urllib.request.Request(base_url + "/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)

    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return clean(json.load(response)["choices"][0]["message"])
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(wait_time(error, attempt))
                continue
            details = error.read().decode(errors="replace")[:300]
            if config.PROVIDER == "ollama" and error.code == 404:
                details += f" (download it first: ollama pull {model_name()})"
            raise RuntimeError(f"{config.PROVIDER} returned {error.code}: {details}")
        except urllib.error.URLError as error:  # couldn't connect at all
            hint = " (is Ollama running? try: ollama serve)" if config.PROVIDER == "ollama" else ""
            raise RuntimeError(f"can't reach {base_url}: {error.reason}{hint}")


def wait_time(error, attempt):
    """How long to wait before retrying. A rate-limited provider usually tells us
    in a Retry-After header; otherwise wait 2s, 4s, 8s, 16s."""
    try:
        seconds = float(error.headers.get("Retry-After"))
    except (TypeError, ValueError):
        seconds = 2 ** (attempt + 1)
    seconds = min(seconds, 60)
    print(f"  ({config.PROVIDER} is busy or rate-limited; retrying in {seconds:.0f}s)")
    return seconds


def clean(message):
    """Keep only the standard fields so the reply can go back into the history.

    Providers add their own extras (like "reasoning"), and another provider may
    reject them. Stripping them is what lets you switch provider mid-chat.
    """
    reply = {"role": "assistant", "content": message.get("content") or ""}
    if message.get("tool_calls"):
        reply["tool_calls"] = []
        for call in message["tool_calls"]:
            arguments = call["function"].get("arguments") or "{}"
            if not isinstance(arguments, str):  # a few providers send a dict
                arguments = json.dumps(arguments)
            reply["tool_calls"].append({
                "id": call["id"],
                "type": "function",
                "function": {"name": call["function"]["name"], "arguments": arguments},
            })
    return reply
