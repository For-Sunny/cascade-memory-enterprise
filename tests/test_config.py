"""Tests for ram_disk_manager.config module.

Validates configuration dataclasses, enums, path coercion, and defaults.
"""

from pathlib import Path

import pytest

from ram_disk_manager.config import (
    RamDiskConfig,
    ManagerConfig,
    SyncStrategy,
    Platform,
)


class TestSyncStrategy:
    """Verify SyncStrategy enum values."""

    def test_full_value(self):
        assert SyncStrategy.FULL.value == "full"

    def test_incremental_value(self):
        assert SyncStrategy.INCREMENTAL.value == "incremental"

    def test_pattern_value(self):
        assert SyncStrategy.PATTERN.value == "pattern"

    def test_from_string(self):
        assert SyncStrategy("full") == SyncStrategy.FULL
        assert SyncStrategy("incremental") == SyncStrategy.INCREMENTAL

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            SyncStrategy("nonexistent")


class TestPlatform:
    """Verify Platform enum values."""

    def test_values(self):
        assert Platform.WINDOWS.value == "windows"
        assert Platform.LINUX.value == "linux"
        assert Platform.MACOS.value == "darwin"
        assert Platform.AUTO.value == "auto"


class TestRamDiskConfig:
    """Test RamDiskConfig dataclass behavior."""

    def test_minimal_creation(self, tmp_path):
        config = RamDiskConfig(name="test", disk_path=tmp_path)
        assert config.name == "test"
        assert config.disk_path == tmp_path
        assert config.ram_path is None
        assert config.size_mb == 512
        assert config.patterns == ["*"]
        assert config.sync_strategy == SyncStrategy.FULL
        assert config.auto_sync_on_startup is True
        assert config.persist_on_shutdown is True
        assert config.verify_integrity is True

    def test_string_path_coercion(self):
        """Paths passed as strings should be converted to Path objects."""
        config = RamDiskConfig(
            name="test",
            disk_path="/some/path",
            ram_path="/ram/path",
        )
        assert isinstance(config.disk_path, Path)
        assert isinstance(config.ram_path, Path)
        # On Windows, Path("/some/path") becomes "\\some\\path"
        assert config.disk_path == Path("/some/path")

    def test_path_objects_unchanged(self, tmp_path):
        """Paths passed as Path objects should remain unchanged."""
        config = RamDiskConfig(name="test", disk_path=tmp_path)
        assert config.disk_path is tmp_path

    def test_custom_values(self, tmp_path):
        config = RamDiskConfig(
            name="custom",
            disk_path=tmp_path / "disk",
            ram_path=tmp_path / "ram",
            size_mb=128,
            patterns=["*.db", "*.json"],
            sync_strategy=SyncStrategy.INCREMENTAL,
            auto_sync_on_startup=False,
            persist_on_shutdown=False,
            verify_integrity=False,
        )
        assert config.size_mb == 128
        assert config.patterns == ["*.db", "*.json"]
        assert config.sync_strategy == SyncStrategy.INCREMENTAL
        assert config.auto_sync_on_startup is False


class TestManagerConfig:
    """Test ManagerConfig dataclass behavior."""

    def test_defaults(self):
        config = ManagerConfig()
        assert config.platform == Platform.AUTO
        assert config.base_ram_path is None
        assert config.log_file is None
        assert config.enable_dual_write is True
        assert config.recovery_marker_file == ".ram_disk_clean_shutdown"

    def test_string_path_coercion(self):
        config = ManagerConfig(
            base_ram_path="/ram",
            log_file="/var/log/ramdisk.log",
        )
        assert isinstance(config.base_ram_path, Path)
        assert isinstance(config.log_file, Path)

    def test_custom_marker(self):
        config = ManagerConfig(recovery_marker_file=".custom_marker")
        assert config.recovery_marker_file == ".custom_marker"
