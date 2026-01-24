"""Platform detection and privilege checking utilities.

Handles Windows/Linux differences for:
- Admin/root privilege detection
- Default RAM disk paths
- Platform-specific behaviors
"""

import ctypes
import os
import sys
from pathlib import Path

# Import Platform enum from config to maintain single source of truth
from ram_disk_manager.config import Platform


def detect_platform() -> Platform:
    """Detect the current operating system platform.

    Returns:
        Platform.WINDOWS, Platform.LINUX, or Platform.MACOS based on sys.platform

    Example:
        >>> platform = detect_platform()
        >>> if platform == Platform.WINDOWS:
        ...     print("Running on Windows")
    """
    if sys.platform == "win32":
        return Platform.WINDOWS
    elif sys.platform == "darwin":
        return Platform.MACOS
    elif sys.platform.startswith("linux"):
        return Platform.LINUX
    else:
        # Default to Linux for other Unix-like systems
        return Platform.LINUX


def is_admin() -> bool:
    """Check if the current process has elevated privileges.

    On Windows: Checks for Administrator rights
    On Linux/macOS: Checks for root (UID 0)

    Returns:
        True if running with elevated privileges, False otherwise

    Example:
        >>> if not is_admin():
        ...     print("Warning: Some operations may require admin privileges")
    """
    platform = detect_platform()

    if platform == Platform.WINDOWS:
        try:
            # Windows-specific admin check
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except (AttributeError, OSError):
            # Fallback: try to access a protected location
            try:
                # Try to write to a Windows-protected location
                test_path = Path(os.environ.get("SYSTEMROOT", "C:\\Windows")) / "temp_admin_test"
                test_path.touch()
                test_path.unlink()
                return True
            except (PermissionError, OSError):
                return False
    else:
        # Linux/Unix: check for root
        return os.geteuid() == 0


def get_default_ram_path(platform: Platform) -> Path:
    """Get the default RAM disk mount path for the given platform.

    Args:
        platform: Target platform (WINDOWS, LINUX, MACOS, or AUTO)

    Returns:
        Default Path for RAM disk mount point

    Platform defaults:
        - Windows: R:\\ (common RAM disk drive letter)
        - Linux: /mnt/ramdisk (tmpfs mount point)
        - macOS: /Volumes (hdiutil mount location)

    Example:
        >>> path = get_default_ram_path(Platform.WINDOWS)
        >>> print(path)  # R:\\
    """
    # Resolve AUTO to actual platform
    if platform == Platform.AUTO:
        platform = detect_platform()

    if platform == Platform.WINDOWS:
        return Path("R:\\")
    elif platform == Platform.MACOS:
        return Path("/Volumes")
    else:
        return Path("/mnt/ramdisk")


def get_temp_path(platform: Platform) -> Path:
    """Get platform-appropriate temporary directory.

    Args:
        platform: Target platform

    Returns:
        Path to system temp directory
    """
    if platform == Platform.AUTO:
        platform = detect_platform()

    if platform == Platform.WINDOWS:
        return Path(os.environ.get("TEMP", "C:\\Temp"))
    else:
        # Linux and macOS both use /tmp
        return Path("/tmp")


def ensure_path_exists(path: Path, is_dir: bool = True) -> bool:
    """Ensure a path exists, creating it if necessary.

    Args:
        path: Path to ensure exists
        is_dir: If True, create as directory. If False, create parent dirs only.

    Returns:
        True if path exists or was created, False on failure
    """
    try:
        if is_dir:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except (PermissionError, OSError):
        return False


def check_ram_disk_available(ram_path: Path) -> bool:
    """Check if a RAM disk is mounted and accessible.

    Args:
        ram_path: Path to RAM disk mount point

    Returns:
        True if the path exists and is writable
    """
    if not ram_path.exists():
        return False

    # Try to write a test file
    test_file = ram_path / ".ram_disk_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        return True
    except (PermissionError, OSError):
        return False
