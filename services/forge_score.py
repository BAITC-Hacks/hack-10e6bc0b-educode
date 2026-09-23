"""Deterministic backend-only Forge Score calculation."""

from dataclasses import dataclass

from models.product_schemas import Readiness, ScoreBreakdownItem


@dataclass(frozen=True)
class ScoreCategory:
    label: str
    fields: tuple[str, ...]
    weight: int


CATEGORIES: dict[str, ScoreCategory] = {
    "context_need": ScoreCategory("Контекст + потребность", ("context", "need"), 20),
    "data_materials": ScoreCategory("Данные и материалы", ("data_materials",), 20),
    "expected_result": ScoreCategory("Ожидаемый результат", ("expected_result",), 15),
    "success_criteria": ScoreCategory("Критерии успеха", ("success_criteria",), 15),
    "constraints": ScoreCategory("Ограничения", ("constraints",), 10),
    "users": ScoreCategory("Пользователи", ("users",), 10),
    "contact_interaction": ScoreCategory("Связь с бизнесом", ("contact", "interaction_format"), 10),
}

FIELD_LABELS = {
    "title": "Название",
    "context": "Контекст",
    "need": "Потребность",
    "users": "Пользователи",
    "data_materials": "Данные и материалы",
    "constraints": "Ограничения",
    "expected_result": "Ожидаемый результат",
    "success_criteria": "Критерии успеха",
    "contact": "Контакт",
    "interaction_format": "Формат взаимодействия",
}


def readiness_level(score: int) -> Readiness:
    if score >= 90:
        return "FORGED"
    if score >= 70:
        return "READY"
    if score >= 40:
        return "SHAPING"
    return "RAW"


def calculate_forge_score(
    canvas: dict[str, str | None], confirmed_fields: set[str]
) -> tuple[int, Readiness, dict[str, ScoreBreakdownItem], list[str]]:
    """Award points only for non-empty fields explicitly confirmed by business."""

    total = 0
    breakdown: dict[str, ScoreBreakdownItem] = {}
    missing: list[str] = []
    for key, category in CATEGORIES.items():
        confirmed = [
            field
            for field in category.fields
            if field in confirmed_fields and bool(canvas.get(field))
        ]
        # Combined categories are split evenly between their two explicit fields.
        points = round(category.weight * len(confirmed) / len(category.fields))
        category_missing = [
            FIELD_LABELS[field] for field in category.fields if field not in confirmed
        ]
        total += points
        missing.extend(category_missing)
        breakdown[key] = ScoreBreakdownItem(
            label=category.label,
            points=points,
            max_points=category.weight,
            complete=points == category.weight,
            missing_fields=category_missing,
        )
    return total, readiness_level(total), breakdown, missing

