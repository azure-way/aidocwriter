from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Iterator, Optional, Dict, Any

try:  # Optional at import time to allow tests with FakeLLM without the SDK installed
    from openai import OpenAI, AzureOpenAI  # type: ignore
except Exception:  # pragma: no cover - only triggered when SDK missing
    OpenAI = None  # type: ignore
    AzureOpenAI = None  # type: ignore


@dataclass
class LLMMessage:
    role: str
    content: str


class LLMClient:
    """Thin wrapper over OpenAI Responses API to support streaming and model selection.

    Uses `client.responses.create/stream`, which supports reasoning models (o3) and GPT‑4.1.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        use_responses: bool = True,
    ):
        if OpenAI is None:
            raise RuntimeError(
                "openai package not installed. Install with `pip install openai` or use FakeLLM in tests."
            )
        self.use_responses = use_responses
        self.last_usage: Dict[str, Optional[int]] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        client_kwargs: dict[str, object] = {}
        if base_url and "azure.com" in base_url.lower():
            if AzureOpenAI is None:
                raise RuntimeError(
                    "AzureOpenAI client not available. Ensure openai package >= 1.42 and azure models access."
                )
            endpoint = base_url.rstrip("/")
            client_kwargs.update(
                {
                    "api_key": api_key,
                    "api_version": api_version or "2024-08-01-preview",
                    "azure_endpoint": endpoint,
                }
            )
            self.client = AzureOpenAI(**client_kwargs)
        else:
            client_kwargs.update({"api_key": api_key, "base_url": base_url})
            self.client = OpenAI(**client_kwargs)

    def _supports_sampling(self, model: str) -> bool:
        # OpenAI "smart" models (o1, o3, etc.) do not allow sampling params like temperature
        return not model.lower().startswith("o")

    def _supports_response_format(self) -> bool:
        try:
            sig = inspect.signature(self.client.responses.create)
            return "response_format" in sig.parameters
        except Exception:
            return False

    def _extract_responses_text(self, resp) -> str:
        if hasattr(resp, "output_text") and resp.output_text:
            try:
                text_val = resp.output_text
                if isinstance(text_val, str):
                    return text_val
                try:
                    return "".join(text_val)
                except Exception:
                    pass
            except Exception:
                pass
        output_blocks = getattr(resp, "output", None)
        if output_blocks:
            pieces: list[str] = []
            for block in output_blocks:
                contents = getattr(block, "content", None)
                if not contents:
                    continue
                for item in contents:
                    text = getattr(item, "text", None)
                    if text:
                        pieces.append(text)
            if pieces:
                return "".join(pieces)
        return str(resp)

    def _update_usage(self, resp: Any) -> None:
        usage = getattr(resp, "usage", None)
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None
        if usage is not None:
            if isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                total_tokens = usage.get("total_tokens")
            else:
                prompt_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
                completion_tokens = getattr(usage, "completion_tokens", None) or getattr(
                    usage, "output_tokens", None
                )
                total_tokens = getattr(usage, "total_tokens", None)
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens
        if prompt_tokens is None and completion_tokens is None and total_tokens is None:
            self.last_usage = {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }
        else:
            self.last_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }

    def chat_stream(self, model: str, messages: list[LLMMessage]) -> Iterator[str]:
        inputs = [{"role": m.role, "content": m.content} for m in messages]
        temp = 0.2 if self._supports_sampling(model) else None
        if self.use_responses:
            request_kwargs = {"model": model, "input": inputs}
            if temp is not None:
                request_kwargs["temperature"] = temp
            with self.client.responses.stream(**request_kwargs) as s:
                for event in s:
                    if event.type == "response.output_text.delta":
                        yield event.delta
                final_resp = s.get_final_response()
            self._update_usage(final_resp)
        else:
            completion_kwargs = {"model": model, "messages": inputs}
            if temp is not None:
                completion_kwargs["temperature"] = temp
            for chunk in self.client.chat.completions.create(stream=True, **completion_kwargs):
                try:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                except Exception:
                    continue
            self.last_usage = {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }

    def chat(
        self,
        model: str,
        messages: list[LLMMessage],
        response_format: Optional[dict] = None,
    ) -> str | dict:
        inputs = [{"role": m.role, "content": m.content} for m in messages]
        temp = 0.2 if self._supports_sampling(model) else None
        if self.use_responses:
            request_kwargs = {"model": model, "input": inputs}
            if temp is not None:
                request_kwargs["temperature"] = temp
            if response_format is not None and self._supports_response_format():
                request_kwargs["response_format"] = response_format
            resp = self.client.responses.create(**request_kwargs)
            self._update_usage(resp)
            if response_format is not None:
                try:
                    first_output = resp.output[0]
                    first_content = first_output.content[0]
                    return first_content.parsed if hasattr(first_content, "parsed") else json.loads(first_content.text)
                except Exception:
                    pass
            return self._extract_responses_text(resp)
        else:
            completion_kwargs = {"model": model, "messages": inputs}
            if temp is not None:
                completion_kwargs["temperature"] = temp
            resp = self.client.chat.completions.create(**completion_kwargs)
            self._update_usage(resp)
            try:
                return str(resp.choices[0].message.content or "")
            except Exception:
                pass
