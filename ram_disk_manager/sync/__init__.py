"""Synchronization module for RAM Disk Manager.

Philosophy: DISK IS TRUTH, RAM IS CACHE.

This module provides:
- SyncEngine: Bidirectional sync between disk (truth) and RAM (cache)
- DualWriteController: Thread-safe writes to both locations

Write order: Disk first (must succeed), RAM second (best effort).
Read order: RAM first (fast), disk fallback (guaranteed).
"""

from ram_disk_manager.sync.engine import SyncEngine, SyncStats
from ram_disk_manager.sync.dual_write import DualWriteController

__all__ = [
    "SyncEngine",
    "SyncStats",
    "DualWriteController",
]
