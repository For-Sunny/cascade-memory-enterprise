#!/usr/bin/env python3
"""Incremental sync example for RAM Disk Manager.

This example demonstrates:
1. Setting up incremental sync strategy
2. Making changes to files
3. Syncing only changed files (hash-based detection)
4. Viewing sync statistics

Incremental sync uses hash-based change detection to avoid copying
unchanged files, making it much faster for large directories with
frequent small changes.

Run this example:
    python incremental_sync.py
"""

import tempfile
import time
from pathlib import Path

from ram_disk_manager import (
    RamDiskManager,
    RamDiskConfig,
    ManagerConfig,
    SyncStrategy,
)
from ram_disk_manager.sync.engine import SyncEngine


def create_test_files(directory: Path, count: int = 50) -> int:
    """Create test files and return total bytes written."""
    total_bytes = 0
    for i in range(count):
        content = f"File {i} content: {'x' * (100 + i * 10)}"
        (directory / f"file_{i:03d}.txt").write_text(content)
        total_bytes += len(content)
    return total_bytes


def main():
    print("=" * 60)
    print("RAM Disk Manager - Incremental Sync Example")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        disk_path = temp_path / "disk"
        ram_path = temp_path / "ram"
        disk_path.mkdir()
        ram_path.mkdir()

        # ---------------------------------------------------------------------
        # Step 1: Create test files on disk
        # ---------------------------------------------------------------------
        print("[1] Creating test files on disk...")

        total_bytes = create_test_files(disk_path, count=50)
        print(f"    Created 50 files ({total_bytes:,} bytes)")

        # ---------------------------------------------------------------------
        # Step 2: Configure incremental sync
        # ---------------------------------------------------------------------
        print("\n[2] Configuring incremental sync...")

        config = RamDiskConfig(
            name="data",
            disk_path=disk_path,
            ram_path=ram_path,
            size_mb=256,
            patterns=["*.txt"],                      # Only sync .txt files
            sync_strategy=SyncStrategy.INCREMENTAL,  # Use hash-based sync
            verify_integrity=True,
        )

        # Create SyncEngine directly (for fine-grained control)
        engine = SyncEngine(config)

        print(f"    Strategy: {config.sync_strategy.value}")
        print(f"    Patterns: {config.patterns}")

        # ---------------------------------------------------------------------
        # Step 3: Initial full sync (disk to RAM)
        # ---------------------------------------------------------------------
        print("\n[3] Initial sync (disk -> RAM)...")

        stats = engine.disk_to_ram(force_full=True)

        print(f"    Strategy used: {stats.strategy}")
        print(f"    Files copied: {stats.files_copied}")
        print(f"    Files deleted: {stats.files_deleted}")
        print(f"    Bytes copied: {stats.bytes_copied:,}")
        print(f"    Duration: {stats.duration_ms:.2f}ms")
        print(f"    Success: {stats.success}")

        # Verify files exist in RAM
        ram_files = list(ram_path.glob("*.txt"))
        print(f"    Files in RAM: {len(ram_files)}")

        # ---------------------------------------------------------------------
        # Step 4: Make some changes on disk
        # ---------------------------------------------------------------------
        print("\n[4] Making changes on disk...")

        # Modify 5 files
        modified_count = 0
        for i in range(0, 50, 10):  # Modify files 0, 10, 20, 30, 40
            file_path = disk_path / f"file_{i:03d}.txt"
            file_path.write_text(f"MODIFIED content for file {i}")
            modified_count += 1
        print(f"    Modified {modified_count} files")

        # Add 3 new files
        for i in range(50, 53):
            content = f"New file {i}"
            (disk_path / f"file_{i:03d}.txt").write_text(content)
        print(f"    Added 3 new files")

        # Delete 2 files
        (disk_path / "file_001.txt").unlink()
        (disk_path / "file_002.txt").unlink()
        print(f"    Deleted 2 files")

        # ---------------------------------------------------------------------
        # Step 5: Incremental sync (only changes)
        # ---------------------------------------------------------------------
        print("\n[5] Incremental sync (only changes)...")

        stats = engine.disk_to_ram(force_full=False)  # Use incremental

        print(f"    Strategy used: {stats.strategy}")
        print(f"    Files copied: {stats.files_copied}")       # Should be 8 (5 modified + 3 new)
        print(f"    Files deleted: {stats.files_deleted}")     # Should be 2
        print(f"    Files unchanged: {stats.files_unchanged}") # Should be 43
        print(f"    Bytes copied: {stats.bytes_copied:,}")
        print(f"    Duration: {stats.duration_ms:.2f}ms")
        print(f"    Success: {stats.success}")

        # ---------------------------------------------------------------------
        # Step 6: Check sync status
        # ---------------------------------------------------------------------
        print("\n[6] Checking sync status...")

        status = engine.get_sync_status()

        print(f"    Disk exists: {status['disk_exists']}")
        print(f"    RAM exists: {status['ram_exists']}")
        print(f"    In sync: {status['in_sync']}")

        if status['differences']:
            diff = status['differences']
            print(f"    Disk-only files: {len(diff['disk_only'])}")
            print(f"    RAM-only files: {len(diff['ram_only'])}")
            print(f"    Modified files: {len(diff['modified'])}")
            print(f"    Identical files: {diff['identical']}")

        # ---------------------------------------------------------------------
        # Step 7: Compare full vs incremental sync performance
        # ---------------------------------------------------------------------
        print("\n[7] Performance comparison...")

        # Make a small change
        (disk_path / "file_010.txt").write_text("Another small change")

        # Time incremental sync
        start = time.perf_counter()
        incremental_stats = engine.disk_to_ram(force_full=False)
        incremental_time = (time.perf_counter() - start) * 1000

        # Time full sync
        start = time.perf_counter()
        full_stats = engine.disk_to_ram(force_full=True)
        full_time = (time.perf_counter() - start) * 1000

        print(f"    Incremental sync:")
        print(f"      Files copied: {incremental_stats.files_copied}")
        print(f"      Time: {incremental_time:.2f}ms")

        print(f"    Full sync:")
        print(f"      Files copied: {full_stats.files_copied}")
        print(f"      Time: {full_time:.2f}ms")

        if incremental_time > 0:
            speedup = full_time / incremental_time
            print(f"    Speedup: {speedup:.1f}x faster with incremental")

        # ---------------------------------------------------------------------
        # Step 8: Sync RAM changes back to disk
        # ---------------------------------------------------------------------
        print("\n[8] Syncing RAM changes back to disk...")

        # Make changes in RAM
        (ram_path / "file_020.txt").write_text("Changed in RAM!")
        (ram_path / "new_from_ram.txt").write_text("Created in RAM")

        # Sync back to disk (persisting changes)
        stats = engine.ram_to_disk()

        print(f"    Files copied: {stats.files_copied}")
        print(f"    Files deleted: {stats.files_deleted}")
        print(f"    Duration: {stats.duration_ms:.2f}ms")
        print(f"    Success: {stats.success}")

        # Verify changes persisted
        assert (disk_path / "new_from_ram.txt").exists(), "New file not persisted!"
        content = (disk_path / "file_020.txt").read_text()
        assert "Changed in RAM" in content, "Changes not persisted!"
        print("    Changes successfully persisted to disk")

        # ---------------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("Summary: Incremental Sync Strategy")
        print("=" * 60)
        print("""
How it works:
  1. Compute hash of each file in source and target
  2. Compare hashes to find: added, modified, removed, unchanged
  3. Only copy files that changed

Benefits:
  - Much faster for large directories with few changes
  - Lower I/O and CPU usage
  - Hash cache persists on disk for even faster subsequent syncs

Use cases:
  - Large codebases with frequent small edits
  - Configuration directories
  - Any directory where most files don't change between syncs

Trade-offs:
  - Initial sync still needs to hash all files
  - Memory overhead for storing hashes
  - For small directories, full sync may be faster
""")


if __name__ == "__main__":
    main()
