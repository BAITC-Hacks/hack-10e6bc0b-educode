"""LLM boundary. The rest of the application does not import an LLM SDK."""

import os
from pathlib import Path
from abc import ABC, abstractmethod

import httpx

STRONG_SYSTEM_PROMPT = "Return a careful, factual answer that follows the requested schema."


class ModelProvider(ABC):
    @abstractmethod
    async def generate_strong(self, task: str) -> str:
        raise NotImplementedError

    async def generate_structured(
        self, task: str, schema: dict, schema_name: str
    ) -> str:
        """Generate JSON. Providers may enforce the supplied schema natively."""
        return await self.generate_strong(task)

    @property
    def is_live(self) -> bool:
        return False

    @property
    def model_name(self) -> str | None:
        return None


class MockModelProvider(ModelProvider):
    async def generate_strong(self, task: str) -> str:
        return f"[Mock strong model] Received: {task}"


class OpenAICompatibleModelProvider(ModelProvider):
    """Small HTTP adapter for providers exposing /chat/completions."""

    def __init__(self, api_key: str, base_url: str, strong_model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.strong_model = strong_model

    async def _generate(
        self,
        model: str,
        system_prompt: str,
        task: str,
        response_format: dict | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ],
        }
        if response_format:
            payload["response_format"] = response_format
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Model response content must be a string")
            return content

    async def generate_strong(self, task: str) -> str:
        return await self._generate(self.strong_model, STRONG_SYSTEM_PROMPT, task)

    async def generate_structured(
        self, task: str, schema: dict, schema_name: str
    ) -> str:
        return await self._generate(
            self.strong_model,
            STRONG_SYSTEM_PROMPT,
            task,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": False,
                    "schema": schema,
                },
            },
        )

    @property
    def is_live(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return self.strong_model


def _load_local_env() -> None:
    """Load a small local .env without adding a runtime dependency."""
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def create_provider() -> ModelProvider:
    _load_local_env()
    provider_name = os.getenv("LLM_PROVIDER", "auto").strip().lower() or "auto"
    api_key = (
        os.getenv("LLM_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    if provider_name == "mock" or not api_key:
        return MockModelProvider()
    if provider_name not in {"auto", "openai", "openai_compatible"}:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider_name}")
    default_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    strong_model = os.getenv("STRONG_MODEL", "").strip() or default_model
    return OpenAICompatibleModelProvider(
        api_key=api_key,
        base_url=(
            os.getenv("LLM_BASE_URL", "").strip()
            or os.getenv("OPENAI_BASE_URL", "").strip()
            or "https://api.openai.com/v1"
        ),
        strong_model=strong_model,
    )
