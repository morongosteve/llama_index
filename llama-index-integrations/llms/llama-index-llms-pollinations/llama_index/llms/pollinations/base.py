from typing import Any, Dict, Optional

from llama_index.core.base.llms.generic_utils import get_from_param_or_env
from llama_index.llms.openai_like import OpenAILike

DEFAULT_API_BASE = "https://text.pollinations.ai/openai"
DEFAULT_MODEL = "openai"

# Pollinations text models that expose OpenAI-compatible function calling / tools.
# Pollinations proxies a number of OpenAI models behind friendly aliases; the
# ``openai`` family supports tool use. New aliases can be discovered through the
# ``https://text.pollinations.ai/models`` endpoint.
FUNCTION_CALLING_MODELS = {
    "openai",
    "openai-large",
    "openai-reasoning",
    "openai-fast",
}


def is_function_calling_model(model: str) -> bool:
    """Return ``True`` if the given Pollinations model supports tool/function calling."""
    return any(name in model for name in FUNCTION_CALLING_MODELS)


class Pollinations(OpenAILike):
    """
    Pollinations.AI LLM.

    Pollinations.AI is an open, free, no-signup GenAI platform. Its text API
    exposes an OpenAI-compatible chat completions endpoint at
    ``https://text.pollinations.ai/openai`` supporting chat, vision (image
    input), function calling and streaming.

    Because the API requires no signup, an API key is optional. A placeholder
    key is used by default so the underlying OpenAI client can be constructed.

    Examples:
        `pip install llama-index-llms-pollinations`

        ```python
        from llama_index.llms.pollinations import Pollinations

        llm = Pollinations(model="openai")
        response = llm.complete("Hello, who are you?")
        print(response)
        ```

    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        is_chat_model: bool = True,
        referrer: Optional[str] = None,
        additional_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        additional_kwargs = additional_kwargs or {}
        # Pollinations recommends sending a referrer to identify your app and
        # to potentially qualify for different rate limits. It is forwarded as
        # an extra body parameter on each request when provided.
        referrer = get_from_param_or_env(
            "referrer", referrer, "POLLINATIONS_REFERRER", ""
        )
        if referrer:
            # ``referrer`` is a Pollinations-specific field, so it must be sent
            # through ``extra_body`` rather than as a top-level argument that the
            # OpenAI client would reject.
            extra_body = additional_kwargs.setdefault("extra_body", {})
            extra_body.setdefault("referrer", referrer)

        api_base = get_from_param_or_env(
            "api_base", api_base, "POLLINATIONS_API_BASE", DEFAULT_API_BASE
        )
        # No signup is required, so default to a placeholder key. A real key can
        # still be supplied for verified referrers / enhanced access.
        api_key = get_from_param_or_env(
            "api_key", api_key, "POLLINATIONS_API_KEY", "pollinations"
        )

        super().__init__(
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=temperature,
            max_tokens=max_tokens,
            is_chat_model=is_chat_model,
            is_function_calling_model=is_function_calling_model(model),
            additional_kwargs=additional_kwargs,
            **kwargs,
        )

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "Pollinations"
