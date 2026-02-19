"""CASCADE RAM Disk Manager - High-performance RAM disk management for Python.

A cross-platform library for creating and managing RAM disks with automatic
synchronization to persistent storage. Built for scenarios requiring maximum
I/O performance with data safety.

Key Features:
    - Cross-platform support (Windows via ImDisk, Linux via tmpfs, macOS via diskutil)
    - Automatic sync between RAM and persistent storage
    - Dual-write controllers for consistency
    - Incremental sync with hash-based change detection
    - Clean shutdown handling with atexit hooks
    - Recovery from unclean shutdowns

Quick Start:
    from ram_disk_manager import RamDiskManager, RamDiskConfig
    from pathlib import Path

    # Create manager
    manager = RamDiskManager()

    # Register and mount a RAM disk
    manager.register(RamDiskConfig(
        name="cache",
        disk_path=Path("./data/cache"),
        size_mb=256
    ))
    ram_path = manager.mount("cache")

    # Use the high-speed RAM path
    (ram_path / "file.txt").write_text("fast writes!")

    # Automatic cleanup on exit, or manual:
    manager.unmount("cache", persist=True)

Classes:
    RamDiskManager: Main interface for RAM disk operations
    RamDiskConfig: Configuration for individual RAM disks
    ManagerConfig: Global manager configuration
    SyncStrategy: Enum for sync strategies (FULL, INCREMENTAL, PATTERN)
    Platform: Enum for target platforms (WINDOWS, LINUX, MACOS, AUTO)

See Also:
    - README.md for full documentation
    - examples/ for usage patterns
"""

__version__ = "2.2.0"
__author__ = "CIPS Corp"
__license__ = "MIT"

# Core configuration classes
from .config import (
    RamDiskConfig,
    ManagerConfig,
    SyncStrategy,
    Platform,
)

# Main manager class
from .manager import RamDiskManager

# Backend base classes (for extension)
from .backends.base import (
    RamDiskBackend,
    BackendResult,
    DiskUsage,
)

# Sync components
try:
    from .sync.dual_write import DualWriteController, WriteResult
    from .sync.engine import SyncEngine, SyncStats
except ImportError:
    DualWriteController = None
    WriteResult = None
    SyncEngine = None
    SyncStats = None

# Recovery components
try:
    from .recovery import RecoveryManager
except ImportError:
    RecoveryManager = None

# Public API
__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # Main classes
    "RamDiskManager",
    "RamDiskConfig",
    "ManagerConfig",
    # Enums
    "SyncStrategy",
    "Platform",
    # Backend classes
    "RamDiskBackend",
    "BackendResult",
    "DiskUsage",
    # Sync components
    "DualWriteController",
    "WriteResult",
    "SyncEngine",
    "SyncStats",
    # Recovery
    "RecoveryManager",
]


def create_manager(
    platform: str = "auto",
    base_ram_path: str = None,
    enable_dual_write: bool = True,
) -> RamDiskManager:
    """Convenience function to create a configured RamDiskManager.

    Args:
        platform: Target platform ("windows", "linux", "darwin", or "auto")
        base_ram_path: Base path for RAM disks (e.g., "R:\\" or "/mnt/ramdisk")
        enable_dual_write: Enable dual-write controllers

    Returns:
        Configured RamDiskManager instance

    Example:
        manager = create_manager(platform="auto")
    """
    from pathlib import Path

    platform_enum = Platform(platform.lower())

    config = ManagerConfig(
        platform=platform_enum,
        base_ram_path=Path(base_ram_path) if base_ram_path else None,
        enable_dual_write=enable_dual_write,
    )

    return RamDiskManager(config)
