"""Crash detection via shutdown marker files.

The marker file approach:
1. On clean startup: clear_shutdown_marker() removes any existing marker
2. On clean shutdown: mark_clean_shutdown() writes marker with timestamp
3. On next startup: was_clean_shutdown() checks if marker exists

If marker is missing on startup, it indicates a crash (marker was never written).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ram_disk_manager.config import RamDiskConfig, ManagerConfig


def _get_marker_path(config: RamDiskConfig, manager_config: Optional[ManagerConfig] = None) -> Path:
    """Get the path to the shutdown marker file.

    The marker is stored in the disk_path (persistent storage) since
    RAM content is lost on crash/reboot.

    Args:
        config: RAM disk configuration
        manager_config: Optional manager config for marker filename

    Returns:
        Path to marker file
    """
    marker_name = ".ram_disk_clean_shutdown"
    if manager_config is not None:
        marker_name = manager_config.recovery_marker_file

    return config.disk_path / marker_name


def was_clean_shutdown(
    config: RamDiskConfig,
    manager_config: Optional[ManagerConfig] = None
) -> bool:
    """Check if the last shutdown was clean.

    A clean shutdown is indicated by the presence of a valid marker file
    in the disk_path. The marker contains a timestamp from when it was written.

    Args:
        config: RAM disk configuration
        manager_config: Optional manager config for marker filename

    Returns:
        True if marker exists and is valid, False otherwise (indicates crash)
    """
    marker_path = _get_marker_path(config, manager_config)

    if not marker_path.exists():
        return False

    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate marker structure
        if not isinstance(data, dict):
            return False
        if "clean_shutdown" not in data:
            return False
        if not data.get("clean_shutdown", False):
            return False

        # Marker is valid
        return True

    except (json.JSONDecodeError, OSError, KeyError):
        # Corrupted or unreadable marker - treat as crash
        return False


def mark_clean_shutdown(
    config: RamDiskConfig,
    manager_config: Optional[ManagerConfig] = None
) -> bool:
    """Write a clean shutdown marker.

    Called during clean shutdown to indicate that RAM content was
    properly synced to disk.

    Args:
        config: RAM disk configuration
        manager_config: Optional manager config for marker filename

    Returns:
        True if marker was written successfully, False otherwise
    """
    marker_path = _get_marker_path(config, manager_config)

    try:
        # Ensure parent directory exists
        marker_path.parent.mkdir(parents=True, exist_ok=True)

        marker_data = {
            "clean_shutdown": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": config.name,
            "disk_path": str(config.disk_path),
            "ram_path": str(config.ram_path) if config.ram_path else None,
        }

        with open(marker_path, "w", encoding="utf-8") as f:
            json.dump(marker_data, f, indent=2)

        return True

    except (OSError, IOError) as e:
        # Failed to write marker - log would go here
        return False


def clear_shutdown_marker(
    config: RamDiskConfig,
    manager_config: Optional[ManagerConfig] = None
) -> bool:
    """Remove the shutdown marker on startup.

    Called at the beginning of a session to clear any existing marker.
    This ensures that if a crash occurs, there will be no marker present
    on the next startup.

    Args:
        config: RAM disk configuration
        manager_config: Optional manager config for marker filename

    Returns:
        True if marker was removed or didn't exist, False on error
    """
    marker_path = _get_marker_path(config, manager_config)

    try:
        if marker_path.exists():
            marker_path.unlink()
        return True

    except OSError:
        # Failed to remove marker
        return False


def get_shutdown_info(
    config: RamDiskConfig,
    manager_config: Optional[ManagerConfig] = None
) -> Optional[dict]:
    """Get information from the shutdown marker if it exists.

    Args:
        config: RAM disk configuration
        manager_config: Optional manager config for marker filename

    Returns:
        Dict with marker info if valid, None otherwise
    """
    marker_path = _get_marker_path(config, manager_config)

    if not marker_path.exists():
        return None

    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
