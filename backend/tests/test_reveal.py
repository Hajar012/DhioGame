from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    Assignment,
    ReferenceImage,
    Reveal,
    Room,
    RoomStatus,
)


def complete_game(api, mode: str = "same_image"):
    settings = {
        "mode": mode,
        "viewing_duration_seconds": 60,
        "drawing_duration_seconds": 180,
    }
    host = api.create_room("RevealHost", settings)
    code = host["room"]["code"]
    guest = api.join(code, "RevealGuest")

    if mode == "same_image":
        image = api.image_bytes((190, 70, 40))
        api.upload(code, host["token"], image)
    else:
        image = api.image_bytes((190, 70, 40))
        second = api.image_bytes((40, 90, 190))
        api.upload(code, host["token"], image, filename="first.png")
        api.upload(code, host["token"], second, filename="second.png")

    api.start_game(code, host["token"])
    api.advance_to_drawing(code, host["token"])
    assert api.save_drawing(code, host["token"]).status_code == 200
    assert api.submit_drawing(code, host["token"]).status_code == 200
    assert api.save_drawing(
        code, guest["token"], api.drawing_payload(30)
    ).status_code == 200
    assert api.submit_drawing(code, guest["token"]).status_code == 200
    api.finish_drawing_phase(code, host["token"])
    return host, guest, image


def test_reveal_flow_privacy_permissions_and_completion(api):
    host, guest, image = complete_game(api)
    code = host["room"]["code"]

    guest_start = api.start_reveal(code, guest["token"])
    assert guest_start.status_code == 403
    assert api.get_reveal_reference(code, guest["token"]).status_code == 404

    started = api.start_reveal(code, host["token"])
    assert started.status_code == 200
    state = started.json()
    assert state["phase"] == "reveal_drawing"
    assert state["total_players"] == 2
    assert state["current_index"] == 0
    assert state["original_revealed"] is False
    assert state["current_player"]["drawing_data"]["strokes"]

    serialized = json.dumps(state)
    assert "reveal_order" not in serialized
    assert "reference_image_id" not in serialized
    assert "storage_key" not in serialized

    with SessionLocal() as db:
        reveal = db.scalar(
            select(Reveal).where(Reveal.game_id == UUID(state["game_id"]))
        )
        assert reveal is not None
        assert len(reveal.reveal_order) == 2
        assert len(set(reveal.reveal_order)) == 2
        assert str(state["current_player"]["player_id"]) == reveal.reveal_order[0]

    guest_view = api.get_reveal(code, guest["token"])
    assert guest_view.status_code == 200
    assert (
        guest_view.json()["current_player"]["player_id"]
        == state["current_player"]["player_id"]
    )

    assert api.save_drawing(code, host["token"]).status_code == 409
    assert api.submit_drawing(code, host["token"]).status_code == 409
    assert api.unsubmit_drawing(code, host["token"]).status_code == 409

    original_before = api.get_reveal_reference(code, guest["token"])
    assert original_before.status_code == 403

    guest_original = api.reveal_original(code, guest["token"])
    assert guest_original.status_code == 403
    guest_next = api.next_reveal(code, guest["token"])
    assert guest_next.status_code == 403

    original_state = api.reveal_original(code, host["token"])
    assert original_state.status_code == 200
    assert original_state.json()["phase"] == "reveal_original"
    assert original_state.json()["original_revealed"] is True

    original_content = api.get_reveal_reference(code, guest["token"])
    assert original_content.status_code == 200
    assert original_content.content == image

    second_drawing = api.next_reveal(code, host["token"])
    assert second_drawing.status_code == 200
    assert second_drawing.json()["phase"] == "reveal_drawing"
    assert second_drawing.json()["current_index"] == 1
    assert second_drawing.json()["original_revealed"] is False
    assert api.get_reveal_reference(code, guest["token"]).status_code == 403

    second_original = api.reveal_original(code, host["token"])
    assert second_original.status_code == 200
    final_state = api.next_reveal(code, host["token"])
    assert final_state.status_code == 200
    assert final_state.json()["phase"] == "results_completed"
    assert final_state.json()["current_player"] is None

    with SessionLocal() as db:
        room = db.scalar(select(Room).where(Room.join_code == code))
        assert room is not None
        assert room.status == RoomStatus.COMPLETED
        assert room.expires_at is not None
        assert room.expires_at > datetime.now(timezone.utc) + timedelta(
            hours=23
        )

    reconnect_client = TestClient(api.client.app)
    reconnected = reconnect_client.get(
        f"/api/rooms/{code}/reveal", headers=api.auth(guest["token"])
    )
    assert reconnected.status_code == 200
    assert reconnected.json()["phase"] == "results_completed"

    assert api.next_reveal(code, host["token"]).status_code == 409
    assert api.reveal_original(code, host["token"]).status_code == 409


def test_random_reveal_original_matches_current_assignment(api):
    host, _guest, _first_image = complete_game(api, mode="random_assignment")
    code = host["room"]["code"]

    started = api.start_reveal(code, host["token"])
    assert started.status_code == 200
    state = started.json()
    current_player_id = UUID(state["current_player"]["player_id"])

    with SessionLocal() as db:
        assignment = db.scalar(
            select(Assignment).where(
                Assignment.game_id == UUID(state["game_id"]),
                Assignment.player_id == current_player_id,
            )
        )
        assert assignment is not None
        image = db.get(ReferenceImage, assignment.reference_image_id)
        assert image is not None
        expected = (
            Path(get_settings().upload_dir) / image.storage_key
        ).read_bytes()

    assert api.get_reveal_reference(code, host["token"]).status_code == 403
    revealed = api.reveal_original(code, host["token"])
    assert revealed.status_code == 200
    original = api.get_reveal_reference(code, host["token"])
    assert original.status_code == 200
    assert original.content == expected
