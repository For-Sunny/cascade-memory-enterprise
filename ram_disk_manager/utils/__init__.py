"""Utility modules for RAM Disk Manager.

This package provides:
- hashing: Fast file and directory hashing utilities
- logging: Configured logging with JSON/text output support
- platform: Platform detection and admin privilege checks
"""

from ram_disk_manager.utils.hashing import fast_hash_file, hash_directory
from ram_disk_manager.utils.logging import get_logger
from ram_disk_manager.utils.platform import detect_platform, is_admin, get_default_ram_path

__all__ = [
    "fast_hash_file",
    "hash_directory",
    "get_logger",
    "detect_platform",
    "is_admin",
    "get_default_ram_path",
]
