"""Small SQLite persistence layer for the hackathon product flow."""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models.product_schemas import (
    AIAnalysis,
    CANVAS_FIELDS,
    ChallengeCanvas,
    MissionQuestion,
    Topic,
)
from services.forge_score import calculate_forge_score

STAGES = (
    (1, "Prototype", 50),
    (2, "Testing", 50),
    (3, "Final Version", 50),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_idea TEXT NOT NULL,
            topic TEXT NOT NULL,
            title TEXT,
            context TEXT,
            need TEXT,
            users TEXT,
            data_materials TEXT,
            constraints TEXT,
            expected_result TEXT,
            success_criteria TEXT,
            contact TEXT,
            interaction_format TEXT,
            analysis_json TEXT,
            confirmed_fields TEXT NOT NULL DEFAULT '[]',
            confirmed INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            level TEXT NOT NULL DEFAULT 'RAW',
            published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ai_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            question_json TEXT NOT NULL,
            answer TEXT NOT NULL,
            feedback TEXT NOT NULL,
            next_question_json TEXT,
            potential_score INTEGER NOT NULL,
            ready INTEGER NOT NULL DEFAULT 0,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            initials TEXT NOT NULL,
            interests TEXT NOT NULL,
            skills TEXT NOT NULL,
            technologies TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            idea TEXT NOT NULL,
            plan TEXT NOT NULL,
            deadline TEXT NOT NULL,
            prototype_url TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS progress_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            stage_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            points INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            completed_at TEXT,
            UNIQUE(challenge_id, team_id, stage_number)
        );
        CREATE TABLE IF NOT EXISTS point_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            points INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
        with self._lock, self.connect() as connection:
            connection.executescript(schema)
            count = connection.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
            if count == 0:
                self._seed(connection)

    def _seed(self, connection: sqlite3.Connection) -> None:
        teams = [
            ("Nomad AI", "NA", ["AI в образовании", "NLP", "Документы"], ["OCR", "RAG", "API"], ["Python", "LLM", "FastAPI"], 50),
            ("TechVision", "TV", ["Computer Vision", "EdTech"], ["CV", "MLOps"], ["Python", "OpenCV", "YOLO"], 0),
            ("KZ Innovators", "KI", ["Smart City", "IoT"], ["Analytics", "Hardware"], ["Python", "IoT", "SQL"], 0),
            ("DataSteppe", "DS", ["FinTech", "Analytics"], ["Forecasting", "BI"], ["Pandas", "ML", "Power BI"], 0),
            ("Qazaq Code", "QC", ["Web", "Automation"], ["Frontend", "Bots"], ["React", "Node", "Telegram"], 0),
        ]
        connection.executemany(
            "INSERT INTO teams(name, initials, interests, skills, technologies, points) VALUES (?, ?, ?, ?, ?, ?)",
            [(name, initials, json.dumps(interests, ensure_ascii=False), json.dumps(skills, ensure_ascii=False), json.dumps(tech, ensure_ascii=False), points) for name, initials, interests, skills, tech, points in teams],
        )

        base = {
            "context": "Процесс выполняется вручную и занимает много времени.",
            "need": "Нужно сократить ручную работу и количество ошибок.",
            "users": "Сотрудники организации и студенты.",
            "data_materials": "Анонимизированные примеры и описание текущего процесса.",
            "constraints": "MVP за 8 недель, открытые технологии.",
            "expected_result": "Рабочий прототип, проверенный на тестовых данных.",
            "success_criteria": "Время обработки сокращено минимум в два раза.",
            "contact": "Куратор от бизнеса.",
            "interaction_format": "Еженедельный созвон и чат.",
        }
        published = [
            ("AI-проверка документов студентов", "Education", 9),
            ("Чат-бот приёмной комиссии", "AI-ML", 8),
            ("Прогноз загрузки кафедр", "Education", 7),
            ("Раннее выявление финансового мошенничества", "FinTech", 7),
            ("Маршрутизация пациентов клиники", "Healthcare", 6),
            ("Умное расписание аудиторий", "Smart City", 6),
            ("Мониторинг энергопотребления кампуса", "Smart City", 5),
            ("Карьерные рекомендации студентам", "AI-ML", 5),
            ("Цифровизация архива", "Other", 4),
            ("Карта доступности кампуса", "Smart City", 3),
            ("Онлайн-заказы для студенческой кофейни", "Other", 2),
            ("Персональный AI-тренер по математике", "Education", 8),
        ]
        ordered_fields = [
            "context", "need", "data_materials", "expected_result", "success_criteria",
            "constraints", "users", "contact", "interaction_format",
        ]
        published_ids: list[int] = []
        for index, (title, topic, filled_count) in enumerate(published):
            canvas = {key: (value if key in ordered_fields[:filled_count] else None) for key, value in base.items()}
            confirmed = set(ordered_fields[:filled_count])
            score, level, _, _ = calculate_forge_score(canvas, confirmed)
            now = _now()
            cursor = connection.execute(
                """INSERT INTO challenges(
                    raw_idea, topic, title, context, need, users, data_materials,
                    constraints, expected_result, success_criteria, contact,
                    interaction_format, confirmed_fields, confirmed, score, level,
                    published, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 1, ?, ?)""",
                (
                    f"Требуется решение: {title}", topic, title, canvas["context"], canvas["need"],
                    canvas["users"], canvas["data_materials"], canvas["constraints"],
                    canvas["expected_result"], canvas["success_criteria"], canvas["contact"],
                    canvas["interaction_format"], json.dumps(sorted(confirmed)), score, level, now, now,
                ),
            )
            challenge_id = int(cursor.lastrowid)
            published_ids.append(challenge_id)
            history = [max(0, score - 30), max(0, score - 15), score]
            for history_score in dict.fromkeys(history):
                connection.execute(
                    "INSERT INTO score_history(challenge_id, score, created_at) VALUES (?, ?, ?)",
                    (challenge_id, history_score, now),
                )

        raw_drafts = [
            ("Хотим быстрее отвечать на повторяющиеся вопросы абитуриентов.", "Education"),
            ("Нужно лучше понимать загрузку преподавателей на следующий семестр.", "Education"),
            ("Хотим находить подозрительные операции в обезличенных транзакциях.", "FinTech"),
            ("Нужно сократить ожидание пациентов в регистратуре.", "Healthcare"),
            ("Хотим видеть свободные аудитории и избегать конфликтов расписания.", "Smart City"),
        ]
        for raw_idea, topic in raw_drafts:
            now = _now()
            connection.execute(
                "INSERT INTO challenges(raw_idea, topic, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (raw_idea, topic, "Черновик без названия", now, now),
            )

        proposals = [
            (published_ids[0], 1, "OCR и LLM проверяют комплектность документов.", "Прототип OCR, правила, интерфейс и тестирование.", "6 недель", "https://github.com/nomad-ai/docs", "SELECTED"),
            (published_ids[0], 2, "Computer Vision распознаёт печати и подписи.", "Сбор тестового набора, модель, API и отчёт.", "8 недель", None, "PENDING"),
            (published_ids[1], 5, "RAG-бот отвечает по официальной базе знаний.", "Индекс, бот, оценка качества и пилот.", "5 недель", None, "PENDING"),
            (published_ids[2], 4, "Модель прогнозирует нагрузку по истории кафедр.", "Подготовка данных, baseline, dashboard.", "7 недель", None, "PENDING"),
            (published_ids[5], 3, "Оптимизатор устраняет конфликты расписания.", "Модель ограничений, API, тестовый прогон.", "6 недель", None, "PENDING"),
        ]
        now = _now()
        connection.executemany(
            """INSERT INTO proposals(challenge_id, team_id, idea, plan, deadline, prototype_url, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(*proposal, now) for proposal in proposals],
        )
        for number, name, points in STAGES:
            connection.execute(
                """INSERT INTO progress_stages(challenge_id, team_id, stage_number, name, points, status, completed_at)
                VALUES (?, 1, ?, ?, ?, ?, ?)""",
                (published_ids[0], number, name, points, "COMPLETED" if number == 1 else "PENDING", now if number == 1 else None),
            )
        connection.execute(
            "INSERT INTO point_history(team_id, challenge_id, points, reason, created_at) VALUES (1, ?, 50, ?, ?)",
            (published_ids[0], "Stage 1 — Prototype", now),
        )

    def create_draft(self, raw_idea: str, topic: Topic, analysis: AIAnalysis) -> dict[str, Any]:
        canvas = analysis.canvas.model_dump()
        now = _now()
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO challenges(
                    raw_idea, topic, title, context, need, users, data_materials,
                    constraints, expected_result, success_criteria, contact,
                    interaction_format, analysis_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    raw_idea, topic, canvas["title"], canvas["context"], canvas["need"],
                    canvas["users"], canvas["data_materials"], canvas["constraints"],
                    canvas["expected_result"], canvas["success_criteria"], canvas["contact"],
                    canvas["interaction_format"], analysis.model_dump_json(), now, now,
                ),
            )
            challenge_id = int(cursor.lastrowid)
        return self.get_challenge(challenge_id)

    def update_canvas(self, challenge_id: int, canvas: ChallengeCanvas, topic: Topic) -> dict[str, Any]:
        values = canvas.model_dump()
        assignments = ", ".join(f"{field} = ?" for field in CANVAS_FIELDS)
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                f"""UPDATE challenges SET {assignments}, topic = ?, confirmed_fields = '[]',
                confirmed = 0, score = 0, level = 'RAW', updated_at = ? WHERE id = ?""",
                [*(values[field] for field in CANVAS_FIELDS), topic, _now(), challenge_id],
            )
            if cursor.rowcount == 0:
                raise KeyError("Challenge not found")
        return self.get_challenge(challenge_id)

    def save_ai_refinement(
        self,
        *,
        challenge_id: int,
        canvas: ChallengeCanvas,
        question: MissionQuestion,
        answer: str,
        feedback: str,
        next_question: MissionQuestion | None,
        potential_score: int,
        ready: bool,
        fallback_used: bool,
    ) -> dict[str, Any]:
        """Persist a verified user answer and the next AI interview step."""
        values = canvas.model_dump()
        assignments = ", ".join(f"{field} = ?" for field in CANVAS_FIELDS)
        now = _now()
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                f"""UPDATE challenges SET {assignments}, confirmed_fields = '[]',
                confirmed = 0, score = 0, level = 'RAW', updated_at = ? WHERE id = ?""",
                [*(values[field] for field in CANVAS_FIELDS), now, challenge_id],
            )
            if cursor.rowcount == 0:
                raise KeyError("Challenge not found")
            connection.execute(
                """INSERT INTO ai_turns(
                    challenge_id, question_json, answer, feedback, next_question_json,
                    potential_score, ready, fallback_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    challenge_id,
                    question.model_dump_json(),
                    answer,
                    feedback,
                    next_question.model_dump_json() if next_question else None,
                    potential_score,
                    int(ready),
                    int(fallback_used),
                    now,
                ),
            )
        return self.get_challenge(challenge_id)

    def confirm_challenge(self, challenge_id: int) -> dict[str, Any]:
        with self._lock, self.connect() as connection:
            row = connection.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,)).fetchone()
            if row is None:
                raise KeyError("Challenge not found")
            canvas = {field: row[field] for field in CANVAS_FIELDS}
            confirmed_fields = {field for field, value in canvas.items() if value}
            score, level, _, _ = calculate_forge_score(canvas, confirmed_fields)
            now = _now()
            connection.execute(
                """UPDATE challenges SET confirmed_fields = ?, confirmed = 1, score = ?,
                level = ?, updated_at = ? WHERE id = ?""",
                (json.dumps(sorted(confirmed_fields)), score, level, now, challenge_id),
            )
            last = connection.execute(
                "SELECT score FROM score_history WHERE challenge_id = ? ORDER BY id DESC LIMIT 1",
                (challenge_id,),
            ).fetchone()
            if last is None or last["score"] != score:
                connection.execute(
                    "INSERT INTO score_history(challenge_id, score, created_at) VALUES (?, ?, ?)",
                    (challenge_id, score, now),
                )
        return self.get_challenge(challenge_id)

    def publish_challenge(self, challenge_id: int) -> dict[str, Any]:
        with self._lock, self.connect() as connection:
            row = connection.execute("SELECT confirmed, title FROM challenges WHERE id = ?", (challenge_id,)).fetchone()
            if row is None:
                raise KeyError("Challenge not found")
            if not row["confirmed"]:
                raise ValueError("Challenge Canvas must be confirmed by business before publishing")
            if not row["title"]:
                raise ValueError("Challenge title is required")
            connection.execute(
                "UPDATE challenges SET published = 1, updated_at = ? WHERE id = ?",
                (_now(), challenge_id),
            )
        return self.get_challenge(challenge_id)

    def list_challenges(
        self, topic: str = "All", readiness: str = "All", published_only: bool = True
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if published_only:
            clauses.append("published = 1")
        if topic != "All":
            clauses.append("topic = ?")
            params.append(topic)
        if readiness != "All":
            clauses.append("level = ?")
            params.append(readiness)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT id FROM challenges {where} ORDER BY score DESC, id ASC", params
            ).fetchall()
        return [self.get_challenge(int(row["id"])) for row in rows]

    def get_challenge(self, challenge_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,)).fetchone()
            if row is None:
                raise KeyError("Challenge not found")
            canvas = {field: row[field] for field in CANVAS_FIELDS}
            confirmed_fields = set(json.loads(row["confirmed_fields"]))
            total, level, breakdown, missing = calculate_forge_score(canvas, confirmed_fields)
            history = [
                item["score"]
                for item in connection.execute(
                    "SELECT score FROM score_history WHERE challenge_id = ? ORDER BY id", (challenge_id,)
                ).fetchall()
            ]
            proposal_count = connection.execute(
                "SELECT COUNT(*) FROM proposals WHERE challenge_id = ?", (challenge_id,)
            ).fetchone()[0]
            published_ids = [
                item["id"]
                for item in connection.execute(
                    "SELECT id FROM challenges WHERE published = 1 ORDER BY score DESC, id ASC"
                ).fetchall()
            ]
            position = published_ids.index(challenge_id) + 1 if challenge_id in published_ids else None
            if position is not None:
                projected_position = position
            else:
                # An unpublished challenge is inserted after existing equal-score items,
                # matching the catalog's stable score DESC, id ASC ordering.
                projected_position = 1 + connection.execute(
                    "SELECT COUNT(*) FROM challenges WHERE published = 1 AND score >= ?",
                    (row["score"],),
                ).fetchone()[0]
            analysis = json.loads(row["analysis_json"]) if row["analysis_json"] else None
            turns = []
            for item in connection.execute(
                "SELECT * FROM ai_turns WHERE challenge_id = ? ORDER BY id",
                (challenge_id,),
            ).fetchall():
                turns.append(
                    {
                        "id": int(item["id"]),
                        "question": json.loads(item["question_json"]),
                        "answer": item["answer"],
                        "feedback": item["feedback"],
                        "next_question": (
                            json.loads(item["next_question_json"])
                            if item["next_question_json"] else None
                        ),
                        "potential_score": int(item["potential_score"]),
                        "ready": bool(item["ready"]),
                        "fallback_used": bool(item["fallback_used"]),
                        "created_at": item["created_at"],
                    }
                )
            preview_fields = {field for field, value in canvas.items() if value}
            preview_total, preview_level, preview_breakdown, preview_missing = (
                calculate_forge_score(canvas, preview_fields)
            )
            return {
                "id": challenge_id,
                "raw_idea": row["raw_idea"],
                "topic": row["topic"],
                "canvas": canvas,
                "confirmed": bool(row["confirmed"]),
                "score": total if row["confirmed"] else int(row["score"]),
                "level": level if row["confirmed"] else row["level"],
                "published": bool(row["published"]),
                "position": position,
                "projected_position": projected_position,
                "breakdown": {key: value.model_dump() for key, value in breakdown.items()},
                "missing_information": missing,
                "score_history": history,
                "proposal_count": int(proposal_count),
                "analysis": analysis,
                "ai_turns": turns,
                "ai_ready": bool(turns and turns[-1]["ready"]),
                "ai_preview_score": preview_total,
                "ai_preview_level": preview_level,
                "ai_preview_breakdown": {
                    key: value.model_dump() for key, value in preview_breakdown.items()
                },
                "ai_preview_missing_information": preview_missing,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            return {
                "published_challenges": connection.execute("SELECT COUNT(*) FROM challenges WHERE published = 1").fetchone()[0],
                "drafts": connection.execute("SELECT COUNT(*) FROM challenges WHERE published = 0").fetchone()[0],
                "teams": connection.execute("SELECT COUNT(*) FROM teams").fetchone()[0],
                "topics": connection.execute("SELECT COUNT(DISTINCT topic) FROM challenges WHERE published = 1").fetchone()[0],
                "proposals": connection.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],
            }

    def list_teams(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM teams ORDER BY points DESC, id").fetchall()
        return [self._team_payload(row) for row in rows]

    def get_team(self, team_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
            if row is None:
                raise KeyError("Team not found")
            payload = self._team_payload(row)
            payload["progress"] = [
                dict(item)
                for item in connection.execute(
                    """SELECT ps.*, c.title AS challenge_title FROM progress_stages ps
                    JOIN challenges c ON c.id = ps.challenge_id
                    WHERE ps.team_id = ? ORDER BY ps.challenge_id, ps.stage_number""",
                    (team_id,),
                ).fetchall()
            ]
            payload["point_history"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM point_history WHERE team_id = ? ORDER BY id DESC", (team_id,)
                ).fetchall()
            ]
            payload["proposal_count"] = connection.execute(
                "SELECT COUNT(*) FROM proposals WHERE team_id = ?", (team_id,)
            ).fetchone()[0]
            return payload

    @staticmethod
    def _team_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "name": row["name"],
            "initials": row["initials"],
            "interests": json.loads(row["interests"]),
            "skills": json.loads(row["skills"]),
            "technologies": json.loads(row["technologies"]),
            "points": int(row["points"]),
        }

    def create_proposal(
        self, challenge_id: int, team_id: int, idea: str, plan: str,
        deadline: str, prototype_url: str | None,
    ) -> dict[str, Any]:
        with self._lock, self.connect() as connection:
            challenge = connection.execute(
                "SELECT published FROM challenges WHERE id = ?", (challenge_id,)
            ).fetchone()
            if challenge is None:
                raise KeyError("Challenge not found")
            if not challenge["published"]:
                raise ValueError("Proposals are accepted only for published challenges")
            if connection.execute("SELECT 1 FROM teams WHERE id = ?", (team_id,)).fetchone() is None:
                raise KeyError("Team not found")
            cursor = connection.execute(
                """INSERT INTO proposals(challenge_id, team_id, idea, plan, deadline, prototype_url, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)""",
                (challenge_id, team_id, idea, plan, deadline, prototype_url, _now()),
            )
            proposal_id = int(cursor.lastrowid)
        return self.get_proposal(proposal_id)

    def get_proposal(self, proposal_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT p.*, t.name AS team_name, t.initials, c.title AS challenge_title
                FROM proposals p JOIN teams t ON t.id = p.team_id
                JOIN challenges c ON c.id = p.challenge_id WHERE p.id = ?""",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Proposal not found")
            return dict(row)

    def dashboard(self) -> dict[str, Any]:
        challenges = self.list_challenges(published_only=False)
        with self.connect() as connection:
            proposal_rows = connection.execute(
                """SELECT p.*, t.name AS team_name, t.initials, c.title AS challenge_title
                FROM proposals p JOIN teams t ON t.id = p.team_id
                JOIN challenges c ON c.id = p.challenge_id ORDER BY p.id DESC"""
            ).fetchall()
        return {"challenges": challenges, "proposals": [dict(row) for row in proposal_rows]}

    def decide_proposal(self, proposal_id: int, status: str) -> dict[str, Any]:
        with self._lock, self.connect() as connection:
            proposal = connection.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
            if proposal is None:
                raise KeyError("Proposal not found")
            connection.execute("UPDATE proposals SET status = ? WHERE id = ?", (status, proposal_id))
            if status == "SELECTED":
                for number, name, points in STAGES:
                    connection.execute(
                        """INSERT OR IGNORE INTO progress_stages(
                        challenge_id, team_id, stage_number, name, points, status
                        ) VALUES (?, ?, ?, ?, ?, 'PENDING')""",
                        (proposal["challenge_id"], proposal["team_id"], number, name, points),
                    )
        return self.get_proposal(proposal_id)

    def confirm_stage(self, challenge_id: int, team_id: int, stage_number: int) -> dict[str, Any]:
        with self._lock, self.connect() as connection:
            stage = connection.execute(
                """SELECT * FROM progress_stages
                WHERE challenge_id = ? AND team_id = ? AND stage_number = ?""",
                (challenge_id, team_id, stage_number),
            ).fetchone()
            if stage is None:
                raise KeyError("Progress stage not found")
            if stage["status"] == "COMPLETED":
                return self.get_team(team_id)
            if stage_number > 1:
                previous = connection.execute(
                    """SELECT status FROM progress_stages
                    WHERE challenge_id = ? AND team_id = ? AND stage_number = ?""",
                    (challenge_id, team_id, stage_number - 1),
                ).fetchone()
                if previous is None or previous["status"] != "COMPLETED":
                    raise ValueError("Previous stage must be completed first")
            now = _now()
            connection.execute(
                "UPDATE progress_stages SET status = 'COMPLETED', completed_at = ? WHERE id = ?",
                (now, stage["id"]),
            )
            connection.execute("UPDATE teams SET points = points + ? WHERE id = ?", (stage["points"], team_id))
            connection.execute(
                """INSERT INTO point_history(team_id, challenge_id, points, reason, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (team_id, challenge_id, stage["points"], f"Stage {stage_number} — {stage['name']}", now),
            )
        return self.get_team(team_id)
