#!/usr/bin/env python3
"""Dual-write pattern example for RAM Disk Manager.

Philosophy: DISK IS TRUTH, RAM IS CACHE.

This example demonstrates:
1. Creating a DualWriteController
2. Writing to both disk and RAM simultaneously
3. Reading from RAM with automatic disk fallback
4. Handling partial failures (RAM fails but disk succeeds)
5. Re-syncing stale RAM content

The dual-write pattern ensures data safety while maximizing read performance:
- Writes: Disk FIRST (must succeed), RAM second (best effort)
- Reads: RAM first (fast), disk fallback (guaranteed)

Run this example:
    python dual_write_example.py
"""

import tempfile
from pathlib import Path

from ram_disk_manager import RamDiskConfig, SyncStrategy
from ram_disk_manager.sync.dual_write import DualWriteController, WriteResult


def on_ram_failure(relative_path: str, error: Exception):
    """Callback when RAM write fails (data is safe on disk)."""
    print(f"    [CALLBACK] RAM write failed for {relative_path}: {error}")
    print(f"    [CALLBACK] Data is safe on disk, will resync later")


def on_sync_needed(relative_path: str):
    """Callback when RAM cache is stale and was read from disk."""
    print(f"    [CALLBACK] File {relative_path} was read from disk (RAM stale)")


def main():
    print("=" * 60)
    print("RAM Disk Manager - Dual-Write Pattern Example")
    print("=" * 60)
    print()
    print("Philosophy: DISK IS TRUTH, RAM IS CACHE")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        disk_path = temp_path / "disk"
        ram_path = temp_path / "ram"
        disk_path.mkdir()
        ram_path.mkdir()

        # ---------------------------------------------------------------------
        # Step 1: Create DualWriteController
        # ---------------------------------------------------------------------
        print("[1] Creating DualWriteController...")

        config = RamDiskConfig(
            name="cache",
            disk_path=disk_path,
            ram_path=ram_path,
            size_mb=256,
        )

        controller = DualWriteController(
            config=config,
            on_ram_failure=on_ram_failure,
            on_sync_needed=on_sync_needed,
        )

        print(f"    Disk path: {disk_path}")
        print(f"    RAM path: {ram_path}")

        # ---------------------------------------------------------------------
        # Step 2: Write content to both locations
        # ---------------------------------------------------------------------
        print("\n[2] Writing content (disk FIRST, RAM second)...")

        # Write string content
        result = controller.write("config/settings.json", '{"theme": "dark"}')
        print(f"    settings.json:")
        print(f"      Success: {result.success}")
        print(f"      Disk written: {result.disk_written}")
        print(f"      RAM written: {result.ram_written}")
        print(f"      Bytes: {result.bytes_written}")

        # Write binary content
        binary_data = b"\x00\x01\x02\x03\x04"
        result = controller.write("data/binary.bin", binary_data)
        print(f"    binary.bin:")
        print(f"      Success: {result.success}")
        print(f"      Bytes: {result.bytes_written}")

        # Verify both locations have the files
        assert (disk_path / "config/settings.json").exists(), "Disk write failed!"
        assert (ram_path / "config/settings.json").exists(), "RAM write failed!"
        print("    Files exist in both disk and RAM")

        # ---------------------------------------------------------------------
        # Step 3: Read content (RAM first, disk fallback)
        # ---------------------------------------------------------------------
        print("\n[3] Reading content (RAM first, disk fallback)...")

        # Read from RAM (fast path)
        content = controller.read_text("config/settings.json")
        print(f"    Read settings.json: {content}")

        # Read binary
        binary = controller.read_bytes("data/binary.bin")
        print(f"    Read binary.bin: {binary!r}")

        # ---------------------------------------------------------------------
        # Step 4: Simulate RAM failure
        # ---------------------------------------------------------------------
        print("\n[4] Simulating RAM failure scenario...")

        # Delete RAM file to simulate failure/corruption
        (ram_path / "config/settings.json").unlink()
        print("    Deleted RAM copy of settings.json")

        # Read will fall back to disk
        content = controller.read_text("config/settings.json")
        print(f"    Read (fell back to disk): {content}")

        # ---------------------------------------------------------------------
        # Step 5: Handle partial write failures
        # ---------------------------------------------------------------------
        print("\n[5] Demonstrating partial failure handling...")

        # Write new content - disk succeeds
        result = controller.write("config/settings.json", '{"theme": "light"}')
        print(f"    Re-wrote settings.json:")
        print(f"      Success: {result.success}")
        print(f"      Disk written: {result.disk_written}")
        print(f"      RAM written: {result.ram_written}")

        # Check needs_resync list
        needs_resync = controller.get_needs_resync()
        print(f"    Files needing resync: {needs_resync}")

        # Resync the stale path
        if needs_resync:
            print("\n    Resyncing stale files...")
            for path in needs_resync:
                result = controller.resync_path(path)
                print(f"      Resynced {path}: success={result.success}")

        # Verify resync cleared the list
        needs_resync = controller.get_needs_resync()
        print(f"    After resync, files needing resync: {needs_resync}")

        # ---------------------------------------------------------------------
        # Step 6: Delete operation (also dual-write)
        # ---------------------------------------------------------------------
        print("\n[6] Delete operation (disk first, RAM second)...")

        result = controller.delete("data/binary.bin")
        print(f"    Delete binary.bin:")
        print(f"      Success: {result.success}")
        print(f"      Disk deleted: {result.disk_written}")
        print(f"      RAM deleted: {result.ram_written}")

        # Verify deletion
        assert not (disk_path / "data/binary.bin").exists(), "Disk delete failed!"
        print("    File removed from both locations")

        # ---------------------------------------------------------------------
        # Step 7: Check existence (disk is truth)
        # ---------------------------------------------------------------------
        print("\n[7] Checking existence (disk is source of truth)...")

        exists = controller.exists("config/settings.json")
        print(f"    config/settings.json exists: {exists}")

        exists = controller.exists("data/binary.bin")
        print(f"    data/binary.bin exists: {exists}")

        # ---------------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("Summary: Dual-Write Pattern")
        print("=" * 60)
        print("""
Write Order:
  1. Disk (MUST succeed) - Data is safe
  2. RAM (best effort)   - If fails, trigger callback

Read Order:
  1. RAM (fast)          - Immediate return if available
  2. Disk (fallback)     - Guaranteed data source

Benefits:
  - Data safety: Disk always has the truth
  - Read speed: RAM serves most reads
  - Graceful degradation: RAM failure doesn't lose data
  - Automatic tracking: Knows which files need resync
""")


if __name__ == "__main__":
    main()
