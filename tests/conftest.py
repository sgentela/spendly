import pytest
import database.db as _db
from app import app as flask_app
from database.db import init_db


@pytest.fixture
def app(tmp_path):
    original_path = _db.DB_PATH
    _db.DB_PATH = str(tmp_path / "test.db")
    flask_app.config.update({
        "TESTING":          True,
        "SECRET_KEY":       "test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    with flask_app.app_context():
        init_db()
        yield flask_app
    _db.DB_PATH = original_path


@pytest.fixture
def client(app):
    return app.test_client()
