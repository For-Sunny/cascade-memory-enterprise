"""Tests for ram_disk_manager.utils.hashing module.

Validates file hashing, directory hashing, and hash comparison logic.
These are the foundation of sync integrity -- if hashing breaks, everything breaks.
"""

import json
from pathlib import Path

import pytest

from ram_disk_manager.utils.hashing import (
    fast_hash_file,
    hash_directory,
    compare_hashes,
)


class TestFastHashFile:
    """Test file hashing with different algorithms."""

    def test_hash_text_file(self, tmp_path):
        """Basic text file should produce consistent hash."""
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h1 = fast_hash_file(f)
        h2 = fast_hash_file(f)
        assert h1 == h2
        assert isinstance(h1, str)
        assert len(h1) > 0

    def test_hash_binary_file(self, tmp_path):
        """Binary file should hash correctly."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00\x01\x02\x03" * 1000)
        h = fast_hash_file(f)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_different_content_different_hash(self, tmp_path):
        """Different content must produce different hashes."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content A")
        f2.write_text("content B")
        assert fast_hash_file(f1) != fast_hash_file(f2)

    def test_same_content_same_hash(self, tmp_path):
        """Same content in different files must produce same hash."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("identical")
        f2.write_text("identical")
        assert fast_hash_file(f1) == fast_hash_file(f2)

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fast_hash_file(tmp_path / "nonexistent.txt")

    def test_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Not a file"):
            fast_hash_file(tmp_path)

    def test_md5_algorithm(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("md5 test")
        h = fast_hash_file(f, algorithm="md5")
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 produces 32 hex chars

    def test_sha256_algorithm(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("sha256 test")
        h = fast_hash_file(f, algorithm="sha256")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256 produces 64 hex chars

    def test_unknown_algorithm_raises(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("test")
        with pytest.raises(ValueError, match="Unknown algorithm"):
            fast_hash_file(f, algorithm="bogus")

    def test_empty_file(self, tmp_path):
        """Empty file should still produce a valid hash."""
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        h = fast_hash_file(f)
        assert isinstance(h, str)
        assert len(h) > 0


class TestHashDirectory:
    """Test directory hashing and file collection."""

    def test_empty_directory(self, tmp_path):
        result = hash_directory(tmp_path)
        assert result == {}

    def test_single_file(self, tmp_path):
        (tmp_path / "test.txt").write_text("hello")
        result = hash_directory(tmp_path)
        assert "test.txt" in result
        assert len(result) == 1

    def test_nested_directory(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "nested.txt").write_text("nested")
        (tmp_path / "root.txt").write_text("root")
        result = hash_directory(tmp_path)
        assert "root.txt" in result
        assert "sub/nested.txt" in result
        assert len(result) == 2

    def test_forward_slash_keys(self, tmp_path):
        """Keys should use forward slashes regardless of platform."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "file.txt").write_text("test")
        result = hash_directory(tmp_path)
        for key in result:
            assert "\\" not in key

    def test_nonexistent_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            hash_directory(tmp_path / "nonexistent")

    def test_file_instead_of_directory_raises(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("test")
        with pytest.raises(ValueError, match="Not a directory"):
            hash_directory(f)

    def test_pattern_filtering(self, tmp_path):
        """Only files matching patterns should be hashed."""
        (tmp_path / "keep.txt").write_text("keep")
        (tmp_path / "skip.json").write_text("{}")
        result = hash_directory(tmp_path, patterns=["*.txt"])
        assert "keep.txt" in result
        # *.txt pattern with rglob may or may not match .json -- check it doesn't
        for key in result:
            assert key.endswith(".txt")


class TestCompareHashes:
    """Test hash comparison logic."""

    def test_identical(self):
        hashes = {"a.txt": "abc123", "b.txt": "def456"}
        diff = compare_hashes(hashes, hashes.copy())
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["modified"] == []
        assert sorted(diff["unchanged"]) == ["a.txt", "b.txt"]

    def test_added_files(self):
        source = {"a.txt": "abc", "b.txt": "def"}
        target = {"a.txt": "abc"}
        diff = compare_hashes(source, target)
        assert diff["added"] == ["b.txt"]
        assert diff["removed"] == []
        assert diff["modified"] == []
        assert diff["unchanged"] == ["a.txt"]

    def test_removed_files(self):
        source = {"a.txt": "abc"}
        target = {"a.txt": "abc", "b.txt": "def"}
        diff = compare_hashes(source, target)
        assert diff["added"] == []
        assert diff["removed"] == ["b.txt"]
        assert diff["modified"] == []

    def test_modified_files(self):
        source = {"a.txt": "abc"}
        target = {"a.txt": "xyz"}
        diff = compare_hashes(source, target)
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["modified"] == ["a.txt"]
        assert diff["unchanged"] == []

    def test_empty_both(self):
        diff = compare_hashes({}, {})
        assert diff == {
            "added": [],
            "removed": [],
            "modified": [],
            "unchanged": [],
        }

    def test_complex_diff(self):
        """Test with additions, removals, modifications, and unchanged."""
        source = {
            "same.txt": "aaa",
            "changed.txt": "bbb",
            "new.txt": "ccc",
        }
        target = {
            "same.txt": "aaa",
            "changed.txt": "xxx",
            "deleted.txt": "ddd",
        }
        diff = compare_hashes(source, target)
        assert diff["added"] == ["new.txt"]
        assert diff["removed"] == ["deleted.txt"]
        assert diff["modified"] == ["changed.txt"]
        assert diff["unchanged"] == ["same.txt"]

    def test_results_are_sorted(self):
        source = {"c.txt": "1", "a.txt": "2", "b.txt": "3"}
        target = {}
        diff = compare_hashes(source, target)
        assert diff["added"] == ["a.txt", "b.txt", "c.txt"]
