"""Shared pytest fixtures for CASCADE Enterprise Python tests.

Provides temp directories, config objects, and test helpers for
testing RAM disk manager components without touching real filesystems.
"""

import json
import shutil
from pathlib import Path

import pytest

from ram_disk_manager.config import RamDiskConfig, ManagerConfig, SyncStrategy, Platform


@pytest.fixture
def tmp_dirs(tmp_path):
    """Create temporary disk_path and ram_path directories for testing."""
    disk_path = tmp_path / "disk"
    ram_path = tmp_path / "ram"
    disk_path.mkdir()
    ram_path.mkdir()
    return {"disk": disk_path, "ram": ram_path, "root": tmp_path}


@pytest.fixture
def sample_config(tmp_dirs):
    """Create a sample RamDiskConfig with temp directories."""
    return RamDiskConfig(
        name="test_disk",
        disk_path=tmp_dirs["disk"],
        ram_path=tmp_dirs["ram"],
        size_mb=64,
        sync_strategy=SyncStrategy.FULL,
        auto_sync_on_startup=False,
        persist_on_shutdown=True,
        verify_integrity=True,
    )


@pytest.fixture
def sample_manager_config():
    """Create a sample ManagerConfig."""
    return ManagerConfig(
        platform=Platform.AUTO,
        enable_dual_write=True,
        recovery_marker_file=".test_clean_shutdown",
    )


@pytest.fixture
def populated_dirs(tmp_dirs):
    """Create temp directories with sample files for sync tests."""
    disk = tmp_dirs["disk"]

    # Create sample files on disk (truth)
    (disk / "file1.txt").write_text("hello world")
    (disk / "file2.json").write_text(json.dumps({"key": "value"}))
    (disk / "subdir").mkdir()
    (disk / "subdir" / "nested.txt").write_text("nested content")
    (disk / "data.bin").write_bytes(b"\x00\x01\x02\x03" * 100)

    return tmp_dirs


@pytest.fixture
def dual_write_config(tmp_dirs):
    """Config specifically for DualWriteController tests."""
    return RamDiskConfig(
        name="dual_write_test",
        disk_path=tmp_dirs["disk"],
        ram_path=tmp_dirs["ram"],
        size_mb=32,
        sync_strategy=SyncStrategy.FULL,
    )
