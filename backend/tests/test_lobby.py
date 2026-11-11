from __future__ import annotations


def test_room_creation_join_readiness_settings_and_uploads(api):
    host = api.create_room("HostPlayer")
    code = host["room"]["code"]

    state = api.get_room(code, host["token"])
    assert state["player_count"] == 1
    assert state["status"] == "waiting"
    assert state["can_start"] is False

    missing_token = api.client.get(f"/api/rooms/{code}")
    assert missing_token.status_code == 401
    bad_token = api.client.get(
        f"/api/rooms/{code}", headers=api.auth("invalid")
    )
    assert bad_token.status_code == 401

    guest = api.join(code, "GuestPlayer")
    duplicate = api.client.post(
        "/api/rooms/join",
        json={"room_code": code, "nickname": "guestplayer"},
    )
    assert duplicate.status_code == 409

    ready = api.client.post(
        f"/api/rooms/{code}/ready",
        headers=api.auth(guest["token"]),
        json={"is_ready": True},
    )
    assert ready.status_code == 200
    assert ready.json()["ready_count"] == 1

    guest_settings = api.client.patch(
        f"/api/rooms/{code}/settings",
        headers=api.auth(guest["token"]),
        json={"viewing_duration_seconds": 30},
    )
    assert guest_settings.status_code == 403

    host_settings = api.client.patch(
        f"/api/rooms/{code}/settings",
        headers=api.auth(host["token"]),
        json={
            "viewing_duration_seconds": 30,
            "drawing_duration_seconds": None,
        },
    )
    assert host_settings.status_code == 200
    assert host_settings.json()["settings"]["viewing_duration_seconds"] == 30
    assert host_settings.json()["settings"]["drawing_duration_seconds"] is None

    invalid_settings = api.client.patch(
        f"/api/rooms/{code}/settings",
        headers=api.auth(host["token"]),
        json={"viewing_duration_seconds": 15},
    )
    assert invalid_settings.status_code == 422

    guest_upload = api.client.post(
        f"/api/rooms/{code}/images",
        headers=api.auth(guest["token"]),
        files={"file": ("ref.png", api.image_bytes(), "image/png")},
    )
    assert guest_upload.status_code == 403

    bad_type = api.client.post(
        f"/api/rooms/{code}/images",
        headers=api.auth(host["token"]),
        files={"file": ("ref.txt", b"not an image", "text/plain")},
    )
    assert bad_type.status_code == 400

    oversized = api.client.post(
        f"/api/rooms/{code}/images",
        headers=api.auth(host["token"]),
        files={
            "file": (
                "huge.png",
                b"x" * (5 * 1024 * 1024 + 1),
                "image/png",
            )
        },
    )
    assert oversized.status_code == 400

    first_upload = api.upload(code, host["token"])
    assert first_upload["room"]["uploaded_images"] == 1
    assert first_upload["room"]["can_start"] is True

    extra_upload = api.client.post(
        f"/api/rooms/{code}/images",
        headers=api.auth(host["token"]),
        files={"file": ("extra.png", api.image_bytes((10, 10, 10)), "image/png")},
    )
    assert extra_upload.status_code == 409


def test_room_player_limit(api):
    host = api.create_room("LimitHost")
    code = host["room"]["code"]

    for index in range(9):
        api.join(code, f"LimitGuest{index}")

    overflow = api.client.post(
        "/api/rooms/join",
        json={"room_code": code, "nickname": "OverflowPlayer"},
    )
    assert overflow.status_code == 409
