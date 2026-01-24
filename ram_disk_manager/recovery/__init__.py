"""Recovery system for RAM Disk Manager.

Handles crash detection, integrity verification, and automatic recovery
after unclean shutdowns.

This package provides:
- detector: Clean shutdown detection via marker files
- integrity: Hash-based verification of disk vs RAM content
- auto_sync: Automatic recovery orchestration
"""

from ram_disk_manager.recovery.detector import (
    was_clean_shutdown,
    mark_clean_shutdown,
    clear_shutdown_marker,
)
from ram_disk_manager.recovery.integrity import verify_integrity
from ram_disk_manager.recovery.auto_sync import RecoveryManager

__all__ = [
    "was_clean_shutdown",
    "mark_clean_shutdown",
    "clear_shutdown_marker",
    "verify_integrity",
    "RecoveryManager",
]
