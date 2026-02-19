"""Tests for ram_disk_manager.sync.dual_write module.

Validates the DualWriteController: disk-first writes, RAM-first reads,
failure callbacks, resync tracking, and thread safety.

DISK IS TRUTH, RAM IS CACHE.
"""

import json
import threading
from pathlib import Path

import pytest

from ram_disk_manager.sync.dual_write import DualWriteController, WriteResult


class TestWriteResult:
    """Test WriteResult dataclass properties."""

    def test_success_both_written(self):
        r = WriteResult(success=True, disk_written=True, ram_written=True, bytes_written=100)
        assert r.success is True
        assert r.partial is False

    def test_partial_ram_failed(self):
        r = WriteResult(success=True, disk_written=True, ram_written=False, bytes_written=100)
        assert r.partial is True

    def test_total_failure(self):
        r = WriteResult(success=False, disk_written=False, ram_written=False, bytes_written=0, error="disk fail")
        assert r.success is False
        assert r.partial is False


class TestDualWriteController:
    """Test DualWriteController operations."""

    def test_write_text(self, dual_write_config):
        """Write text content to both disk and RAM."""
        ctrl = DualWriteController(dual_write_config)
        result = ctrl.write("test.txt", "hello world")

        assert result.success is True
        assert result.disk_written is True
        assert result.ram_written is True
        assert result.bytes_written == len("hello world".encode("utf-8"))

        # Verify files exist
        disk_file = dual_write_config.disk_path / "test.txt"
        ram_file = dual_write_config.ram_path / "test.txt"
        assert disk_file.read_text() == "hello world"
        assert ram_file.read_text() == "hello world"

    def test_write_bytes(self, dual_write_config):
        """Write binary content to both locations."""
        ctrl = DualWriteController(dual_write_config)
        data = b"\x00\x01\x02\x03"
        result = ctrl.write("data.bin", data)

        assert result.success is True
        assert result.bytes_written == 4
        assert (dual_write_config.disk_path / "data.bin").read_bytes() == data
        assert (dual_write_config.ram_path / "data.bin").read_bytes() == data

    def test_write_creates_subdirectories(self, dual_write_config):
        """Subdirectories should be created automatically."""
        ctrl = DualWriteController(dual_write_config)
        result = ctrl.write("sub/dir/deep.txt", "deep content")

        assert result.success is True
        assert (dual_write_config.disk_path / "sub" / "dir" / "deep.txt").exists()
        assert (dual_write_config.ram_path / "sub" / "dir" / "deep.txt").exists()

    def test_write_backslash_normalization(self, dual_write_config):
        """Backslashes in paths should be normalized to forward slashes."""
        ctrl = DualWriteController(dual_write_config)
        result = ctrl.write("sub\\dir\\file.txt", "content")

        assert result.success is True
        assert (dual_write_config.disk_path / "sub" / "dir" / "file.txt").exists()

    def test_read_from_ram(self, dual_write_config):
        """Read should return from RAM (fast path)."""
        ctrl = DualWriteController(dual_write_config)
        ctrl.write("test.txt", "ram content")
        content = ctrl.read_text("test.txt")
        assert content == "ram content"

    def test_read_bytes(self, dual_write_config):
        """Read bytes should return raw binary."""
        ctrl = DualWriteController(dual_write_config)
        ctrl.write("data.bin", b"\x00\x01\x02")
        content = ctrl.read_bytes("data.bin")
        assert content == b"\x00\x01\x02"

    def test_read_disk_fallback(self, dual_write_config):
        """If RAM file missing, should fall back to disk."""
        ctrl = DualWriteController(dual_write_config)

        # Write only to disk (bypass controller)
        disk_file = dual_write_config.disk_path / "disk_only.txt"
        disk_file.write_text("disk truth")

        content = ctrl.read_text("disk_only.txt")
        assert content == "disk truth"

    def test_read_nonexistent_returns_none(self, dual_write_config):
        """Reading a nonexistent file should return None."""
        ctrl = DualWriteController(dual_write_config)
        assert ctrl.read_text("nonexistent.txt") is None

    def test_delete(self, dual_write_config):
        """Delete should remove from both disk and RAM."""
        ctrl = DualWriteController(dual_write_config)
        ctrl.write("deleteme.txt", "temp")
        assert (dual_write_config.disk_path / "deleteme.txt").exists()

        result = ctrl.delete("deleteme.txt")
        assert result.success is True
        assert not (dual_write_config.disk_path / "deleteme.txt").exists()
        assert not (dual_write_config.ram_path / "deleteme.txt").exists()

    def test_delete_nonexistent_succeeds(self, dual_write_config):
        """Deleting a nonexistent file should succeed (idempotent)."""
        ctrl = DualWriteController(dual_write_config)
        result = ctrl.delete("nonexistent.txt")
        assert result.success is True

    def test_exists(self, dual_write_config):
        """Exists checks disk (truth), not RAM."""
        ctrl = DualWriteController(dual_write_config)
        assert ctrl.exists("nope.txt") is False

        ctrl.write("yes.txt", "exists")
        assert ctrl.exists("yes.txt") is True

    def test_write_file_copy(self, dual_write_config, tmp_path):
        """write_file should copy a source file to both locations."""
        source = tmp_path / "source.txt"
        source.write_text("source content")

        ctrl = DualWriteController(dual_write_config)
        result = ctrl.write_file("dest.txt", source)

        assert result.success is True
        assert (dual_write_config.disk_path / "dest.txt").read_text() == "source content"
        assert (dual_write_config.ram_path / "dest.txt").read_text() == "source content"

    def test_write_file_nonexistent_source(self, dual_write_config, tmp_path):
        """write_file with nonexistent source should fail."""
        ctrl = DualWriteController(dual_write_config)
        result = ctrl.write_file("dest.txt", tmp_path / "nonexistent.txt")
        assert result.success is False
        assert "not found" in result.error

    def test_no_ram_path(self, tmp_dirs):
        """Controller with no ram_path should still write to disk."""
        from ram_disk_manager.config import RamDiskConfig

        config = RamDiskConfig(
            name="disk_only",
            disk_path=tmp_dirs["disk"],
            ram_path=None,
            size_mb=32,
        )
        ctrl = DualWriteController(config)
        result = ctrl.write("test.txt", "disk only")

        assert result.success is True
        assert result.disk_written is True
        assert result.ram_written is False
        assert (tmp_dirs["disk"] / "test.txt").read_text() == "disk only"

    def test_ram_failure_callback(self, tmp_dirs, tmp_path):
        """on_ram_failure callback should fire when RAM write fails."""
        from ram_disk_manager.config import RamDiskConfig
        from unittest.mock import patch

        failures = []

        def on_failure(path, error):
            failures.append((path, str(error)))

        config = RamDiskConfig(
            name="test",
            disk_path=tmp_dirs["disk"],
            ram_path=tmp_dirs["ram"],
            size_mb=32,
        )
        ctrl = DualWriteController(config, on_ram_failure=on_failure)

        # Capture the actual RAM path string for precise matching
        ram_str = str(tmp_dirs["ram"])

        original_write_bytes = Path.write_bytes

        def patched_write_bytes(self, data):
            if str(self).startswith(ram_str):
                raise OSError("Simulated RAM failure")
            return original_write_bytes(self, data)

        with patch.object(Path, "write_bytes", patched_write_bytes):
            result = ctrl.write("test.txt", "should fail on RAM")

        # Disk should succeed, RAM should fail
        assert result.success is True  # disk is truth
        assert result.disk_written is True
        assert result.ram_written is False
        assert len(failures) == 1
        assert failures[0][0] == "test.txt"

    def test_needs_resync_tracking(self, dual_write_config):
        """Paths that fail RAM write should be tracked for resync."""
        from unittest.mock import patch

        ctrl = DualWriteController(dual_write_config)

        ram_str = str(dual_write_config.ram_path)
        original_write_bytes = Path.write_bytes

        def patched_write_bytes(self, data):
            if str(self).startswith(ram_str):
                raise OSError("Simulated RAM failure")
            return original_write_bytes(self, data)

        with patch.object(Path, "write_bytes", patched_write_bytes):
            ctrl.write("fail1.txt", "data")
            ctrl.write("fail2.txt", "data")

        needs = ctrl.get_needs_resync()
        assert "fail1.txt" in needs
        assert "fail2.txt" in needs

    def test_resync_path(self, dual_write_config):
        """resync_path should copy from disk to RAM."""
        ctrl = DualWriteController(dual_write_config)

        # Write to disk only
        (dual_write_config.disk_path / "resync.txt").write_text("truth")

        result = ctrl.resync_path("resync.txt")
        assert result.success is True
        assert (dual_write_config.ram_path / "resync.txt").read_text() == "truth"

    def test_clear_needs_resync(self, dual_write_config):
        """clear_needs_resync should empty the tracking set."""
        ctrl = DualWriteController(dual_write_config)
        ctrl._needs_resync.add("test.txt")
        ctrl.clear_needs_resync()
        assert ctrl.get_needs_resync() == []

    def test_thread_safety(self, dual_write_config):
        """Multiple threads writing concurrently should not corrupt data."""
        ctrl = DualWriteController(dual_write_config)
        errors = []

        def write_task(i):
            try:
                result = ctrl.write(f"thread_{i}.txt", f"content_{i}")
                if not result.success:
                    errors.append(f"Thread {i} failed: {result.error}")
            except Exception as e:
                errors.append(f"Thread {i} exception: {e}")

        threads = [threading.Thread(target=write_task, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"

        # Verify all files written correctly
        for i in range(20):
            disk_file = dual_write_config.disk_path / f"thread_{i}.txt"
            assert disk_file.read_text() == f"content_{i}"
