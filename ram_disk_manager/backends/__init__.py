"""RAM Disk Manager Backends.

This module provides platform-specific backends for RAM disk operations.
Each backend implements the RamDiskBackend interface.

Available backends:
    - WindowsBackend: Windows implementation using ImDisk
    - LinuxBackend: Linux implementation using tmpfs or /dev/shm fallback
    - MacOSBackend: macOS implementation using hdiutil/diskutil

Usage:
    from ram_disk_manager.backends import get_backend

    backend = get_backend()  # Auto-detect platform
    if backend.is_available():
        path = backend.create(config)
"""

from typing import Optional, Type
import platform

from .base import RamDiskBackend


def get_backend(force_platform: Optional[str] = None) -> RamDiskBackend:
    """Get the appropriate backend for the current platform.

    Args:
        force_platform: Override platform detection ("windows", "linux", or "darwin")

    Returns:
        RamDiskBackend: Platform-specific backend instance

    Raises:
        NotImplementedError: If platform is not supported
    """
    target = force_platform or platform.system().lower()

    if target == "windows":
        from .windows import WindowsBackend
        return WindowsBackend()
    elif target == "linux":
        from .linux import LinuxBackend
        return LinuxBackend()
    elif target == "darwin":
        from .macos import MacOSBackend
        return MacOSBackend()
    else:
        raise NotImplementedError(
            f"Platform '{target}' is not supported. "
            f"Supported platforms: windows, linux, darwin (macOS)"
        )


def get_backend_class(platform_name: str) -> Type[RamDiskBackend]:
    """Get the backend class for a specific platform.

    Args:
        platform_name: Platform name ("windows", "linux", or "darwin")

    Returns:
        Type[RamDiskBackend]: Backend class for the platform

    Raises:
        NotImplementedError: If platform is not supported
    """
    if platform_name == "windows":
        from .windows import WindowsBackend
        return WindowsBackend
    elif platform_name == "linux":
        from .linux import LinuxBackend
        return LinuxBackend
    elif platform_name == "darwin":
        from .macos import MacOSBackend
        return MacOSBackend
    else:
        raise NotImplementedError(
            f"Platform '{platform_name}' is not supported. "
            f"Supported platforms: windows, linux, darwin (macOS)"
        )


__all__ = [
    "RamDiskBackend",
    "get_backend",
    "get_backend_class",
]
