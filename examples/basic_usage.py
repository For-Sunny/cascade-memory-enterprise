#!/usr/bin/env python3
"""Basic usage example for RAM Disk Manager.

This example demonstrates:
1. Creating a RamDiskManager instance
2. Registering a RAM disk with configuration
3. Mounting the RAM disk
4. Writing and reading files at RAM speed
5. Unmounting with persistence to disk
6. Showing recovery on restart

Run this example:
    python basic_usage.py
"""

import tempfile
from pathlib import Path
import time

from ram_disk_manager import (
    RamDiskManager,
    RamDiskConfig,
    ManagerConfig,
    SyncStrategy,
    Platform,
)


def main():
    # -------------------------------------------------------------------------
    # Setup: Create temporary directories for this example
    # In real usage, disk_path would be your persistent storage location
    # -------------------------------------------------------------------------

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Persistent storage (survives reboots)
        disk_path = temp_path / "persistent_data"
        disk_path.mkdir(parents=True, exist_ok=True)

        # RAM storage (fast, volatile)
        ram_path = temp_path / "ram_cache"

        # Pre-populate some data on disk
        (disk_path / "config.json").write_text('{"setting": "value"}')
        (disk_path / "data.txt").write_text("Important data that must persist")

        print("=" * 60)
        print("RAM Disk Manager - Basic Usage Example")
        print("=" * 60)

        # ---------------------------------------------------------------------
        # Step 1: Create Manager
        # ---------------------------------------------------------------------
        print("\n[1] Creating RamDiskManager...")

        # For cross-platform compatibility, let the manager auto-detect platform
        # You can also specify: platform=Platform.WINDOWS or Platform.LINUX
        manager_config = ManagerConfig(
            platform=Platform.AUTO,
            enable_dual_write=True,
        )
        manager = RamDiskManager(manager_config)

        print(f"    Platform: {manager.status()['platform']}")
        print(f"    Backend available: {manager.status()['backend_available']}")

        # ---------------------------------------------------------------------
        # Step 2: Register a RAM disk
        # ---------------------------------------------------------------------
        print("\n[2] Registering RAM disk configuration...")

        config = RamDiskConfig(
            name="mydata",                    # Unique identifier
            disk_path=disk_path,              # Source of truth (persistent)
            ram_path=ram_path,                # RAM mount point (fast)
            size_mb=256,                      # RAM disk size
            patterns=["*"],                   # Sync all files
            sync_strategy=SyncStrategy.FULL,  # Full sync on mount
            auto_sync_on_startup=True,        # Sync disk->RAM on mount
            persist_on_shutdown=True,         # Sync RAM->disk on unmount
            verify_integrity=True,            # Verify files after sync
        )

        success = manager.register(config)
        print(f"    Registered: {success}")

        # ---------------------------------------------------------------------
        # Step 3: Mount the RAM disk
        # ---------------------------------------------------------------------
        print("\n[3] Mounting RAM disk...")

        # Mount syncs from disk to RAM (since auto_sync_on_startup=True)
        mounted_path = manager.mount("mydata")
        print(f"    Mounted at: {mounted_path}")

        # Verify data was synced
        print(f"    Files in RAM: {list(ram_path.glob('*'))}")

        # ---------------------------------------------------------------------
        # Step 4: Work with RAM disk (fast I/O)
        # ---------------------------------------------------------------------
        print("\n[4] Working with RAM disk...")

        # Write new files to RAM (these are at RAM speed)
        start = time.perf_counter()
        for i in range(100):
            (ram_path / f"file_{i:03d}.txt").write_text(f"Content {i}")
        write_time = (time.perf_counter() - start) * 1000
        print(f"    Wrote 100 files in {write_time:.2f}ms")

        # Read files from RAM
        start = time.perf_counter()
        for i in range(100):
            _ = (ram_path / f"file_{i:03d}.txt").read_text()
        read_time = (time.perf_counter() - start) * 1000
        print(f"    Read 100 files in {read_time:.2f}ms")

        # Modify existing data
        (ram_path / "data.txt").write_text("Modified data at RAM speed!")

        # ---------------------------------------------------------------------
        # Step 5: Check status
        # ---------------------------------------------------------------------
        print("\n[5] Checking status...")

        status = manager.status()
        disk_status = status["disks"]["mydata"]

        print(f"    Mounted: {disk_status['mounted']}")
        print(f"    Mount time: {disk_status['mount_time']}")
        print(f"    Sync count: {disk_status['sync_count']}")
        print(f"    Dual-write enabled: {disk_status['dual_write_enabled']}")

        if disk_status['usage']:
            usage = disk_status['usage']
            print(f"    Disk usage: {usage.get('used_mb', 'N/A')}MB / {usage.get('total_mb', 'N/A')}MB")

        # ---------------------------------------------------------------------
        # Step 6: Unmount with persistence
        # ---------------------------------------------------------------------
        print("\n[6] Unmounting with persistence...")

        # Unmount syncs from RAM to disk (since persist=True)
        success = manager.unmount("mydata", persist=True)
        print(f"    Unmounted successfully: {success}")

        # Verify data was persisted to disk
        print(f"    Files on disk after unmount: {len(list(disk_path.glob('*')))}")

        # Check that modified data was saved
        disk_content = (disk_path / "data.txt").read_text()
        print(f"    Modified data persisted: {'Modified' in disk_content}")

        # ---------------------------------------------------------------------
        # Step 7: Recovery on restart (simulated)
        # ---------------------------------------------------------------------
        print("\n[7] Simulating recovery on restart...")

        # Create a new manager (simulates app restart)
        manager2 = RamDiskManager(manager_config)

        # Re-register the disk
        manager2.register(config)

        # Mount again - auto syncs from disk to RAM
        recovered_path = manager2.mount("mydata")

        # Count files in recovered RAM disk
        file_count = len(list(ram_path.glob("*.txt")))
        print(f"    Recovered {file_count} files from disk to RAM")

        # Verify data integrity
        recovered_content = (ram_path / "data.txt").read_text()
        print(f"    Data integrity preserved: {'Modified' in recovered_content}")

        # Cleanup
        manager2.unmount("mydata", persist=True)

        print("\n" + "=" * 60)
        print("Example complete!")
        print("=" * 60)


if __name__ == "__main__":
    main()
