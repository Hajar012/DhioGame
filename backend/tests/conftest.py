from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ENV_PATH = REPO_ROOT / ".env"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
elif not os.environ.get("DATABASE_URL") and ENV_PATH.exists():
    env_values = dotenv_values(ENV_PATH)
    if env_values.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = env_values["DATABASE_URL"]

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models import Room
from tests.helpers import GameApi


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def created_room_codes():
    codes: list[str] = []
    yield codes

    if not codes:
        return

    with SessionLocal() as session:
        rooms = session.scalars(
            select(Room).where(Room.join_code.in_(set(codes)))
        ).all()
        room_ids = [room.id for room in rooms]
        for room in rooms:
            session.delete(room)
        session.commit()

    upload_root = Path(get_settings().upload_dir)
    for room_id in room_ids:
        directory = upload_root / str(room_id)
        shutil.rmtree(directory, ignore_errors=True)
        if directory.exists():
            try:
                directory.rmdir()
            except OSError:
                pass


@pytest.fixture()
def api(client, created_room_codes):
    return GameApi(client, created_room_codes)
