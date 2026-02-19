"""Tests for ram_disk_manager.recovery module.

Validates crash detection, integrity verification, and automatic recovery.
"""

import json
from pathlib import Path

import pytest

from ram_disk_manager.config import RamDiskConfig, ManagerConfig
from ram_disk_manager.recovery.detector import (
    was_clean_shutdown,
    mark_clean_shutdown,
    clear_shutdown_marker,
    get_shutdown_info,
)
from ram_disk_manager.recovery.integrity import (
    verify_integrity,
    verify_single_file,
    IntegrityResult,
)
from ram_disk_manager.recovery.auto_sync import RecoveryManager, RecoveryResult


class TestShutdownDetector:
    """Test crash detection via shutdown marker files."""

    def test_no_marker_means_crash(self, sample_config):
        """Missing marker should indicate a crash."""
        assert was_clean_shutdown(sample_config) is False

    def test_mark_and_detect_clean_shutdown(self, sample_config):
        """Writing marker should indicate clean shutdown on next check."""
        assert mark_clean_shutdown(sample_config) is True
        assert was_clean_shutdown(sample_config) is True

    def test_clear_marker(self, sample_config):
        """Clearing marker should make next check return False (crash)."""
        mark_clean_shutdown(sample_config)
        assert was_clean_shutdown(sample_config) is True
        assert clear_shutdown_marker(sample_config) is True
        assert was_clean_shutdown(sample_config) is False

    def test_corrupted_marker(self, sample_config):
        """Corrupted marker file should be treated as crash."""
        marker_path = sample_config.disk_path / ".ram_disk_clean_shutdown"
        marker_path.write_text("not valid json {{{")
        assert was_clean_shutdown(sample_config) is False

    def test_marker_missing_required_field(self, sample_config):
        """Marker without 'clean_shutdown' key should be treated as crash."""
        marker_path = sample_config.disk_path / ".ram_disk_clean_shutdown"
        marker_path.write_text(json.dumps({"timestamp": "2025-01-01"}))
        assert was_clean_shutdown(sample_config) is False

    def test_marker_with_false_value(self, sample_config):
        """Marker with clean_shutdown=false should indicate crash."""
        marker_path = sample_config.disk_path / ".ram_disk_clean_shutdown"
        marker_path.write_text(json.dumps({"clean_shutdown": False}))
        assert was_clean_shutdown(sample_config) is False

    def test_get_shutdown_info(self, sample_config):
        """get_shutdown_info should return marker data."""
        mark_clean_shutdown(sample_config)
        info = get_shutdown_info(sample_config)
        assert info is not None
        assert info["clean_shutdown"] is True
        assert "timestamp" in info
        assert info["name"] == "test_disk"

    def test_get_shutdown_info_no_marker(self, sample_config):
        """get_shutdown_info should return None if no marker."""
        assert get_shutdown_info(sample_config) is None

    def test_custom_marker_filename(self, sample_config, sample_manager_config):
        """Custom marker filename from ManagerConfig should be used."""
        assert mark_clean_shutdown(sample_config, sample_manager_config) is True
        assert was_clean_shutdown(sample_config, sample_manager_config) is True

        # Verify it used the custom filename
        custom_marker = sample_config.disk_path / ".test_clean_shutdown"
        assert custom_marker.exists()

    def test_clear_nonexistent_marker_succeeds(self, sample_config):
        """Clearing a nonexistent marker should succeed (idempotent)."""
        assert clear_shutdown_marker(sample_config) is True


class TestIntegrityVerification:
    """Test hash-based integrity verification between disk and RAM."""

    def test_in_sync(self, populated_dirs):
        """Identical disk and RAM should verify clean."""
        import shutil

        disk = populated_dirs["disk"]
        ram = populated_dirs["ram"]

        # Copy all files from disk to RAM
        for item in disk.iterdir():
            if item.is_file():
                shutil.copy2(item, ram / item.name)
            elif item.is_dir():
                shutil.copytree(item, ram / item.name)

        config = RamDiskConfig(name="test", disk_path=disk, ram_path=ram)
        result = verify_integrity(config)
        assert result.is_valid is True
        assert result.needs_recovery is False
        assert len(result.mismatched_files) == 0
        assert len(result.missing_in_ram) == 0

    def test_missing_in_ram(self, populated_dirs):
        """Files on disk but not in RAM should be detected."""
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
        )
        result = verify_integrity(config)
        assert result.is_valid is False
        assert result.needs_recovery is True
        assert len(result.missing_in_ram) > 0

    def test_mismatched_content(self, populated_dirs):
        """Modified files should be detected as mismatched."""
        import shutil

        disk = populated_dirs["disk"]
        ram = populated_dirs["ram"]

        # Copy files
        for item in disk.iterdir():
            if item.is_file():
                shutil.copy2(item, ram / item.name)
            elif item.is_dir():
                shutil.copytree(item, ram / item.name)

        # Modify a file in RAM
        (ram / "file1.txt").write_text("MODIFIED CONTENT")

        config = RamDiskConfig(name="test", disk_path=disk, ram_path=ram)
        result = verify_integrity(config)
        assert result.is_valid is False
        assert "file1.txt" in result.mismatched_files

    def test_disk_path_missing(self, tmp_path):
        """Missing disk path should report error."""
        config = RamDiskConfig(
            name="test",
            disk_path=tmp_path / "nonexistent",
            ram_path=tmp_path / "ram",
        )
        result = verify_integrity(config)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_ram_path_missing(self, tmp_path):
        """Missing RAM path should report error."""
        disk = tmp_path / "disk"
        disk.mkdir()
        config = RamDiskConfig(
            name="test",
            disk_path=disk,
            ram_path=tmp_path / "nonexistent_ram",
        )
        result = verify_integrity(config)
        assert len(result.errors) > 0

    def test_verify_single_file(self, populated_dirs):
        """Single file verification should check disk vs RAM."""
        import shutil

        disk = populated_dirs["disk"]
        ram = populated_dirs["ram"]
        shutil.copy2(disk / "file1.txt", ram / "file1.txt")

        config = RamDiskConfig(name="test", disk_path=disk, ram_path=ram)
        result = verify_single_file(config, "file1.txt")
        assert result["match"] is True
        assert result["exists_on_disk"] is True
        assert result["exists_in_ram"] is True

    def test_verify_single_file_mismatch(self, populated_dirs):
        """Single file with different content should not match."""
        disk = populated_dirs["disk"]
        ram = populated_dirs["ram"]
        (ram / "file1.txt").write_text("different content")

        config = RamDiskConfig(name="test", disk_path=disk, ram_path=ram)
        result = verify_single_file(config, "file1.txt")
        assert result["match"] is False

    def test_integrity_result_properties(self):
        """IntegrityResult properties should compute correctly."""
        r = IntegrityResult(
            verified_count=10,
            mismatched_files=["a.txt"],
            disk_hashes={"a.txt": "1", "b.txt": "2"},
        )
        assert r.total_files == 2
        assert r.is_valid is False
        assert r.needs_recovery is True

        r2 = IntegrityResult(verified_count=5, disk_hashes={"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"})
        assert r2.is_valid is True
        assert r2.needs_recovery is False


class TestRecoveryManager:
    """Test automatic recovery orchestration."""

    def test_recovery_on_crash(self, populated_dirs, sample_manager_config):
        """After a crash (no marker), recovery should sync disk to RAM."""
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
        )
        mgr = RecoveryManager(sample_manager_config)
        result = mgr.recover(config)

        assert result.recovery_needed is True
        assert result.clean_shutdown is False
        assert result.files_synced > 0
        assert result.success is True

    def test_no_recovery_after_clean_shutdown(self, populated_dirs, sample_manager_config):
        """After clean shutdown with intact files, no recovery needed."""
        import shutil

        disk = populated_dirs["disk"]
        ram = populated_dirs["ram"]

        # Sync files manually
        for item in disk.iterdir():
            if item.is_file():
                shutil.copy2(item, ram / item.name)
            elif item.is_dir():
                shutil.copytree(item, ram / item.name)

        config = RamDiskConfig(
            name="test",
            disk_path=disk,
            ram_path=ram,
        )

        # Mark clean shutdown
        mark_clean_shutdown(config, sample_manager_config)

        mgr = RecoveryManager(sample_manager_config)
        result = mgr.recover(config)

        assert result.clean_shutdown is True
        # May or may not need recovery depending on integrity check

    def test_forced_recovery(self, populated_dirs, sample_manager_config):
        """force_full_sync should always trigger recovery."""
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
        )
        mark_clean_shutdown(config, sample_manager_config)

        mgr = RecoveryManager(sample_manager_config)
        result = mgr.recover(config, force_full_sync=True)

        assert result.recovery_needed is True
        assert result.files_synced > 0

    def test_prepare_shutdown(self, populated_dirs, sample_manager_config):
        """prepare_shutdown should write marker for clean detection."""
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
        )
        mgr = RecoveryManager(sample_manager_config)
        success = mgr.prepare_shutdown(config)
        assert success is True
        assert was_clean_shutdown(config, sample_manager_config) is True

    def test_check_status(self, populated_dirs, sample_manager_config):
        """check_status should report current state without performing recovery."""
        config = RamDiskConfig(
            name="test",
            disk_path=populated_dirs["disk"],
            ram_path=populated_dirs["ram"],
        )
        mgr = RecoveryManager(sample_manager_config)
        status = mgr.check_status(config)

        assert "clean_shutdown" in status
        assert "recovery_needed" in status
        assert "disk_path_exists" in status
        assert status["disk_path_exists"] is True

    def test_recovery_result_to_dict(self):
        """RecoveryResult.to_dict should serialize cleanly."""
        r = RecoveryResult(
            recovery_needed=True,
            clean_shutdown=False,
            files_synced=5,
            files_copied=["a.txt", "b.txt"],
            duration_ms=12.5,
        )
        d = r.to_dict()
        assert d["recovery_needed"] is True
        assert d["files_synced"] == 5
        assert d["success"] is True
        assert d["duration_ms"] == 12.5
