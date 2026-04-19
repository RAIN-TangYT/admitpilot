from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class QwenChatResponse:
    content: str
    raw: dict[str, Any]


def _load_dotenv_if_present() -> None:
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve_qwen_api_key() -> str:
    _load_dotenv_if_present()
    value = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or ""
    value = value.strip()
    if not value:
        raise RuntimeError("Missing Qwen API key. Set QWEN_API_KEY or DASHSCOPE_API_KEY.")
    return value


def qwen_available() -> bool:
    try:
        _resolve_qwen_api_key()
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
    raise RuntimeError("Qwen JSON response is not an object.")


@dataclass(slots=True)
class QwenClient:
    model: str = ""
    base_url: str = ""
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        _load_dotenv_if_present()
        if not self.model:
            self.model = os.getenv("QWEN_MODEL", "qwen-turbo")
        if not self.base_url:
            self.base_url = os.getenv(
                "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )

    @property
    def enabled(self) -> bool:
        return qwen_available()

    def chat(
        self, user_prompt: str, system_prompt: str | None = None, temperature: float = 0
    ) -> QwenChatResponse:
        api_key = _resolve_qwen_api_key()
        url = self.base_url.rstrip("/") + "/chat/completions"
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
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
            raise RuntimeError(f"Qwen request failed: HTTP {e.code} {e.reason}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Qwen request failed: {e.reason}") from e
        raw = json.loads(body)
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        return QwenChatResponse(content=str(content), raw=raw)

    def chat_json(
        self, user_prompt: str, system_prompt: str | None = None, temperature: float = 0
    ) -> dict[str, Any]:
        response = self.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return _extract_json_object(response.content)


def qwen_chat(prompt: str) -> QwenChatResponse:
    return QwenClient().chat(user_prompt=prompt)
