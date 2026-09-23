from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from models.provider import MockModelProvider
from storage.database import Database


def product_client(tmp_path: Path) -> TestClient:
    database = Database(tmp_path / "test-sana-forge.db")
    return TestClient(create_app(provider=MockModelProvider(), database=database))


def test_seed_data_and_real_counters(tmp_path: Path) -> None:
    with product_client(tmp_path) as client:
        stats = client.get("/api/stats").json()
        challenges = client.get("/api/challenges").json()
        teams = client.get("/api/teams").json()
    assert stats["published_challenges"] >= 12
    assert stats["drafts"] >= 5
    assert stats["teams"] >= 5
    assert stats["proposals"] >= 5
    assert len(challenges) == stats["published_challenges"]
    assert len(teams) == stats["teams"]
    assert [item["score"] for item in challenges] == sorted(
        (item["score"] for item in challenges), reverse=True
    )


def test_complete_business_to_team_progress_flow(tmp_path: Path) -> None:
    with product_client(tmp_path) as client:
        draft_response = client.post(
            "/api/challenges/draft",
            json={
                "raw_idea": "Мы вручную проверяем заявки студентов и хотим сократить время обработки.",
                "topic": "Education",
            },
        )
        assert draft_response.status_code == 201
        draft = draft_response.json()
        challenge_id = draft["challenge"]["id"]
        analysis = draft["analysis"]
        assert len(analysis["questions"]) >= 3
        assert analysis["fallback_used"] is True
        assert "score" not in analysis
        assert analysis["canvas"]["data_materials"] is None

        canvas = {
            "title": "AI-проверка заявок студентов",
            "context": "Сотрудники вручную проверяют каждую заявку около 20 минут.",
            "need": "Нужно сократить время проверки и число пропущенных ошибок.",
            "users": "Сотрудники деканата и студенты.",
            "data_materials": "100 анонимизированных заявок в PDF.",
            "constraints": "MVP за 6 недель, Python и открытые библиотеки.",
            "expected_result": "Рабочий прототип проверки комплектности заявки.",
            "success_criteria": "Проверка одной заявки занимает не более 5 минут.",
            "contact": "Куратор деканата.",
            "interaction_format": "Telegram и созвон раз в неделю.",
        }
        updated = client.put(
            f"/api/challenges/{challenge_id}/canvas",
            json={"canvas": canvas, "topic": "Education"},
        )
        assert updated.status_code == 200
        assert updated.json()["confirmed"] is False
        position_before_score = updated.json()["projected_position"]

        early_publish = client.post(f"/api/challenges/{challenge_id}/publish")
        assert early_publish.status_code == 409

        confirmed = client.post(
            f"/api/challenges/{challenge_id}/confirm", json={"confirmed": True}
        )
        assert confirmed.status_code == 200
        confirmed_body = confirmed.json()
        assert confirmed_body["score"] == 100
        assert confirmed_body["level"] == "FORGED"
        assert confirmed_body["missing_information"] == []
        assert confirmed_body["score_history"] == [100]
        assert confirmed_body["projected_position"] < position_before_score

        published = client.post(f"/api/challenges/{challenge_id}/publish")
        assert published.status_code == 200
        published_body = published.json()
        assert published_body["published"] is True
        catalog = client.get("/api/challenges").json()
        expected_position = next(
            index for index, item in enumerate(catalog, start=1) if item["id"] == challenge_id
        )
        assert published_body["position"] == expected_position
        assert published_body["position"] == confirmed_body["projected_position"]

        team = client.get("/api/teams/2").json()
        points_before = team["points"]
        proposal_response = client.post(
            f"/api/challenges/{challenge_id}/proposals",
            json={
                "team_id": 2,
                "idea": "OCR извлекает поля, а правила проверяют комплектность заявки.",
                "plan": "Собрать тестовый набор, сделать API и проверить метрики.",
                "deadline": "6 недель",
                "prototype_url": "https://github.com/techvision/prototype",
            },
        )
        assert proposal_response.status_code == 201
        proposal = proposal_response.json()
        dashboard = client.get("/api/business/dashboard").json()
        assert any(item["id"] == proposal["id"] for item in dashboard["proposals"])

        selected = client.patch(
            f"/api/proposals/{proposal['id']}", json={"status": "SELECTED"}
        )
        assert selected.status_code == 200
        assert selected.json()["status"] == "SELECTED"

        progress_before = client.get("/api/teams/2").json()
        stages = [
            stage for stage in progress_before["progress"]
            if stage["challenge_id"] == challenge_id
        ]
        assert len(stages) == 3
        assert all(stage["status"] == "PENDING" for stage in stages)

        completed = client.post(
            f"/api/challenges/{challenge_id}/teams/2/stages/1/confirm"
        )
        assert completed.status_code == 200
        completed_team = completed.json()
        assert completed_team["points"] == points_before + 50
        assert any(
            event["challenge_id"] == challenge_id and event["points"] == 50
            for event in completed_team["point_history"]
        )


def test_catalog_filters_and_frontend_history_routes(tmp_path: Path) -> None:
    with product_client(tmp_path) as client:
        education = client.get("/api/challenges", params={"topic": "Education"})
        forged = client.get("/api/challenges", params={"readiness": "FORGED"})
        challenge_page = client.get("/challenges/1")
        business_page = client.get("/business/new")
    assert education.status_code == 200
    assert all(item["topic"] == "Education" for item in education.json())
    assert forged.status_code == 200
    assert all(item["level"] == "FORGED" for item in forged.json())
    assert challenge_page.status_code == 200 and "SANA FORGE" in challenge_page.text
    assert business_page.status_code == 200 and "SANA FORGE" in business_page.text


def test_ai_refinement_continues_until_backend_preview_reaches_80(tmp_path: Path) -> None:
    answers = {
        "context": "Сотрудники вручную проверяют документы около 20 минут.",
        "need": "Нужно сократить ручную проверку и количество пропущенных ошибок.",
        "users": "Сотрудники деканата, которые проверяют заявления студентов.",
        "data_materials": "Есть 100 обезличенных PDF-заявлений и правила проверки.",
        "expected_result": "Рабочий прототип проверки комплектности документов.",
        "success_criteria": "Проверка занимает не более 5 минут при точности 90 процентов.",
        "constraints": "MVP за 6 недель на Python и открытых библиотеках.",
        "contact": "Куратор деканата.",
        "interaction_format": "Созвон раз в неделю и рабочий чат.",
    }
    with product_client(tmp_path) as client:
        created = client.post(
            "/api/challenges/draft",
            json={
                "raw_idea": "Мы вручную проверяем документы студентов и теряем много времени.",
                "topic": "Education",
            },
        ).json()
        challenge_id = created["challenge"]["id"]
        question = created["refinement"]["next_question"]
        result = None
        for _ in range(10):
            response = client.post(
                f"/api/challenges/{challenge_id}/refine",
                json={"question": question, "answer": answers[question["target_field"]]},
            )
            assert response.status_code == 200
            result = response.json()
            # The interview preview never mutates the official score.
            assert result["challenge"]["score"] == 0
            if result["refinement"]["ready_for_canvas"]:
                break
            question = result["refinement"]["next_question"]

        assert result is not None
        assert result["refinement"]["ready_for_canvas"] is True
        assert 80 <= result["refinement"]["potential_score"] <= 100
        assert result["refinement"]["answered_questions"] >= 3
        assert result["challenge"]["ai_ready"] is True
        assert len(result["challenge"]["ai_turns"]) >= 3

        confirmed = client.post(
            f"/api/challenges/{challenge_id}/confirm", json={"confirmed": True}
        ).json()
        assert confirmed["score"] == result["refinement"]["potential_score"]
