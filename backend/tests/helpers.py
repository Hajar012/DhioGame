from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.db.session import SessionLocal
from app.models import Game


class GameApi:
    def __init__(self, client: TestClient, created_codes: list[str]) -> None:
        self.client = client
        self.created_codes = created_codes

    @staticmethod
    def auth(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def image_bytes(
        color: tuple[int, int, int] = (210, 90, 60),
        size: tuple[int, int] = (100, 75),
        image_format: str = "PNG",
    ) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", size, color).save(buffer, format=image_format)
        return buffer.getvalue()

    @staticmethod
    def drawing_payload(x_offset: int = 0) -> dict:
        return {
            "data": {
                "version": 1,
                "width": 1600,
                "height": 1000,
                "strokes": [
                    {
                        "color": "#1b1b1f",
                        "size": 11,
                        "erase": False,
                        "points": [
                            {"x": 20 + x_offset, "y": 20},
                            {"x": 200 + x_offset, "y": 120},
                        ],
                    }
                ],
            }
        }

    def create_room(
        self,
        nickname: str | None = None,
        settings: dict | None = None,
    ) -> dict:
        payload = {
            "nickname": nickname or f"Host-{uuid4().hex[:8]}",
            "settings": settings
            or {
                "mode": "same_image",
                "viewing_duration_seconds": 60,
                "drawing_duration_seconds": 180,
            },
        }
        response = self.client.post("/api/rooms", json=payload)
        assert response.status_code == 201, response.text
        data = response.json()
        self.created_codes.append(data["room"]["code"])
        return data

    def join(self, room_code: str, nickname: str | None = None) -> dict:
        response = self.client.post(
            "/api/rooms/join",
            json={
                "room_code": room_code,
                "nickname": nickname or f"Guest-{uuid4().hex[:8]}",
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def get_room(self, room_code: str, token: str) -> dict:
        response = self.client.get(
            f"/api/rooms/{room_code}", headers=self.auth(token)
        )
        assert response.status_code == 200, response.text
        return response.json()

    def upload(
        self,
        room_code: str,
        token: str,
        data: bytes | None = None,
        *,
        filename: str = "reference.png",
        content_type: str = "image/png",
    ) -> dict:
        response = self.client.post(
            f"/api/rooms/{room_code}/images",
            headers=self.auth(token),
            files={
                "file": (
                    filename,
                    data if data is not None else self.image_bytes(),
                    content_type,
                )
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    def start_game(self, room_code: str, token: str) -> dict:
        response = self.client.post(
            f"/api/rooms/{room_code}/game/start",
            headers=self.auth(token),
        )
        assert response.status_code == 200, response.text
        return response.json()

    def get_game(self, room_code: str, token: str) -> dict:
        response = self.client.get(
            f"/api/rooms/{room_code}/game", headers=self.auth(token)
        )
        assert response.status_code == 200, response.text
        return response.json()

    def sync_game(self, room_code: str, token: str) -> dict:
        response = self.client.post(
            f"/api/rooms/{room_code}/game/sync",
            headers=self.auth(token),
        )
        assert response.status_code == 200, response.text
        return response.json()

    def finish_drawing(self, room_code: str, token: str) -> dict:
        response = self.client.post(
            f"/api/rooms/{room_code}/game/finish-drawing",
            headers=self.auth(token),
        )
        assert response.status_code == 200, response.text
        return response.json()

    def get_reference(self, room_code: str, token: str):
        return self.client.get(
            f"/api/rooms/{room_code}/game/reference",
            headers=self.auth(token),
        )

    def get_drawing(self, room_code: str, token: str) -> dict:
        response = self.client.get(
            f"/api/rooms/{room_code}/drawing", headers=self.auth(token)
        )
        assert response.status_code == 200, response.text
        return response.json()

    def save_drawing(
        self,
        room_code: str,
        token: str,
        payload: dict | None = None,
    ):
        return self.client.put(
            f"/api/rooms/{room_code}/drawing",
            headers=self.auth(token),
            json=payload or self.drawing_payload(),
        )

    def submit_drawing(self, room_code: str, token: str):
        return self.client.post(
            f"/api/rooms/{room_code}/drawing/submit",
            headers=self.auth(token),
        )

    def unsubmit_drawing(self, room_code: str, token: str):
        return self.client.post(
            f"/api/rooms/{room_code}/drawing/unsubmit",
            headers=self.auth(token),
        )

    def start_reveal(self, room_code: str, token: str):
        return self.client.post(
            f"/api/rooms/{room_code}/reveal/start",
            headers=self.auth(token),
        )

    def get_reveal(self, room_code: str, token: str):
        return self.client.get(
            f"/api/rooms/{room_code}/reveal", headers=self.auth(token)
        )

    def reveal_original(self, room_code: str, token: str):
        return self.client.post(
            f"/api/rooms/{room_code}/reveal/original",
            headers=self.auth(token),
        )

    def next_reveal(self, room_code: str, token: str):
        return self.client.post(
            f"/api/rooms/{room_code}/reveal/next",
            headers=self.auth(token),
        )

    def get_reveal_reference(self, room_code: str, token: str):
        return self.client.get(
            f"/api/rooms/{room_code}/reveal/reference",
            headers=self.auth(token),
        )

    def set_phase_end(self, game_id: str, delta_seconds: int) -> None:
        with SessionLocal() as session:
            game = session.get(Game, UUID(game_id))
            assert game is not None
            game.phase_ends_at = datetime.now(timezone.utc) + timedelta(
                seconds=delta_seconds
            )
            session.commit()

    def advance_to_drawing(self, room_code: str, token: str) -> dict:
        game = self.get_game(room_code, token)
        self.set_phase_end(game["id"], -1)
        state = self.sync_game(room_code, token)
        assert state["phase"] == "drawing"
        return state

    def finish_drawing_phase(self, room_code: str, token: str) -> dict:
        game = self.get_game(room_code, token)
        self.set_phase_end(game["id"], -1)
        state = self.sync_game(room_code, token)
        assert state["phase"] == "drawing_completed"
        return state
