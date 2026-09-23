import asyncio
import json

from models.provider import ModelProvider, OpenAICompatibleModelProvider, create_provider
from services.forge_score import calculate_forge_score, readiness_level
from services.sana_ai import SanaAIService


class InvalidAIProvider(ModelProvider):
    async def generate_strong(self, task: str) -> str:
        return '{"score": 100, "questions": []}'


class StructuredAIProvider(ModelProvider):
    def __init__(self) -> None:
        self.schemas: list[str] = []

    @property
    def is_live(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return "test-live-model"

    async def generate_strong(self, task: str) -> str:
        return "{}"

    async def generate_structured(self, task: str, schema: dict, schema_name: str) -> str:
        self.schemas.append(schema_name)
        return json.dumps(
            {
                "known_information": {"raw_idea": "Есть ручная проверка"},
                "missing_information": ["Данные"],
                "questions": [
                    {"mission": "DEFINE THE WIN", "target_field": "need", "question": "Что нужно изменить?", "hint": "Опишите потребность."},
                    {"mission": "UNLOCK THE DATA", "target_field": "data_materials", "question": "Какие данные доступны?", "hint": "Укажите формат."},
                    {"mission": "DEFINE THE WIN", "target_field": "success_criteria", "question": "Как измерить успех?", "hint": "Укажите метрику."},
                ],
                "canvas": {
                    "title": "Проверка документов",
                    "context": "Есть ручная проверка",
                    "need": None,
                    "users": None,
                    "data_materials": None,
                    "constraints": None,
                    "expected_result": None,
                    "success_criteria": None,
                    "contact": None,
                    "interaction_format": None,
                },
                "challenge_health": ["Нужны уточнения"],
                "fallback_used": False,
            },
            ensure_ascii=False,
        )


def test_invalid_ai_output_uses_validated_fallback_without_score() -> None:
    analysis = asyncio.run(
        SanaAIService(InvalidAIProvider()).analyze(
            "Мы вручную проверяем документы студентов и теряем много времени.",
            "Education",
        )
    )
    payload = analysis.model_dump()
    assert analysis.fallback_used is True
    assert len(analysis.questions) >= 3
    assert analysis.canvas.data_materials is None
    assert "score" not in payload


def test_score_counts_only_filled_and_confirmed_fields() -> None:
    canvas = {
        "context": "Current process",
        "need": "Reduce manual work",
        "data_materials": "Dataset exists",
        "expected_result": None,
        "success_criteria": None,
        "constraints": None,
        "users": None,
        "contact": None,
        "interaction_format": None,
    }
    score, level, breakdown, missing = calculate_forge_score(canvas, {"context"})
    assert score == 10
    assert level == "RAW"
    assert breakdown["context_need"].points == 10
    assert breakdown["data_materials"].points == 0
    assert "Данные и материалы" in missing


def test_readiness_boundaries() -> None:
    assert readiness_level(39) == "RAW"
    assert readiness_level(40) == "SHAPING"
    assert readiness_level(70) == "READY"
    assert readiness_level(90) == "FORGED"


def test_live_ai_uses_structured_output_contract() -> None:
    provider = StructuredAIProvider()
    service = SanaAIService(provider)
    analysis = asyncio.run(
        service.analyze(
            "Мы вручную проверяем документы студентов и теряем много времени.",
            "Education",
        )
    )
    assert analysis.fallback_used is False
    assert provider.schemas == ["sana_challenge_analysis"]
    assert service.status() == {
        "live": True,
        "mode": "openai",
        "model": "test-live-model",
        "last_error": None,
    }


def test_openai_key_automatically_enables_live_provider(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    provider = create_provider()
    assert isinstance(provider, OpenAICompatibleModelProvider)
    assert provider.is_live is True
    assert provider.model_name == "gpt-4o-mini"
