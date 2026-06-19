# LlamaIndex Llms Integration: Pollinations.AI

[Pollinations.AI](https://pollinations.ai) is an open, free, no-signup GenAI
platform. Its text API exposes an OpenAI-compatible chat completions endpoint,
so it plugs directly into LlamaIndex as an LLM with support for chat,
completion, streaming, vision (image input) and function calling.

### Installation

```bash
%pip install llama-index-llms-pollinations
```

### Basic usage

No API key is required — Pollinations needs no signup.

```python
from llama_index.llms.pollinations import Pollinations

llm = Pollinations(model="openai")

# Completion
response = llm.complete("Who are you?")
print(response)

# Chat
from llama_index.core.llms import ChatMessage

messages = [ChatMessage(role="user", content="Who are you?")]
print(llm.chat(messages))
```

### Streaming

```python
llm = Pollinations(model="openai")

for chunk in llm.stream_complete("Tell me a short story"):
    print(chunk.delta, end="")
```

### Function calling

```python
from datetime import datetime
from llama_index.core.tools import FunctionTool
from llama_index.llms.pollinations import Pollinations


def get_current_time() -> dict:
    """Get the current time."""
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


llm = Pollinations(model="openai")
tool = FunctionTool.from_defaults(fn=get_current_time)
response = llm.predict_and_call([tool], "What is the current time?")
print(response)
```

### Referrer

Pollinations recommends sending a `referrer` to identify your application and
to potentially qualify for different rate limits. You can pass it directly or
via the `POLLINATIONS_REFERRER` environment variable:

```python
llm = Pollinations(model="openai", referrer="MyCoolApp")
```

### Configuration

| Parameter  | Environment variable     | Default                                  |
| ---------- | ------------------------ | ---------------------------------------- |
| `model`    | —                        | `openai`                                 |
| `api_base` | `POLLINATIONS_API_BASE`  | `https://text.pollinations.ai/openai`    |
| `api_key`  | `POLLINATIONS_API_KEY`   | `pollinations` (placeholder, optional)   |
| `referrer` | `POLLINATIONS_REFERRER`  | _(unset)_                                |

### Documentation

- Pollinations API Docs: https://github.com/pollinations/pollinations/blob/master/APIDOCS.md
- Available text models: https://text.pollinations.ai/models
