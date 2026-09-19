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


@pytest.fixture(autouse=True)
def _push_request_context():
    """Disable pytest-flask's whole-test request context.

    pytest-flask pushes one test_request_context() for the duration of any
    test that uses the `app` fixture. Flask only creates a new application
    context if one is not already on the stack, so every request made by
    the test client then reuses that outer context — and with it, one
    shared `g`.

    current_user() caches the resolved user on `g` deliberately, so that
    sharing makes one request's answer stick for the rest of the test:
    two test clients in the same test see each other's user, or each
    other's "nobody". In a real process each request gets its own `g` and
    none of that can happen, so the fixture is papering a hole into the
    tests rather than out of them. Overriding it by name is the supported
    way to opt out.
    """
    yield


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
