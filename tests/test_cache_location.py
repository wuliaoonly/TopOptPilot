from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from topoptpilot.service import ResearchService


def test_default_cache_dir_is_inside_data_dir():
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        assert service.cache_dir == (Path(directory) / "cache").resolve()


def test_setting_cache_dir_migrates_existing_entries():
    with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as target:
        service = ResearchService(data, max_workers=1)
        service.cache.put({"task": "migrate-me"}, {"result": "ok"})
        default_entry = next((Path(service.cache_dir)).glob("*.json"))
        result = service.update_settings({"data": {"cache_dir": target}})
        assert result["data"]["cache_dir"] == str(Path(target).resolve())
        assert result["data"]["cache_migration"]["moved_files"] == 1
        assert service.cache_dir == Path(target).resolve()
        assert not default_entry.exists()
        assert (Path(target) / default_entry.name).exists()
        assert service.cache.get({"task": "migrate-me"}) == {"result": "ok"}


def test_cache_dir_setting_survives_restart():
    with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as target:
        ResearchService(data, max_workers=1).update_settings({"data": {"cache_dir": target}})
        relaunched = ResearchService(data, max_workers=1)
        assert relaunched.cache_dir == Path(target).resolve()
        assert relaunched.get_settings()["data"]["cache_dir"] == str(Path(target).resolve())


def test_invalid_cache_dir_is_rejected_without_migration():
    with tempfile.TemporaryDirectory() as data:
        service = ResearchService(data, max_workers=1)
        service.cache.put({"task": "keep"}, {"result": "ok"})
        original_dir = service.cache_dir
        with pytest.raises(ValueError):
            service.update_settings({"data": {"cache_dir": str(Path(data) / "missing-dir")}})
        assert service.cache_dir == original_dir
        assert service.cache.get({"task": "keep"}) == {"result": "ok"}
        assert service.get_settings()["data"]["cache_dir"] is None


def test_cache_dir_cannot_be_the_data_root():
    with tempfile.TemporaryDirectory() as data:
        service = ResearchService(data, max_workers=1)
        with pytest.raises(ValueError):
            service.update_settings({"data": {"cache_dir": data}})


def test_clearing_cache_dir_migrates_back_to_default():
    with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as target:
        service = ResearchService(data, max_workers=1)
        service.update_settings({"data": {"cache_dir": target}})
        service.cache.put({"task": "round-trip"}, {"result": "ok"})
        entry = next(Path(target).glob("*.json"))
        result = service.update_settings({"data": {"cache_dir": ""}})
        assert result["data"]["cache_dir"] is None
        assert result["data"]["cache_migration"]["moved_files"] == 1
        assert service.cache_dir == (Path(data) / "cache").resolve()
        assert (Path(data) / "cache" / entry.name).exists()
        assert service.cache.get({"task": "round-trip"}) == {"result": "ok"}


def test_clear_regenerable_cache_uses_custom_dir_without_touching_data_dir():
    with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as target:
        service = ResearchService(data, max_workers=1)
        service.update_settings({"data": {"cache_dir": target}})
        service.cache.put({"task": "purge"}, {"result": "ok"})
        marker = Path(data) / "research.db"
        result = service.clear_regenerable_cache()
        assert result["removed_entries"] >= 1
        assert not list(Path(target).glob("*.json"))
        assert marker.exists()
