from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from admitpilot.config import AdmitPilotSettings, load_settings


@dataclass(slots=True)
class OpenAIChatResponse:
    content: str
    raw: dict[str, Any]


def _resolve_openai_api_key(settings: AdmitPilotSettings | None = None) -> str:
    value = (settings or load_settings()).openai_api_key.strip()
    if not value:
        raise RuntimeError("Missing OpenAI API key. Set OPENAI_API_KEY.")
    return value


def openai_available(settings: AdmitPilotSettings | None = None) -> bool:
    try:
        _resolve_openai_api_key(settings=settings)
    except RuntimeError:
        return False
    return True


def _extract_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        parts = [part.strip() for part in text.split("```") if part.strip()]
        for part in parts:
            candidate = part
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        return parsed
    raise RuntimeError("OpenAI JSON response is not an object.")


@dataclass(slots=True)
class OpenAIClient:
    settings: AdmitPilotSettings | None = None
    api_key: str = ""
    model: str = ""
    embedding_model: str = ""
    base_url: str = ""
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        effective_settings = self.settings or load_settings()
        self.settings = effective_settings
        if not self.model:
            self.model = effective_settings.openai_model
        if not self.embedding_model:
            self.embedding_model = effective_settings.openai_embedding_model
        if not self.base_url:
            self.base_url = effective_settings.openai_base_url
        if not self.api_key:
            self.api_key = effective_settings.openai_api_key
        self.timeout_seconds = effective_settings.openai_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key.strip())

    def chat(
        self, user_prompt: str, system_prompt: str | None = None, temperature: float = 0
    ) -> OpenAIChatResponse:
        return self._create_response(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format="text",
        )

    def chat_json(
        self, user_prompt: str, system_prompt: str | None = None, temperature: float = 0
    ) -> dict[str, Any]:
        response = self._create_response(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format="json_object",
        )
        return _extract_json_object(response.content)

    def embed_texts(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        api_key = self.api_key.strip() or _resolve_openai_api_key(settings=self.settings)
        url = self.base_url.rstrip("/") + "/embeddings"
        payload = {
            "model": model or self.embedding_model,
            "input": texts,
        }
        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenAI embedding request failed: HTTP {e.code} {e.reason}: {detail}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenAI embedding request failed: {e.reason}") from e
        raw = json.loads(body)
        data = raw.get("data", [])
        if not isinstance(data, list):
            raise RuntimeError("OpenAI embedding response missing data list.")
        indexed_rows: list[tuple[int, list[float]]] = []
        for item in data:
            if not isinstance(item, dict):
                raise RuntimeError("OpenAI embedding row must be an object.")
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise RuntimeError("OpenAI embedding row missing embedding list.")
            indexed_rows.append(
                (
                    int(item.get("index", len(indexed_rows))),
                    [float(value) for value in embedding],
                )
            )
        indexed_rows.sort(key=lambda row: row[0])
        return [row[1] for row in indexed_rows]

    def _create_response(
        self,
        user_prompt: str,
        system_prompt: str | None,
        temperature: float,
        response_format: str,
    ) -> OpenAIChatResponse:
        api_key = self.api_key.strip() or _resolve_openai_api_key(settings=self.settings)
        url = self.base_url.rstrip("/") + "/responses"
        input_items: list[dict[str, Any]] = []
        if system_prompt:
            input_items.append(
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                }
            )
        input_items.append(
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            }
        )
        payload = {
            "model": self.model,
            "input": input_items,
            "temperature": temperature,
            "text": {"format": {"type": response_format}},
        }
        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed: HTTP {e.code} {e.reason}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenAI request failed: {e.reason}") from e
        raw = json.loads(body)
        content = self._extract_output_text(raw)
        return OpenAIChatResponse(content=str(content), raw=raw)

    def _extract_output_text(self, raw: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in raw.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict) or content.get("type") != "output_text":
                    continue
                text = str(content.get("text", "")).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts)


def openai_chat(prompt: str) -> OpenAIChatResponse:
    return OpenAIClient().chat(user_prompt=prompt)
