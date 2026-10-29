import pytest

from swarm import store


@pytest.fixture(autouse=True)
def saved_runs_in_tmp(tmp_path, monkeypatch):
    """Tests never write saved runs into the repo."""
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "data")
