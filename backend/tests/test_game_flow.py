from __future__ import annotations

import json
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Assignment, Drawing, DrawingStatus


def setup_same_image_game(api):
    host = api.create_room(
        "GameHost",
        {
            "mode": "same_image",
            "viewing_duration_seconds": 60,
            "drawing_duration_seconds": 180,
        },
    )
    guest = api.join(host["room"]["code"], "GameGuest")
    image = api.image_bytes((210, 90, 60))
    api.upload(host["room"]["code"], host["token"], image)
    started = api.start_game(host["room"]["code"], host["token"])
    return host, guest, image, started


def test_same_image_references_submissions_reconnection_and_deadline(api):
    host, guest, image, started = setup_same_image_game(api)
    code = host["room"]["code"]
    game_id = started["id"]
    assert started["phase"] == "image_viewing"

    public_state = json.dumps(api.get_game(code, host["token"]))
    assert "storage_key" not in public_state
    assert "reference_image_id" not in public_state
    assert "reveal_order" not in public_state

    host_reference = api.get_reference(code, host["token"])
    guest_reference = api.get_reference(code, guest["token"])
    assert host_reference.status_code == 200
    assert guest_reference.status_code == 200
    assert host_reference.content == guest_reference.content == image

    reconnect_client = TestClient(api.client.app)
    reconnect_reference = reconnect_client.get(
        f"/api/rooms/{code}/game/reference",
        headers=api.auth(host["token"]),
    )
    assert reconnect_reference.status_code == 200
    assert reconnect_reference.content == image

    drawing_state = api.advance_to_drawing(code, host["token"])
    deadline = drawing_state["phase_ends_at"]
    assert api.get_reference(code, host["token"]).status_code == 403

    assert api.get_drawing(code, host["token"])["can_edit"] is True
    assert api.save_drawing(code, host["token"]).status_code == 200
    assert api.submit_drawing(code, host["token"]).status_code == 200
    assert api.save_drawing(code, host["token"]).status_code == 409

    reopened = api.unsubmit_drawing(code, host["token"])
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "draft"
    assert api.save_drawing(
        code, host["token"], api.drawing_payload(25)
    ).status_code == 200
    assert api.submit_drawing(code, host["token"]).status_code == 200

    assert api.save_drawing(
        code, guest["token"], api.drawing_payload(50)
    ).status_code == 200
    assert api.submit_drawing(code, guest["token"]).status_code == 200

    progress = api.get_game(code, guest["token"])
    assert progress["submitted_count"] == 2

    restored_drawing = reconnect_client.get(
        f"/api/rooms/{code}/drawing",
        headers=api.auth(host["token"]),
    )
    assert restored_drawing.status_code == 200
    assert restored_drawing.json()["status"] == "submitted"
    assert (
        restored_drawing.json()["data"]["strokes"][0]["points"][1]["x"]
        == 225
    )

    restored_game = reconnect_client.get(
        f"/api/rooms/{code}/game", headers=api.auth(host["token"])
    ).json()
    assert restored_game["phase_ends_at"] == deadline

    completed = api.finish_drawing_phase(code, host["token"])
    assert completed["drawings_locked"] is True
    assert api.save_drawing(code, host["token"]).status_code == 409
    assert api.submit_drawing(code, host["token"]).status_code == 409
    assert api.unsubmit_drawing(code, host["token"]).status_code == 409
    assert api.get_drawing(code, host["token"])["status"] == "locked"
    assert completed["id"] == game_id


def test_random_assignment_privacy_and_image_count_validation(api):
    host = api.create_room(
        "RandomHost",
        {
            "mode": "random_assignment",
            "viewing_duration_seconds": 60,
            "drawing_duration_seconds": 180,
        },
    )
    code = host["room"]["code"]
    guest = api.join(code, "RandomGuest")
    red = api.image_bytes((220, 40, 40))
    blue = api.image_bytes((40, 80, 220))

    api.upload(code, host["token"], red, filename="red.png")
    not_enough = api.client.post(
        f"/api/rooms/{code}/game/start",
        headers=api.auth(host["token"]),
    )
    assert not_enough.status_code == 409

    api.upload(code, host["token"], blue, filename="blue.png")
    started = api.start_game(code, host["token"])
    assert started["mode"] == "random_assignment"

    late_join = api.client.post(
        "/api/rooms/join",
        json={"room_code": code, "nickname": "LatePlayer"},
    )
    assert late_join.status_code == 409

    host_reference = api.get_reference(code, host["token"])
    guest_reference = api.get_reference(code, guest["token"])
    assert host_reference.status_code == 200
    assert guest_reference.status_code == 200
    assert host_reference.content in {red, blue}
    assert guest_reference.content in {red, blue}
    assert host_reference.content != guest_reference.content

    public_state = json.dumps(api.get_game(code, guest["token"]))
    assert "storage_key" not in public_state
    assert "reference_image_id" not in public_state
    assert "reveal_order" not in public_state

    with SessionLocal() as db:
        assignments = db.scalars(
            select(Assignment).where(
                Assignment.game_id == UUID(started["id"])
            )
        ).all()
        assert len(assignments) == 2
        assert len({assignment.reference_image_id for assignment in assignments}) == 2


def test_unlimited_drawing_and_host_finish(api):
    host = api.create_room(
        "UnlimitedHost",
        {
            "mode": "same_image",
            "viewing_duration_seconds": 60,
            "drawing_duration_seconds": None,
        },
    )
    code = host["room"]["code"]
    guest = api.join(code, "UnlimitedGuest")
    api.upload(code, host["token"])
    api.start_game(code, host["token"])
    drawing = api.advance_to_drawing(code, host["token"])
    assert drawing["phase_ends_at"] is None
    assert api.get_drawing(code, guest["token"])["can_edit"] is True

    guest_finish = api.client.post(
        f"/api/rooms/{code}/game/finish-drawing",
        headers=api.auth(guest["token"]),
    )
    assert guest_finish.status_code == 403

    completed = api.finish_drawing(code, host["token"])
    assert completed["phase"] == "drawing_completed"
    assert completed["drawings_locked"] is True

    with SessionLocal() as db:
        drawings = db.scalars(
            select(Drawing).where(Drawing.game_id == UUID(drawing["id"]))
        ).all()
        assert drawings
        assert all(item.status == DrawingStatus.LOCKED for item in drawings)


def test_websocket_game_updates(api):
    host = api.create_room(
        "SocketHost",
        {
            "mode": "same_image",
            "viewing_duration_seconds": 60,
            "drawing_duration_seconds": 180,
        },
    )
    code = host["room"]["code"]
    guest = api.join(code, "SocketGuest")
    api.upload(code, host["token"])

    with api.client.websocket_connect(
        f"/api/ws/rooms/{code}?token={guest['token']}"
    ) as socket:
        message = socket.receive_json()
        while message["type"] != "lobby_state":
            message = socket.receive_json()

        api.start_game(code, host["token"])
        message = socket.receive_json()
        while message["type"] != "game_state":
            message = socket.receive_json()
        assert message["state"]["phase"] == "image_viewing"

        api.advance_to_drawing(code, host["token"])
        message = socket.receive_json()
        while message["type"] != "game_state":
            message = socket.receive_json()
        assert message["state"]["phase"] == "drawing"

        api.save_drawing(code, guest["token"])
        api.submit_drawing(code, guest["token"])
        message = socket.receive_json()
        while (
            message["type"] != "game_state"
            or message["state"]["submitted_count"] != 1
        ):
            message = socket.receive_json()
        assert message["state"]["submitted_count"] == 1
