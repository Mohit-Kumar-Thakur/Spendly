"""Test fixtures for Spendly.

app.py runs init_db() and seed_db() at import time, so DB_PATH has to be
redirected at a temp file *before* app is imported. get_db() reads the
module global at call time, which makes monkeypatching it enough.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app(tmp_path, monkeypatch):
    import database.db as db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))

    # Drop the cached module so its import-time init_db()/seed_db() run
    # again, this time against the temp database.
    sys.modules.pop("app", None)
    import app as app_module

    app_module.app.config.update(TESTING=True)
    yield app_module.app

    sys.modules.pop("app", None)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def query(app):
    """Run a read-only query against the temp database."""
    import database.db as db

    def run(sql, params=()):
        conn = db.get_db()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    return run
