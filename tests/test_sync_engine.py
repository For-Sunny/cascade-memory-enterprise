"""Tests for ram_disk_manager.sync.engine module.

Validates SyncEngine: disk-to-RAM sync, RAM-to-disk sync, incremental sync,
hash-based change detection, and integrity verification.
"""

import json
import shutil
from pathlib import Path

import pytest

from ram_disk_manager.config import RamDiskConfig, SyncStrategy
from ram_disk_manager.sync.engine import SyncEngine, SyncStats


class TestSyncStats:
    """Test SyncStats dataclass."""

    def test_defaults(self):
        s = SyncStats()
        assert s.success is True
        assert s.files_copied == 0
        assert s.files_failed == 0
        assert s.duration_ms == 0.0

    def test_to_dict(self):
        s = SyncStats(files_copied=5, bytes_copied=1024)
        d = s.to_dict()
        assert d["files_copied"] == 5
        assert d["bytes_copied"] == 1024
        assert "success" in d


class TestSyncEngineDiskToRam:
    """Test disk-to-RAM sync operations."""

    def test_full_sync(self, populated_dirs):
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
            sync_strategy=SyncStrategy.FULL,
            verify_integrity=False,
        )
        engine = SyncEngine(config)
        stats = engine.disk_to_ram()

        assert stats.success is True
        assert stats.direction == "disk_to_ram"
        assert stats.files_copied > 0
        assert stats.bytes_copied > 0
        assert stats.duration_ms > 0

        # Verify files actually exist in RAM
        assert (populated_dirs["ram"] / "file1.txt").exists()
        assert (populated_dirs["ram"] / "file2.json").exists()
        assert (populated_dirs["ram"] / "subdir" / "nested.txt").exists()

    def test_incremental_sync(self, populated_dirs):
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
            sync_strategy=SyncStrategy.INCREMENTAL,
            verify_integrity=False,
        )
        # Store hash cache outside the synced directory to avoid it being
        # picked up as a file change on second sync
        hash_cache = populated_dirs["root"] / ".hash_cache.json"
        engine = SyncEngine(config, hash_cache_path=hash_cache)

        # First sync - everything is new
        stats1 = engine.disk_to_ram()
        assert stats1.success is True
        assert stats1.files_copied > 0

        # Second sync - nothing changed
        stats2 = engine.disk_to_ram()
        assert stats2.success is True
        assert stats2.files_copied == 0
        assert stats2.files_unchanged > 0

    def test_incremental_detects_changes(self, populated_dirs):
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
            sync_strategy=SyncStrategy.INCREMENTAL,
            verify_integrity=False,
        )
        engine = SyncEngine(config)

        # Initial sync
        engine.disk_to_ram()

        # Modify a file on disk
        (populated_dirs["disk"] / "file1.txt").write_text("MODIFIED")

        # Incremental should detect the change
        stats = engine.disk_to_ram()
        assert stats.success is True
        assert stats.files_copied >= 1

        # Verify the RAM copy was updated
        assert (populated_dirs["ram"] / "file1.txt").read_text() == "MODIFIED"

    def test_force_full_overrides_strategy(self, populated_dirs):
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
            sync_strategy=SyncStrategy.INCREMENTAL,
            verify_integrity=False,
        )
        engine = SyncEngine(config)
        stats = engine.disk_to_ram(force_full=True)
        assert stats.strategy == "full"
        assert stats.success is True

    def test_no_ram_path_fails(self, tmp_path):
        config = RamDiskConfig(
            name="test",
            disk_path=tmp_path,
            ram_path=None,
        )
        engine = SyncEngine(config)
        stats = engine.disk_to_ram()
        assert stats.success is False
        assert "RAM path not configured" in stats.errors[0]

    def test_missing_disk_path_fails(self, tmp_path):
        config = RamDiskConfig(
            name="test",
            disk_path=tmp_path / "nonexistent",
            ram_path=tmp_path / "ram",
        )
        engine = SyncEngine(config)
        stats = engine.disk_to_ram()
        assert stats.success is False
        assert "does not exist" in stats.errors[0]


class TestSyncEngineRamToDisk:
    """Test RAM-to-disk sync (persistence)."""

    def test_persist_ram_changes(self, populated_dirs):
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
            verify_integrity=False,
        )
        engine = SyncEngine(config)

        # Initial sync disk -> RAM
        engine.disk_to_ram()

        # Create new file in RAM
        (populated_dirs["ram"] / "new_file.txt").write_text("created in RAM")

        # Sync RAM -> disk
        stats = engine.ram_to_disk()
        assert stats.success is True
        assert stats.direction == "ram_to_disk"

        # Verify new file persisted to disk
        assert (populated_dirs["disk"] / "new_file.txt").read_text() == "created in RAM"

    def test_no_ram_path_fails(self, tmp_path):
        config = RamDiskConfig(
            name="test",
            disk_path=tmp_path,
            ram_path=None,
        )
        engine = SyncEngine(config)
        stats = engine.ram_to_disk()
        assert stats.success is False

    def test_missing_ram_fails(self, tmp_path):
        config = RamDiskConfig(
            name="test",
            disk_path=tmp_path,
            ram_path=tmp_path / "nonexistent_ram",
        )
        engine = SyncEngine(config)
        stats = engine.ram_to_disk()
        assert stats.success is False


class TestSyncEngineStatus:
    """Test sync status reporting."""

    def test_in_sync_status(self, populated_dirs):
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
            verify_integrity=False,
        )
        # Store hash cache outside synced dirs so it doesn't create
        # a difference between disk and RAM
        hash_cache = populated_dirs["root"] / ".hash_cache.json"
        engine = SyncEngine(config, hash_cache_path=hash_cache)
        engine.disk_to_ram(force_full=True)

        status = engine.get_sync_status()
        assert status["disk_exists"] is True
        assert status["ram_exists"] is True
        assert status["in_sync"] is True

    def test_out_of_sync_status(self, populated_dirs):
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
        )
        engine = SyncEngine(config)

        # Don't sync - should be out of sync
        status = engine.get_sync_status()
        assert status["in_sync"] is False
        assert status["differences"] is not None
        assert len(status["differences"]["disk_only"]) > 0

    def test_status_missing_ram(self, tmp_path):
        disk = tmp_path / "disk"
        disk.mkdir()
        config = RamDiskConfig(
            name="test",
            disk_path=disk,
            ram_path=tmp_path / "nonexistent_ram",
        )
        engine = SyncEngine(config)
        status = engine.get_sync_status()
        assert status["ram_exists"] is False
        assert status["in_sync"] is False
