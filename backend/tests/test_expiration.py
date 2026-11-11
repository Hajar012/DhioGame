from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    Drawing,
    Game,
    ReferenceImage,
    Reveal,
    Room,
)
from app.services.expiration import cleanup_expired_rooms


def test_expired_room_deletes_database_rows_and_uploaded_files(api):
    host = api.create_room(
        "ExpireHost",
        {
            "mode": "same_image",
            "viewing_duration_seconds": 60,
            "drawing_duration_seconds": 180,
        },
    )
    code = host["room"]["code"]
    guest = api.join(code, "ExpireGuest")
    api.upload(code, host["token"], api.image_bytes((15, 120, 90)))
    started = api.start_game(code, host["token"])
    api.advance_to_drawing(code, host["token"])
    assert api.save_drawing(code, host["token"]).status_code == 200
    assert api.save_drawing(code, guest["token"]).status_code == 200

    keep_room = api.create_room("KeepHost")

    with SessionLocal() as session:
        room = session.scalar(select(Room).where(Room.join_code == code))
        assert room is not None
        room.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        room_id = room.id
        storage_key = session.scalar(
            select(ReferenceImage.storage_key).where(
                ReferenceImage.room_id == room_id
            )
        )
        session.commit()

    stored_path = Path(get_settings().upload_dir) / storage_key
    room_directory = Path(get_settings().upload_dir) / str(room_id)
    assert stored_path.is_file()
    assert room_directory.is_dir()

    with SessionLocal() as session:
        deleted = cleanup_expired_rooms(session)
    assert deleted >= 1

    with SessionLocal() as session:
        assert session.get(Room, room_id) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(Game)
                .where(Game.id == UUID(started["id"]))
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Drawing)
                .where(Drawing.game_id == UUID(started["id"]))
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReferenceImage)
                .where(ReferenceImage.room_id == room_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Reveal)
                .where(Reveal.game_id == UUID(started["id"]))
            )
            == 0
        )
        assert (
            session.scalar(
                select(Room).where(
                    Room.join_code == keep_room["room"]["code"]
                )
            )
            is not None
        )

    assert not stored_path.exists()
    assert not room_directory.exists() or not any(room_directory.iterdir())
