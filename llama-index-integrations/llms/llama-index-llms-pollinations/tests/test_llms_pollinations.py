import os

import pytest
from llama_index.core.base.llms.base import BaseLLM
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.pollinations import Pollinations
from llama_index.llms.pollinations.base import (
    DEFAULT_API_BASE,
    DEFAULT_MODEL,
    is_function_calling_model,
)

# Pollinations needs no signup; an API key is optional.
api_key = os.environ.get("POLLINATIONS_API_KEY", "")


def test_llm_class():
    names_of_base_classes = [b.__name__ for b in Pollinations.__mro__]
    assert BaseLLM.__name__ in names_of_base_classes
    assert OpenAILike.__name__ in names_of_base_classes


def test_class_name():
    assert Pollinations.class_name() == "Pollinations"


def test_defaults():
    llm = Pollinations()
    assert llm.model == DEFAULT_MODEL
    assert llm.api_base == DEFAULT_API_BASE
    assert llm.is_chat_model is True
    # A placeholder key is set so the client can be constructed without signup.
    assert llm.api_key


def test_is_function_calling_model():
    assert is_function_calling_model("openai") is True
    assert is_function_calling_model("openai-large") is True
    assert is_function_calling_model("mistral") is False


def test_metadata_function_calling():
    assert Pollinations(model="openai").metadata.is_function_calling_model is True
    assert Pollinations(model="mistral").metadata.is_function_calling_model is False


def test_referrer_forwarded():
    llm = Pollinations(referrer="MyApp")
    assert llm.additional_kwargs.get("extra_body", {}).get("referrer") == "MyApp"

    llm_no_ref = Pollinations()
    assert "extra_body" not in llm_no_ref.additional_kwargs


@pytest.mark.skipif(not api_key, reason="No Pollinations API key set")
def test_completion():
    llm = Pollinations()
    response = llm.complete("who are you")
    assert response


@pytest.mark.skipif(not api_key, reason="No Pollinations API key set")
@pytest.mark.asyncio
async def test_async_completion():
    llm = Pollinations()
    response = await llm.acomplete("who are you")
    assert response


@pytest.mark.skipif(not api_key, reason="No Pollinations API key set")
def test_stream_complete():
    llm = Pollinations()
    responses = list(llm.stream_complete("who are you"))
    assert len(responses) > 0
