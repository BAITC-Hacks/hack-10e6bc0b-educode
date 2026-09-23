"""Structured SANA AI analysis with schema validation and safe fallback."""

import json
import re

from models.product_schemas import (
    AIAnalysis,
    AIQuestionAdvice,
    ChallengeCanvas,
    MissionQuestion,
    Topic,
)
from models.provider import MockModelProvider, ModelProvider


class SanaAIService:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider
        self.last_error: str | None = None

    async def analyze(self, raw_idea: str, topic: Topic) -> AIAnalysis:
        if not isinstance(self.provider, MockModelProvider):
            for _ in range(2):
                try:
                    response = await self.provider.generate_structured(
                        self._prompt(raw_idea, topic),
                        AIAnalysis.model_json_schema(),
                        "sana_challenge_analysis",
                    )
                    payload = self._extract_json(response)
                    analysis = AIAnalysis.model_validate(payload)
                    # The schema intentionally has no score field. Unknown values stay null.
                    analysis.fallback_used = False
                    self.last_error = None
                    return analysis
                except Exception as error:
                    self.last_error = f"{type(error).__name__}: {error}"
        return self._fallback(raw_idea, topic)

    async def advise_next_question(
        self,
        *,
        raw_idea: str,
        topic: Topic,
        canvas: ChallengeCanvas,
        current_question: MissionQuestion,
        answer: str,
        next_target: str,
        recent_turns: list[dict],
    ) -> tuple[AIQuestionAdvice, bool]:
        """Give feedback and phrase one backend-selected follow-up question."""
        if not isinstance(self.provider, MockModelProvider):
            prompt = self._refinement_prompt(
                raw_idea=raw_idea,
                topic=topic,
                canvas=canvas,
                current_question=current_question,
                answer=answer,
                next_target=next_target,
                recent_turns=recent_turns,
            )
            for _ in range(2):
                try:
                    response = await self.provider.generate_structured(
                        prompt,
                        AIQuestionAdvice.model_json_schema(),
                        "sana_follow_up",
                    )
                    advice = AIQuestionAdvice.model_validate(self._extract_json(response))
                    if advice.target_field != next_target:
                        raise ValueError("AI changed the backend-selected target field")
                    self.last_error = None
                    return advice, False
                except Exception as error:
                    self.last_error = f"{type(error).__name__}: {error}"
        return self._fallback_advice(next_target), True

    def status(self) -> dict[str, str | bool | None]:
        live = self.provider.is_live and self.last_error is None
        return {
            "live": live,
            "mode": "openai" if live else "fallback",
            "model": self.provider.model_name,
            "last_error": self.last_error,
        }

    @staticmethod
    def _prompt(raw_idea: str, topic: Topic) -> str:
        schema = AIAnalysis.model_json_schema()
        return (
            "Ты SANA AI, помощник бизнеса в формулировании студенческого Challenge. "
            "Верни только JSON по указанной схеме. Извлекай только факты, которые явно "
            "есть в исходном описании; ничего не додумывай. Для отсутствующих полей Canvas "
            "используй null. Сформулируй минимум три конкретных уточняющих вопроса на русском "
            "языке для недостающих полей. Не вычисляй и не упоминай Forge Score, не предлагай "
            "готовое решение и не выбирай команду. fallback_used верни false.\n"
            f"Тема: {topic}\nИсходное описание: {raw_idea}\n"
            f"JSON Schema: {json.dumps(schema, ensure_ascii=False)}"
        )

    @staticmethod
    def _refinement_prompt(
        *,
        raw_idea: str,
        topic: Topic,
        canvas: ChallengeCanvas,
        current_question: MissionQuestion,
        answer: str,
        next_target: str,
        recent_turns: list[dict],
    ) -> str:
        return (
            "Ты SANA AI и ведёшь короткое интервью с представителем бизнеса. "
            "Верни только JSON: target_field — в точности поле, выбранное backend; "
            "feedback — короткая полезная реакция на последний ответ; "
            "question — один следующий вопрос; hint — подсказка, что именно указать. "
            "Следующий вопрос обязан уточнять только поле, выбранное backend: "
            f"{next_target}. Значение поля: {SanaAIService._target_guidance(next_target)}. "
            "Не возвращайся к теме прошлого ответа, если она относится к другому полю. "
            "Не придумывай факты, не предлагай ответ за пользователя, "
            "не рассчитывай и не упоминай баллы или Forge Score. Пиши по-русски.\n"
            f"Тема: {topic}\nИсходная идея: {raw_idea}\n"
            f"Текущий Canvas: {canvas.model_dump_json()}\n"
            f"Последний вопрос: {current_question.question}\n"
            f"Ответ бизнеса: {answer}\n"
            f"Последние ходы: {json.dumps(recent_turns[-3:], ensure_ascii=False)}\n"
            f"JSON Schema: {json.dumps(AIQuestionAdvice.model_json_schema(), ensure_ascii=False)}"
        )

    @staticmethod
    def _target_guidance(target_field: str) -> str:
        guidance = {
            "context": "что происходит сейчас, масштаб и причина проблемы",
            "need": "какое изменение нужно бизнесу, без описания функций решения",
            "users": "кто будет пользоваться результатом или затронут процессом",
            "data_materials": "какие реальные данные и материалы доступны команде",
            "expected_result": "какой проверяемый артефакт должна передать команда",
            "success_criteria": "по каким измеримым признакам бизнес примет результат",
            "constraints": "сроки, технологии, доступы и другие границы MVP",
            "contact": "кто со стороны бизнеса отвечает команде",
            "interaction_format": "канал и частота обратной связи с бизнесом",
        }
        return guidance[target_field]

    @staticmethod
    def _extract_json(response: str) -> dict:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError("AI response must be a JSON object")
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        if '"score"' in serialized or '"forge_score"' in serialized:
            raise ValueError("AI must not calculate Forge Score")
        return payload

    @staticmethod
    def _fallback_advice(target_field: str) -> AIQuestionAdvice:
        questions: dict[str, tuple[str, str]] = {
            "context": (
                "Что именно происходит сейчас и почему текущий процесс создаёт проблему?",
                "Опишите текущий процесс, частоту и основные сложности.",
            ),
            "need": (
                "Что бизнесу необходимо изменить в первую очередь?",
                "Сформулируйте потребность без предложения готового решения.",
            ),
            "users": (
                "Кто будет основным пользователем результата?",
                "Укажите роли или группы пользователей без персональных данных.",
            ),
            "data_materials": (
                "Какие данные и материалы вы сможете предоставить команде?",
                "Укажите тип, формат, примерный объём и условия доступа.",
            ),
            "expected_result": (
                "Какой конкретный результат должна передать команда?",
                "Например: прототип, API, модель, панель или рекомендации.",
            ),
            "success_criteria": (
                "По каким измеримым признакам вы примете результат?",
                "Укажите метрику, желаемое значение или проверяемое условие.",
            ),
            "constraints": (
                "Какие сроки, технологии и ограничения доступа нужно учесть?",
                "Перечислите реальные границы MVP и требования безопасности.",
            ),
            "contact": (
                "Кто со стороны бизнеса сможет отвечать на вопросы команды?",
                "Достаточно роли или рабочего контакта, без личных данных.",
            ),
            "interaction_format": (
                "Как и как часто бизнес будет давать обратную связь?",
                "Укажите канал, частоту встреч и формат проверки промежуточных результатов.",
            ),
        }
        question, hint = questions[target_field]
        return AIQuestionAdvice(
            target_field=target_field,
            feedback="Спасибо, ответ сохранён в Challenge Canvas.",
            question=question,
            hint=hint,
        )

    @staticmethod
    def _fallback(raw_idea: str, topic: Topic) -> AIAnalysis:
        lower = raw_idea.lower()
        if "документ" in lower:
            title = "Автоматизация проверки документов"
        elif "расписан" in lower or "аудитор" in lower:
            title = "Оптимизация расписания"
        elif "нагруз" in lower:
            title = "Прогнозирование нагрузки"
        else:
            words = raw_idea.rstrip(".!?").split()
            title = " ".join(words[:7]).capitalize()

        questions = [
            MissionQuestion(
                mission="DEFINE THE WIN",
                target_field="need",
                question="Что именно бизнесу необходимо изменить в текущем процессе?",
                hint="Опишите потребность без предложения готового решения.",
            ),
            MissionQuestion(
                mission="UNLOCK THE DATA",
                target_field="data_materials",
                question="Какие данные и материалы вы предоставите команде?",
                hint="Перечислите доступные примеры, форматы и ограничения доступа.",
            ),
            MissionQuestion(
                mission="DEFINE THE WIN",
                target_field="expected_result",
                question="Какой конкретный результат должна передать команда?",
                hint="Например: прототип, API, модель, панель или рекомендации.",
            ),
            MissionQuestion(
                mission="DEFINE THE WIN",
                target_field="success_criteria",
                question="Какой измеримый результат будет означать успех?",
                hint="Укажите текущее и желаемое значение, время или процент.",
            ),
            MissionQuestion(
                mission="SET THE BOUNDARIES",
                target_field="constraints",
                question="Какие сроки и технологические ограничения нужно учесть?",
                hint="Например: срок MVP, допустимый стек, требования безопасности.",
            ),
            MissionQuestion(
                mission="CONNECT WITH TEAM",
                target_field="users",
                question="Кто будет основным пользователем результата?",
                hint="Укажите роли или группы пользователей без персональных данных.",
            ),
        ]
        return AIAnalysis(
            known_information={"raw_idea": raw_idea, "topic": topic},
            missing_information=[
                "Пользователи",
                "Данные и материалы",
                "Ожидаемый результат",
                "Критерии успеха",
                "Ограничения",
                "Контакт и формат взаимодействия",
            ],
            questions=questions,
            canvas=ChallengeCanvas(
                title=title,
                context=raw_idea,
                need=None,
                users=None,
                data_materials=None,
                constraints=None,
                expected_result=None,
                success_criteria=None,
                contact=None,
                interaction_format=None,
            ),
            challenge_health=[
                "Исходная проблема сохранена без добавления неподтверждённых фактов.",
                "Ответьте на Forge Missions и отредактируйте Canvas перед подтверждением.",
            ],
            fallback_used=True,
        )
