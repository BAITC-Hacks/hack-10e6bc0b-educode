"""HTTP API for the complete SANA FORGE product journey."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from models.product_schemas import (
    AIQuestionAdvice,
    CanvasUpdate,
    ChallengeCanvas,
    ConfirmationRequest,
    DraftCreate,
    ProposalCreate,
    ProposalDecision,
    Readiness,
    RefinementRequest,
    MissionQuestion,
    Topic,
)
from services.forge_score import calculate_forge_score
from services.sana_ai import SanaAIService
from storage.database import Database


TARGET_PRIORITY = (
    "need",
    "data_materials",
    "expected_result",
    "success_criteria",
    "users",
    "constraints",
    "interaction_format",
    "contact",
    "context",
)
ESSENTIAL_CLARITY_FIELDS = {
    "context", "need", "users", "data_materials", "expected_result", "success_criteria"
}
MISSION_BY_FIELD = {
    "context": "DEFINE THE WIN",
    "need": "DEFINE THE WIN",
    "expected_result": "DEFINE THE WIN",
    "success_criteria": "DEFINE THE WIN",
    "data_materials": "UNLOCK THE DATA",
    "constraints": "SET THE BOUNDARIES",
    "users": "CONNECT WITH TEAM",
    "contact": "CONNECT WITH TEAM",
    "interaction_format": "CONNECT WITH TEAM",
}


def _answer_has_information(answer: str) -> bool:
    normalized = " ".join(answer.lower().strip(" .,!?:;-").split())
    empty_answers = {
        "не знаю", "нет", "не указано", "неизвестно", "пока не знаю",
        "затрудняюсь ответить", "-", "n/a", "none",
    }
    return len(normalized) >= 4 and normalized not in empty_answers


def _pick_next_target(canvas: ChallengeCanvas, just_answered: str) -> str:
    values = canvas.model_dump()
    if not values.get(just_answered):
        return just_answered
    return next((field for field in TARGET_PRIORITY if not values.get(field)), "success_criteria")


def create_product_router(database: Database, sana_ai: SanaAIService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["SANA FORGE"])

    @router.get("/stats")
    def stats() -> dict:
        return database.stats()

    @router.get("/ai/status")
    def ai_status() -> dict:
        """Report live/fallback mode without ever exposing credentials."""
        return sana_ai.status()

    @router.post("/challenges/draft", status_code=201)
    async def create_draft(request: DraftCreate) -> dict:
        analysis = await sana_ai.analyze(request.raw_idea, request.topic)
        challenge = database.create_draft(request.raw_idea, request.topic, analysis)
        return {
            "challenge": challenge,
            "analysis": analysis.model_dump(mode="json"),
            "ai_status": sana_ai.status(),
            "refinement": {
                "potential_score": challenge["ai_preview_score"],
                "potential_level": challenge["ai_preview_level"],
                "breakdown": challenge["ai_preview_breakdown"],
                "missing_information": challenge["ai_preview_missing_information"],
                "ready_for_canvas": False,
                "next_question": analysis.questions[0].model_dump(mode="json"),
                "feedback": "Описание проанализировано. Начнём с самого важного уточнения.",
                "fallback_used": analysis.fallback_used,
                "answered_questions": 0,
            },
        }

    @router.post("/challenges/{challenge_id}/refine")
    async def refine_challenge(challenge_id: int, request: RefinementRequest) -> dict:
        try:
            challenge = database.get_challenge(challenge_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if challenge["confirmed"] or challenge["published"]:
            raise HTTPException(
                status_code=409,
                detail="AI refinement is available only before business confirmation",
            )

        canvas_values = dict(challenge["canvas"])
        informative = _answer_has_information(request.answer)
        if informative:
            # Keep the user's exact confirmed wording. AI only asks and structures the flow.
            canvas_values[request.question.target_field] = request.answer
        canvas = ChallengeCanvas.model_validate(canvas_values)
        filled_fields = {
            field for field, value in canvas.model_dump().items() if value
        }
        potential_score, potential_level, breakdown, missing = calculate_forge_score(
            canvas.model_dump(), filled_fields
        )
        answered_questions = len(challenge["ai_turns"]) + 1
        clarity_complete = all(
            canvas.model_dump().get(field) for field in ESSENTIAL_CLARITY_FIELDS
        )
        ready = answered_questions >= 3 and potential_score >= 80 and clarity_complete

        next_target = _pick_next_target(canvas, request.question.target_field)
        if ready:
            advice = AIQuestionAdvice(
                target_field=request.question.target_field,
                feedback=(
                    "Задача уже достаточно ясна для студенческой команды. "
                    "Проверьте формулировки в Challenge Canvas."
                ),
                question="Проверьте итоговый Challenge Canvas.",
                hint="Все AI-формулировки можно отредактировать перед подтверждением.",
            )
            fallback_used = not bool(sana_ai.status()["live"])
            next_question = None
        else:
            advice, fallback_used = await sana_ai.advise_next_question(
                raw_idea=challenge["raw_idea"],
                topic=challenge["topic"],
                canvas=canvas,
                current_question=request.question,
                answer=request.answer,
                next_target=next_target,
                recent_turns=challenge["ai_turns"],
            )
            if not informative:
                advice.feedback = (
                    "В ответе пока недостаточно конкретики. Можно честно указать, "
                    "что данных нет, но для готовности Challenge понадобится уточнение."
                )
            next_question = MissionQuestion(
                mission=MISSION_BY_FIELD[next_target],
                target_field=next_target,
                question=advice.question,
                hint=advice.hint,
            )

        updated = database.save_ai_refinement(
            challenge_id=challenge_id,
            canvas=canvas,
            question=request.question,
            answer=request.answer,
            feedback=advice.feedback,
            next_question=next_question,
            potential_score=potential_score,
            ready=ready,
            fallback_used=fallback_used,
        )
        return {
            "challenge": updated,
            "ai_status": sana_ai.status(),
            "refinement": {
                "feedback": advice.feedback,
                "next_question": (
                    next_question.model_dump(mode="json") if next_question else None
                ),
                "potential_score": potential_score,
                "potential_level": potential_level,
                "breakdown": {
                    key: value.model_dump() for key, value in breakdown.items()
                },
                "missing_information": missing,
                "ready_for_canvas": ready,
                "fallback_used": fallback_used,
                "answered_questions": answered_questions,
            },
        }

    @router.get("/challenges")
    def list_challenges(
        topic: Topic | Literal["All"] = Query(default="All"),
        readiness: Readiness | Literal["All"] = Query(default="All"),
        include_drafts: bool = Query(default=False),
    ) -> list[dict]:
        return database.list_challenges(
            topic=topic, readiness=readiness, published_only=not include_drafts
        )

    @router.get("/challenges/{challenge_id}")
    def get_challenge(challenge_id: int) -> dict:
        try:
            return database.get_challenge(challenge_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.put("/challenges/{challenge_id}/canvas")
    def update_canvas(challenge_id: int, request: CanvasUpdate) -> dict:
        try:
            return database.update_canvas(challenge_id, request.canvas, request.topic)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post("/challenges/{challenge_id}/confirm")
    def confirm_canvas(challenge_id: int, request: ConfirmationRequest) -> dict:
        try:
            return database.confirm_challenge(challenge_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post("/challenges/{challenge_id}/publish")
    def publish_challenge(challenge_id: int) -> dict:
        try:
            return database.publish_challenge(challenge_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/teams")
    def list_teams() -> list[dict]:
        return database.list_teams()

    @router.get("/teams/{team_id}")
    def get_team(team_id: int) -> dict:
        try:
            return database.get_team(team_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post("/challenges/{challenge_id}/proposals", status_code=201)
    def create_proposal(challenge_id: int, request: ProposalCreate) -> dict:
        try:
            return database.create_proposal(
                challenge_id=challenge_id,
                team_id=request.team_id,
                idea=request.idea,
                plan=request.plan,
                deadline=request.deadline,
                prototype_url=str(request.prototype_url) if request.prototype_url else None,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/business/dashboard")
    def business_dashboard() -> dict:
        return database.dashboard()

    @router.patch("/proposals/{proposal_id}")
    def decide_proposal(proposal_id: int, request: ProposalDecision) -> dict:
        try:
            return database.decide_proposal(proposal_id, request.status)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post(
        "/challenges/{challenge_id}/teams/{team_id}/stages/{stage_number}/confirm"
    )
    def confirm_stage(challenge_id: int, team_id: int, stage_number: int) -> dict:
        if stage_number not in (1, 2, 3):
            raise HTTPException(status_code=422, detail="stage_number must be 1, 2 or 3")
        try:
            return database.confirm_stage(challenge_id, team_id, stage_number)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return router
