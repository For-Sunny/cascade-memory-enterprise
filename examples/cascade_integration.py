#!/usr/bin/env python3
"""SQLite/CASCADE integration example for RAM Disk Manager.

This example demonstrates:
1. Managing SQLite databases with RAM disk for maximum query speed
2. Using dual-write for live changes (WAL mode compatible)
3. Pattern-based sync for database files only
4. Safe shutdown with persistence

Philosophy: DISK IS TRUTH, RAM IS CACHE

For SQLite databases, this translates to:
- The .db file on disk is the source of truth
- The .db file in RAM is a high-speed cache
- Dual-write ensures every write hits disk FIRST
- WAL mode gives you the best of both worlds

This pattern is used in CASCADE memory system for sub-millisecond
database access while maintaining data safety.

Run this example:
    python cascade_integration.py
"""

import sqlite3
import tempfile
import time
from pathlib import Path

from ram_disk_manager import (
    RamDiskManager,
    RamDiskConfig,
    ManagerConfig,
    SyncStrategy,
)
from ram_disk_manager.sync.dual_write import DualWriteController


def create_sample_database(db_path: Path) -> None:
    """Create a sample SQLite database with test data."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance DESC)
    """)

    # Insert sample data
    memories = [
        ("First memory: learning to persist", 0.9),
        ("Second memory: understanding dual-write", 0.8),
        ("Third memory: achieving sub-millisecond access", 0.95),
        ("Background memory: routine operation", 0.3),
    ]

    cursor.executemany(
        "INSERT INTO memories (content, importance) VALUES (?, ?)",
        memories
    )

    conn.commit()
    conn.close()


def benchmark_queries(db_path: Path, label: str, iterations: int = 100) -> float:
    """Benchmark query performance and return average time in microseconds."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    start = time.perf_counter()
    for _ in range(iterations):
        cursor.execute(
            "SELECT * FROM memories WHERE importance > 0.5 ORDER BY importance DESC"
        )
        _ = cursor.fetchall()

    elapsed = (time.perf_counter() - start) * 1_000_000 / iterations  # microseconds
    conn.close()

    print(f"    {label}: {elapsed:.1f}us average per query ({iterations} iterations)")
    return elapsed


def main():
    print("=" * 60)
    print("RAM Disk Manager - SQLite/CASCADE Integration Example")
    print("=" * 60)
    print()
    print("Philosophy: DISK IS TRUTH, RAM IS CACHE")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Persistent storage (SSD/HDD)
        disk_path = temp_path / "cascade_db"
        disk_path.mkdir()

        # RAM storage (maximum speed)
        ram_path = temp_path / "ram_cache"
        ram_path.mkdir()

        # NOTE: 'cascade.db' below is a generic demo SQLite database name used to
        # illustrate RAM Disk Manager behavior. CASCADE's actual memory system stores
        # data as 6 separate layer files (episodic_memory.db, semantic_memory.db, etc.)
        # not as a single cascade.db file.

        # ---------------------------------------------------------------------
        # Step 1: Create database on disk (the truth)
        # ---------------------------------------------------------------------
        print("[1] Creating SQLite database on disk (source of truth)...")

        db_file = disk_path / "cascade.db"
        create_sample_database(db_file)

        # Check size
        db_size = db_file.stat().st_size
        print(f"    Database created: {db_file}")
        print(f"    Size: {db_size:,} bytes")

        # Benchmark disk performance
        disk_time = benchmark_queries(db_file, "Disk query time")

        # ---------------------------------------------------------------------
        # Step 2: Configure RAM disk for database files
        # ---------------------------------------------------------------------
        print("\n[2] Configuring RAM disk for *.db files...")

        config = RamDiskConfig(
            name="cascade",
            disk_path=disk_path,
            ram_path=ram_path,
            size_mb=512,
            patterns=["*.db", "*.db-wal", "*.db-shm"],  # SQLite files
            sync_strategy=SyncStrategy.FULL,
            auto_sync_on_startup=True,
            persist_on_shutdown=True,
            verify_integrity=True,
        )

        print(f"    Patterns: {config.patterns}")
        print("    (Includes WAL and shared memory files for WAL mode)")

        # ---------------------------------------------------------------------
        # Step 3: Mount and sync to RAM
        # ---------------------------------------------------------------------
        print("\n[3] Mounting RAM disk and syncing database...")

        manager = RamDiskManager()
        manager.register(config)
        mounted_path = manager.mount("cascade")

        print(f"    Mounted at: {mounted_path}")

        # Verify database was synced
        ram_db = ram_path / "cascade.db"
        assert ram_db.exists(), "Database not synced to RAM!"
        print(f"    Database synced to RAM: {ram_db}")

        # Benchmark RAM performance
        ram_time = benchmark_queries(ram_db, "RAM query time")

        # Calculate speedup
        if ram_time > 0:
            speedup = disk_time / ram_time
            print(f"    Speedup: {speedup:.1f}x faster from RAM")

        # ---------------------------------------------------------------------
        # Step 4: Set up dual-write for live changes
        # ---------------------------------------------------------------------
        print("\n[4] Setting up dual-write for live database changes...")

        # The dual-write controller ensures DISK is always written first
        # This is critical for database integrity

        def on_ram_failure(path: str, error: Exception):
            print(f"    WARNING: RAM write failed for {path}")
            print(f"    Data is safe on disk, will resync on next mount")

        controller = DualWriteController(
            config=config,
            on_ram_failure=on_ram_failure,
        )

        print("    Dual-write controller ready")
        print("    Write order: Disk (must succeed) -> RAM (best effort)")

        # ---------------------------------------------------------------------
        # Step 5: Demonstrate safe database updates
        # ---------------------------------------------------------------------
        print("\n[5] Safe database update pattern...")

        # For SQLite, the safest pattern is:
        # 1. Write to disk database directly (it's the truth)
        # 2. Read from RAM for speed
        # 3. Sync periodically or on shutdown

        # Write to disk (truth)
        disk_conn = sqlite3.connect(str(db_file))
        disk_cursor = disk_conn.cursor()
        disk_cursor.execute(
            "INSERT INTO memories (content, importance) VALUES (?, ?)",
            ("New memory: dual-write in action", 0.85)
        )
        disk_conn.commit()
        disk_conn.close()
        print("    Wrote new memory to DISK (truth)")

        # The RAM copy is now stale - this is expected
        # You have two options:

        # Option A: Re-sync RAM from disk (for consistency)
        print("    Syncing RAM from disk...")
        manager.sync_to_ram("cascade")

        # Option B: Read directly from disk for this query
        # (Use when you need guaranteed fresh data)

        # Verify the new record is accessible from RAM
        ram_conn = sqlite3.connect(str(ram_db))
        ram_cursor = ram_conn.cursor()
        ram_cursor.execute("SELECT COUNT(*) FROM memories")
        count = ram_cursor.fetchone()[0]
        ram_conn.close()
        print(f"    Total memories in RAM: {count}")

        # ---------------------------------------------------------------------
        # Step 6: WAL mode considerations
        # ---------------------------------------------------------------------
        print("\n[6] WAL mode configuration (recommended for concurrent access)...")

        # Enable WAL mode on the disk database
        disk_conn = sqlite3.connect(str(db_file))
        disk_conn.execute("PRAGMA journal_mode=WAL")
        result = disk_conn.execute("PRAGMA journal_mode").fetchone()[0]
        disk_conn.close()
        print(f"    Journal mode: {result}")

        # WAL creates additional files: .db-wal and .db-shm
        # Our pattern config already includes these
        print("    WAL files will be synced: *.db-wal, *.db-shm")

        # Note: For production use with WAL mode, consider:
        # 1. Checkpoint before sync (PRAGMA wal_checkpoint(TRUNCATE))
        # 2. Use exclusive locking during sync
        # 3. Or use separate connections for read (RAM) and write (disk)

        # ---------------------------------------------------------------------
        # Step 7: Clean shutdown with persistence
        # ---------------------------------------------------------------------
        print("\n[7] Clean shutdown with persistence...")

        # Make a final change to demonstrate persistence
        disk_conn = sqlite3.connect(str(db_file))
        disk_cursor = disk_conn.cursor()
        disk_cursor.execute(
            "INSERT INTO memories (content, importance) VALUES (?, ?)",
            ("Final memory: clean shutdown", 1.0)
        )
        disk_conn.commit()
        disk_conn.close()

        # Unmount - this syncs RAM -> disk if persist_on_shutdown=True
        # For databases, disk is already truth, so this is mainly cleanup
        success = manager.unmount("cascade", persist=True)
        print(f"    Unmounted successfully: {success}")

        # Verify final state
        final_conn = sqlite3.connect(str(db_file))
        final_cursor = final_conn.cursor()
        final_cursor.execute("SELECT COUNT(*) FROM memories")
        final_count = final_cursor.fetchone()[0]
        final_conn.close()
        print(f"    Final memory count on disk: {final_count}")

        # ---------------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("Summary: SQLite/CASCADE Integration Pattern")
        print("=" * 60)
        print("""
Architecture:

  [Application]
       |
       v
  [RAM Database] <--- Fast reads (sub-ms)
       |
  [Sync Engine] <---- Periodic sync / on-demand
       |
       v
  [Disk Database] <-- Source of truth (writes go here FIRST)

Best Practices:

1. DISK IS TRUTH: Always write to disk database first
   - Disk writes must succeed before operation completes
   - RAM is a read cache, not the primary store

2. SYNC STRATEGY: Choose based on workload
   - Read-heavy: Sync on startup, read from RAM
   - Write-heavy: Write to disk, sync to RAM periodically
   - Mixed: Use dual-write with immediate disk, lazy RAM

3. WAL MODE: Recommended for concurrent access
   - Better write performance
   - Readers don't block writers
   - Remember to sync WAL files too

4. PATTERNS: Only sync what you need
   - *.db for main database
   - *.db-wal, *.db-shm for WAL mode
   - Exclude temporary files

5. RECOVERY: On startup, always sync disk -> RAM
   - RAM content is volatile
   - Disk is the recovery source

Performance Tips:

- Use PRAGMA synchronous=NORMAL for disk writes
- Use PRAGMA cache_size=-64000 (64MB) for RAM queries
- Consider read replicas: write to disk, read from RAM
- Benchmark YOUR workload - RAM isn't always faster for small DBs
""")


if __name__ == "__main__":
    main()
