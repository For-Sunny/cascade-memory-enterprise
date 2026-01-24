"""Abstract base class for RAM disk backends.

This module defines the interface that all platform-specific backends must implement.
The interface provides a consistent API for RAM disk operations across platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import logging

from ..config import RamDiskConfig


@dataclass
class DiskUsage:
    """RAM disk usage statistics.

    Attributes:
        total_bytes: Total capacity in bytes
        used_bytes: Used space in bytes
        free_bytes: Available space in bytes
        percent_used: Usage percentage (0-100)
    """
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float

    @property
    def total_mb(self) -> float:
        """Total capacity in megabytes."""
        return self.total_bytes / (1024 * 1024)

    @property
    def used_mb(self) -> float:
        """Used space in megabytes."""
        return self.used_bytes / (1024 * 1024)

    @property
    def free_mb(self) -> float:
        """Free space in megabytes."""
        return self.free_bytes / (1024 * 1024)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "total_bytes": self.total_bytes,
            "used_bytes": self.used_bytes,
            "free_bytes": self.free_bytes,
            "percent_used": self.percent_used,
            "total_mb": round(self.total_mb, 2),
            "used_mb": round(self.used_mb, 2),
            "free_mb": round(self.free_mb, 2),
        }


@dataclass
class BackendResult:
    """Result of a backend operation.

    Attributes:
        success: Whether the operation succeeded
        message: Human-readable status message
        path: Path to the RAM disk (if applicable)
        error: Exception if operation failed
    """
    success: bool
    message: str
    path: Optional[Path] = None
    error: Optional[Exception] = None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "message": self.message,
            "path": str(self.path) if self.path else None,
            "error": str(self.error) if self.error else None,
        }


class RamDiskBackend(ABC):
    """Abstract base class for RAM disk backends.

    Each platform-specific backend must implement these methods to provide
    consistent RAM disk operations across different operating systems.

    Example:
        class LinuxBackend(RamDiskBackend):
            def is_available(self) -> bool:
                return os.path.exists("/dev/shm")
            # ... implement other methods
    """

    def __init__(self):
        """Initialize the backend with a logger."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system.

        This should check for required dependencies, drivers, and permissions.

        Returns:
            bool: True if the backend can be used
        """
        pass

    @abstractmethod
    def get_availability_message(self) -> str:
        """Get a human-readable message about backend availability.

        Returns:
            str: Description of availability status and any issues
        """
        pass

    @abstractmethod
    def create(self, config: RamDiskConfig) -> BackendResult:
        """Create a RAM disk according to the configuration.

        This should:
        1. Allocate RAM for the disk
        2. Format the filesystem
        3. Mount at the specified path

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result with path to mounted RAM disk
        """
        pass

    @abstractmethod
    def exists(self, config: RamDiskConfig) -> bool:
        """Check if a RAM disk exists and is mounted.

        Args:
            config: RAM disk configuration

        Returns:
            bool: True if RAM disk exists and is accessible
        """
        pass

    @abstractmethod
    def destroy(self, config: RamDiskConfig) -> BackendResult:
        """Destroy a RAM disk and free its memory.

        This should:
        1. Unmount the filesystem
        2. Release the RAM back to the system

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the destroy operation
        """
        pass

    @abstractmethod
    def get_usage(self, config: RamDiskConfig) -> Optional[DiskUsage]:
        """Get disk usage statistics for a RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            DiskUsage: Usage statistics, or None if disk doesn't exist
        """
        pass

    @abstractmethod
    def persist_config(self, config: RamDiskConfig) -> BackendResult:
        """Configure the RAM disk to persist across reboots.

        This sets up automatic recreation of the RAM disk on system startup.
        The actual data sync must be handled separately.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the persistence setup
        """
        pass

    @abstractmethod
    def remove_persistence(self, config: RamDiskConfig) -> BackendResult:
        """Remove automatic startup configuration for a RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the removal operation
        """
        pass

    def validate_config(self, config: RamDiskConfig) -> Optional[str]:
        """Validate a RAM disk configuration.

        Args:
            config: Configuration to validate

        Returns:
            str: Error message if invalid, None if valid
        """
        if config.size_mb < 1:
            return "Size must be at least 1 MB"
        if config.size_mb > 65536:  # 64 GB max for sanity
            return "Size cannot exceed 65536 MB (64 GB)"
        if not config.disk_path:
            return "disk_path is required"
        return None

    def ensure_config_path(self, config: RamDiskConfig) -> Path:
        """Ensure the config has a ram_path, generating one if needed.

        Args:
            config: RAM disk configuration

        Returns:
            Path: The ram_path to use
        """
        if config.ram_path:
            return config.ram_path
        # Subclasses should override to provide platform-specific defaults
        raise ValueError("ram_path must be specified in config")
