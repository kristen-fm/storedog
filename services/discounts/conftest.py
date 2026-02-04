# conftest.py
import os
import sys
import importlib
import pytest
from unittest.mock import patch, Mock


@pytest.fixture()
def client(monkeypatch):
    """
    Provides a Flask test client for the discounts app, while ensuring:
    - POSTGRES_* env vars exist before importing discounts.py
    - bootstrap.db is patched during the import to prevent real DB init
    - discounts module is imported fresh (important under pytest collection)
    """
    # Ensure env vars exist before importing discounts.py
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("POSTGRES_HOST", "test_host")

    # Ensure we're importing the local module
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # If discounts was already imported for any reason, reload cleanly
    sys.modules.pop("discounts", None)

    # Patch bootstrap.db during import of discounts
    with patch("bootstrap.db") as mock_db:
        mock_db.init_app = Mock()
        mock_db.drop_all = Mock()
        mock_db.create_all = Mock()
        mock_db.session = Mock()

        discounts_module = importlib.import_module("discounts")
        app = discounts_module.app

    test_client = app.test_client()
    app.testing = True
    return test_client
