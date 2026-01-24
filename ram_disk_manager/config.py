"""Configuration dataclasses for RAM Disk Manager."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from enum import Enum


class SyncStrategy(Enum):
    """Synchronization strategy for disk-RAM sync."""
    FULL = "full"           # Delete and copy all
    INCREMENTAL = "incremental"  # Only changed files (hash-based)
    PATTERN = "pattern"     # Only matching patterns


class Platform(Enum):
    """Target platform for RAM disk operations."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "darwin"
    AUTO = "auto"


@dataclass
class RamDiskConfig:
    """Configuration for a single RAM disk instance.

    Attributes:
        name: Unique identifier (e.g., "cache", "database")
        disk_path: Source of truth on persistent storage
        ram_path: Mount point for RAM disk (auto-determined if not set)
        size_mb: RAM disk size in megabytes
        patterns: Glob patterns for files to sync (default: all)
        sync_strategy: How to sync files
        auto_sync_on_startup: Sync from disk to RAM on mount
        persist_on_shutdown: Sync from RAM to disk on unmount
        verify_integrity: Hash-verify files after sync
    """
    name: str
    disk_path: Path
    ram_path: Optional[Path] = None
    size_mb: int = 512
    patterns: List[str] = field(default_factory=lambda: ["*"])
    sync_strategy: SyncStrategy = SyncStrategy.FULL
    auto_sync_on_startup: bool = True
    persist_on_shutdown: bool = True
    verify_integrity: bool = True

    def __post_init__(self):
        """Ensure paths are Path objects."""
        if isinstance(self.disk_path, str):
            self.disk_path = Path(self.disk_path)
        if isinstance(self.ram_path, str):
            self.ram_path = Path(self.ram_path)


@dataclass
class ManagerConfig:
    """Global configuration for RamDiskManager.

    Attributes:
        platform: Target platform (auto-detected if AUTO)
        base_ram_path: Base path for RAM disks (Windows: R:\\, Linux: /mnt/ramdisk)
        log_file: Path to log file (None for stdout)
        enable_dual_write: Enable dual-write controller
        recovery_marker_file: Filename for clean shutdown marker
    """
    platform: Platform = Platform.AUTO
    base_ram_path: Optional[Path] = None
    log_file: Optional[Path] = None
    enable_dual_write: bool = True
    recovery_marker_file: str = ".ram_disk_clean_shutdown"

    def __post_init__(self):
        """Ensure paths are Path objects."""
        if isinstance(self.base_ram_path, str):
            self.base_ram_path = Path(self.base_ram_path)
        if isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)
