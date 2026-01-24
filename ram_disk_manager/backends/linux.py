"""Linux backend for RAM disk operations using tmpfs.

This module provides RAM disk support on Linux systems through two mechanisms:
1. tmpfs mount (requires root) - Full control with custom mount points
2. /dev/shm fallback (no root) - Uses system shared memory directory

Features:
- Automatic detection of available permissions
- Graceful fallback from tmpfs to /dev/shm
- fstab integration for persistence (when root)
- Proper error handling for all scenarios
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from .base import RamDiskBackend, BackendResult, DiskUsage
from ..config import RamDiskConfig


class LinuxBackend(RamDiskBackend):
    """Linux backend using tmpfs or /dev/shm fallback.

    This backend supports two modes of operation:

    1. Root mode (tmpfs):
       - Creates dedicated tmpfs mounts at custom mount points
       - Full control over size, permissions, and mount options
       - Supports fstab persistence for automatic remounting

    2. Non-root mode (/dev/shm fallback):
       - Uses subdirectories in /dev/shm (system tmpfs)
       - No root required, uses existing system tmpfs
       - Size limited by system /dev/shm configuration
       - No fstab persistence (already system-managed)

    Example:
        backend = LinuxBackend()

        if backend.is_available():
            config = RamDiskConfig(
                name="mydata",
                disk_path=Path("/home/user/persistent"),
                size_mb=256
            )
            result = backend.create(config)
            if result.success:
                print(f"RAM disk at: {result.path}")
    """

    # Default mount point base for tmpfs
    DEFAULT_MOUNT_BASE = Path("/mnt/ramdisk")

    # Fallback for non-root users
    DEV_SHM_PATH = Path("/dev/shm")

    # fstab path
    FSTAB_PATH = Path("/etc/fstab")

    # Marker comment for fstab entries
    FSTAB_MARKER = "# ram-disk-manager:"

    def __init__(self):
        """Initialize Linux backend."""
        super().__init__()
        self._is_root: Optional[bool] = None
        self._has_mount_cmd: Optional[bool] = None
        self._dev_shm_available: Optional[bool] = None

    @property
    def is_root(self) -> bool:
        """Check if running as root."""
        if self._is_root is None:
            self._is_root = os.geteuid() == 0
        return self._is_root

    @property
    def has_mount_command(self) -> bool:
        """Check if mount command is available."""
        if self._has_mount_cmd is None:
            self._has_mount_cmd = shutil.which("mount") is not None
        return self._has_mount_cmd

    @property
    def dev_shm_available(self) -> bool:
        """Check if /dev/shm is available and writable."""
        if self._dev_shm_available is None:
            self._dev_shm_available = (
                self.DEV_SHM_PATH.exists() and
                os.access(self.DEV_SHM_PATH, os.W_OK)
            )
        return self._dev_shm_available

    def is_available(self) -> bool:
        """Check if this backend is available on the current system.

        Returns True if either:
        - Running as root with mount command available
        - /dev/shm exists and is writable

        Returns:
            bool: True if the backend can be used
        """
        if self.is_root and self.has_mount_command:
            return True
        return self.dev_shm_available

    def get_availability_message(self) -> str:
        """Get a human-readable message about backend availability.

        Returns:
            str: Description of availability status and capabilities
        """
        messages = []

        if self.is_root:
            messages.append("Running as root - full tmpfs support available")
            if not self.has_mount_command:
                messages.append("WARNING: mount command not found")
        else:
            messages.append("Running as non-root user")

        if self.dev_shm_available:
            messages.append("/dev/shm available for fallback")
        else:
            messages.append("/dev/shm not available or not writable")

        if self.is_available():
            messages.append("Backend is AVAILABLE")
        else:
            messages.append("Backend is NOT AVAILABLE")

        return "\n".join(messages)

    def _get_ram_path(self, config: RamDiskConfig) -> Path:
        """Determine the RAM disk path based on config and permissions.

        Args:
            config: RAM disk configuration

        Returns:
            Path: The path to use for the RAM disk
        """
        if config.ram_path:
            return config.ram_path

        if self.is_root:
            # Root can mount anywhere, use standard location
            return self.DEFAULT_MOUNT_BASE / config.name
        else:
            # Non-root uses /dev/shm subdirectory
            return self.DEV_SHM_PATH / f"ram-disk-{config.name}"

    def _run_command(
        self,
        cmd: list[str],
        check: bool = True,
        capture_output: bool = True
    ) -> Tuple[int, str, str]:
        """Run a shell command and return results.

        Args:
            cmd: Command and arguments
            check: Raise exception on non-zero exit
            capture_output: Capture stdout/stderr

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        self.logger.debug(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=capture_output,
                text=True
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout or "", e.stderr or ""
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"

    def _is_mountpoint(self, path: Path) -> bool:
        """Check if a path is a mount point.

        Args:
            path: Path to check

        Returns:
            bool: True if path is a mount point
        """
        if not path.exists():
            return False

        # Use mountpoint command if available
        if shutil.which("mountpoint"):
            code, _, _ = self._run_command(
                ["mountpoint", "-q", str(path)],
                check=False
            )
            return code == 0

        # Fallback: check /proc/mounts
        try:
            with open("/proc/mounts", "r") as f:
                mounts = f.read()
            return str(path) in mounts
        except IOError:
            return False

    def _is_tmpfs(self, path: Path) -> bool:
        """Check if a path is on a tmpfs filesystem.

        Args:
            path: Path to check

        Returns:
            bool: True if path is on tmpfs
        """
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[1]
                        fs_type = parts[2]
                        # Check if path starts with this mount point
                        if str(path).startswith(mount_point) and fs_type == "tmpfs":
                            return True
        except IOError:
            pass
        return False

    def _get_shm_usage(self) -> Optional[DiskUsage]:
        """Get /dev/shm usage statistics.

        Returns:
            DiskUsage or None if unable to get stats
        """
        if not self.DEV_SHM_PATH.exists():
            return None

        try:
            stat = os.statvfs(self.DEV_SHM_PATH)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            percent = (used / total * 100) if total > 0 else 0

            return DiskUsage(
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                percent_used=round(percent, 2)
            )
        except OSError as e:
            self.logger.error(f"Failed to get /dev/shm stats: {e}")
            return None

    def create(self, config: RamDiskConfig) -> BackendResult:
        """Create a RAM disk according to the configuration.

        For root users:
            Creates a new tmpfs mount at the specified or default path.

        For non-root users:
            Creates a subdirectory in /dev/shm.
            Note: Size limit is advisory only (enforced by system /dev/shm size).

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result with path to mounted RAM disk
        """
        # Validate config
        error = self.validate_config(config)
        if error:
            return BackendResult(
                success=False,
                message=f"Invalid configuration: {error}"
            )

        ram_path = self._get_ram_path(config)

        # Check if already exists
        if self.exists(config):
            return BackendResult(
                success=True,
                message=f"RAM disk already exists at {ram_path}",
                path=ram_path
            )

        try:
            if self.is_root:
                return self._create_tmpfs_mount(config, ram_path)
            else:
                return self._create_shm_directory(config, ram_path)
        except Exception as e:
            self.logger.exception(f"Failed to create RAM disk: {e}")
            return BackendResult(
                success=False,
                message=f"Failed to create RAM disk: {e}",
                error=e
            )

    def _create_tmpfs_mount(
        self,
        config: RamDiskConfig,
        ram_path: Path
    ) -> BackendResult:
        """Create a tmpfs mount (requires root).

        Args:
            config: RAM disk configuration
            ram_path: Path to mount at

        Returns:
            BackendResult: Result of the mount operation
        """
        # Create mount point directory
        try:
            ram_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return BackendResult(
                success=False,
                message=f"Permission denied creating mount point: {ram_path}"
            )
        except OSError as e:
            return BackendResult(
                success=False,
                message=f"Failed to create mount point: {e}",
                error=e
            )

        # Mount tmpfs
        size_opt = f"size={config.size_mb}M"
        cmd = [
            "mount", "-t", "tmpfs",
            "-o", f"{size_opt},mode=0755",
            "tmpfs", str(ram_path)
        ]

        code, stdout, stderr = self._run_command(cmd, check=False)

        if code != 0:
            return BackendResult(
                success=False,
                message=f"Mount failed: {stderr.strip() or 'Unknown error'}"
            )

        self.logger.info(f"Created tmpfs mount at {ram_path} ({config.size_mb}MB)")

        return BackendResult(
            success=True,
            message=f"Created tmpfs mount at {ram_path} ({config.size_mb}MB)",
            path=ram_path
        )

    def _create_shm_directory(
        self,
        config: RamDiskConfig,
        ram_path: Path
    ) -> BackendResult:
        """Create a directory in /dev/shm (non-root fallback).

        Args:
            config: RAM disk configuration
            ram_path: Path to create

        Returns:
            BackendResult: Result of the directory creation
        """
        if not self.dev_shm_available:
            return BackendResult(
                success=False,
                message="/dev/shm is not available or not writable"
            )

        # Check available space
        shm_usage = self._get_shm_usage()
        if shm_usage:
            required_bytes = config.size_mb * 1024 * 1024
            if shm_usage.free_bytes < required_bytes:
                return BackendResult(
                    success=False,
                    message=(
                        f"Insufficient space in /dev/shm: "
                        f"need {config.size_mb}MB, "
                        f"available {shm_usage.free_mb:.1f}MB"
                    )
                )

        try:
            ram_path.mkdir(parents=True, exist_ok=True)
            # Set permissions
            ram_path.chmod(0o755)
        except PermissionError:
            return BackendResult(
                success=False,
                message=f"Permission denied creating directory: {ram_path}"
            )
        except OSError as e:
            return BackendResult(
                success=False,
                message=f"Failed to create directory: {e}",
                error=e
            )

        self.logger.info(
            f"Created /dev/shm directory at {ram_path} "
            f"(advisory size: {config.size_mb}MB)"
        )

        return BackendResult(
            success=True,
            message=(
                f"Created /dev/shm directory at {ram_path}. "
                f"Note: Size limit ({config.size_mb}MB) is advisory only."
            ),
            path=ram_path
        )

    def exists(self, config: RamDiskConfig) -> bool:
        """Check if a RAM disk exists and is accessible.

        For tmpfs mounts: Checks if the path is a mount point.
        For /dev/shm: Checks if the directory exists.

        Args:
            config: RAM disk configuration

        Returns:
            bool: True if RAM disk exists and is accessible
        """
        ram_path = self._get_ram_path(config)

        if not ram_path.exists():
            return False

        if self.is_root:
            # For root, verify it's actually a mount point
            return self._is_mountpoint(ram_path)
        else:
            # For non-root, just check the directory exists in /dev/shm
            return ram_path.exists() and self._is_tmpfs(ram_path)

    def destroy(self, config: RamDiskConfig) -> BackendResult:
        """Destroy a RAM disk and free its memory.

        For tmpfs mounts: Unmounts the filesystem.
        For /dev/shm directories: Removes the directory and contents.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the destroy operation
        """
        ram_path = self._get_ram_path(config)

        if not ram_path.exists():
            return BackendResult(
                success=True,
                message=f"RAM disk does not exist: {ram_path}"
            )

        try:
            if self.is_root and self._is_mountpoint(ram_path):
                return self._unmount_tmpfs(ram_path)
            else:
                return self._remove_shm_directory(ram_path)
        except Exception as e:
            self.logger.exception(f"Failed to destroy RAM disk: {e}")
            return BackendResult(
                success=False,
                message=f"Failed to destroy RAM disk: {e}",
                error=e
            )

    def _unmount_tmpfs(self, ram_path: Path) -> BackendResult:
        """Unmount a tmpfs filesystem.

        Args:
            ram_path: Path to unmount

        Returns:
            BackendResult: Result of the unmount operation
        """
        # Try normal unmount first
        code, stdout, stderr = self._run_command(
            ["umount", str(ram_path)],
            check=False
        )

        if code != 0:
            # Try lazy unmount if normal fails
            self.logger.warning(
                f"Normal unmount failed, trying lazy unmount: {stderr.strip()}"
            )
            code, stdout, stderr = self._run_command(
                ["umount", "-l", str(ram_path)],
                check=False
            )

            if code != 0:
                return BackendResult(
                    success=False,
                    message=f"Failed to unmount: {stderr.strip()}"
                )

        # Remove the mount point directory
        try:
            ram_path.rmdir()
        except OSError as e:
            self.logger.warning(f"Could not remove mount point: {e}")

        self.logger.info(f"Unmounted tmpfs at {ram_path}")

        return BackendResult(
            success=True,
            message=f"Unmounted tmpfs at {ram_path}",
            path=ram_path
        )

    def _remove_shm_directory(self, ram_path: Path) -> BackendResult:
        """Remove a /dev/shm directory.

        Args:
            ram_path: Directory to remove

        Returns:
            BackendResult: Result of the removal operation
        """
        # Safety check: only remove from /dev/shm
        try:
            ram_path.relative_to(self.DEV_SHM_PATH)
        except ValueError:
            return BackendResult(
                success=False,
                message=f"Refusing to remove directory outside /dev/shm: {ram_path}"
            )

        try:
            shutil.rmtree(ram_path)
        except PermissionError:
            return BackendResult(
                success=False,
                message=f"Permission denied removing: {ram_path}"
            )
        except OSError as e:
            return BackendResult(
                success=False,
                message=f"Failed to remove directory: {e}",
                error=e
            )

        self.logger.info(f"Removed /dev/shm directory: {ram_path}")

        return BackendResult(
            success=True,
            message=f"Removed /dev/shm directory: {ram_path}",
            path=ram_path
        )

    def get_usage(self, config: RamDiskConfig) -> Optional[DiskUsage]:
        """Get disk usage statistics for a RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            DiskUsage: Usage statistics, or None if disk doesn't exist
        """
        ram_path = self._get_ram_path(config)

        if not self.exists(config):
            return None

        try:
            stat = os.statvfs(ram_path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            percent = (used / total * 100) if total > 0 else 0

            return DiskUsage(
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                percent_used=round(percent, 2)
            )
        except OSError as e:
            self.logger.error(f"Failed to get usage stats: {e}")
            return None

    def persist_config(self, config: RamDiskConfig) -> BackendResult:
        """Configure the RAM disk to persist across reboots via fstab.

        This adds an entry to /etc/fstab for automatic tmpfs mounting.
        Only available when running as root.

        For non-root users, /dev/shm is already persistent (system-managed).

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the persistence setup
        """
        if not self.is_root:
            return BackendResult(
                success=True,
                message=(
                    "/dev/shm fallback mode: persistence is system-managed. "
                    "Directory will need to be recreated after reboot."
                )
            )

        ram_path = self._get_ram_path(config)

        # Build fstab entry
        fstab_entry = (
            f"tmpfs {ram_path} tmpfs "
            f"size={config.size_mb}M,mode=0755 0 0 "
            f"{self.FSTAB_MARKER} {config.name}"
        )

        try:
            # Read current fstab
            if self.FSTAB_PATH.exists():
                with open(self.FSTAB_PATH, "r") as f:
                    fstab_content = f.read()
            else:
                fstab_content = ""

            # Check if entry already exists
            marker_pattern = f"{self.FSTAB_MARKER} {config.name}"
            if marker_pattern in fstab_content:
                # Update existing entry
                lines = fstab_content.splitlines()
                new_lines = []
                for line in lines:
                    if marker_pattern in line:
                        new_lines.append(fstab_entry)
                    else:
                        new_lines.append(line)
                new_content = "\n".join(new_lines)
                if not new_content.endswith("\n"):
                    new_content += "\n"

                with open(self.FSTAB_PATH, "w") as f:
                    f.write(new_content)

                self.logger.info(f"Updated fstab entry for {config.name}")
                return BackendResult(
                    success=True,
                    message=f"Updated fstab entry for {config.name}",
                    path=ram_path
                )
            else:
                # Add new entry
                with open(self.FSTAB_PATH, "a") as f:
                    if not fstab_content.endswith("\n"):
                        f.write("\n")
                    f.write(fstab_entry + "\n")

                self.logger.info(f"Added fstab entry for {config.name}")
                return BackendResult(
                    success=True,
                    message=f"Added fstab entry for {config.name}",
                    path=ram_path
                )

        except PermissionError:
            return BackendResult(
                success=False,
                message="Permission denied writing to /etc/fstab"
            )
        except IOError as e:
            return BackendResult(
                success=False,
                message=f"Failed to modify fstab: {e}",
                error=e
            )

    def remove_persistence(self, config: RamDiskConfig) -> BackendResult:
        """Remove automatic startup configuration from fstab.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the removal operation
        """
        if not self.is_root:
            return BackendResult(
                success=True,
                message="/dev/shm fallback mode: no persistence to remove"
            )

        marker_pattern = f"{self.FSTAB_MARKER} {config.name}"

        try:
            if not self.FSTAB_PATH.exists():
                return BackendResult(
                    success=True,
                    message="No fstab file found"
                )

            with open(self.FSTAB_PATH, "r") as f:
                lines = f.readlines()

            # Filter out our entry
            new_lines = [
                line for line in lines
                if marker_pattern not in line
            ]

            if len(new_lines) == len(lines):
                return BackendResult(
                    success=True,
                    message=f"No fstab entry found for {config.name}"
                )

            with open(self.FSTAB_PATH, "w") as f:
                f.writelines(new_lines)

            self.logger.info(f"Removed fstab entry for {config.name}")

            return BackendResult(
                success=True,
                message=f"Removed fstab entry for {config.name}"
            )

        except PermissionError:
            return BackendResult(
                success=False,
                message="Permission denied modifying /etc/fstab"
            )
        except IOError as e:
            return BackendResult(
                success=False,
                message=f"Failed to modify fstab: {e}",
                error=e
            )

    def ensure_config_path(self, config: RamDiskConfig) -> Path:
        """Ensure the config has a ram_path, generating one if needed.

        Args:
            config: RAM disk configuration

        Returns:
            Path: The ram_path to use
        """
        return self._get_ram_path(config)

    def get_mode(self) -> str:
        """Get the current operating mode.

        Returns:
            str: "tmpfs" if running as root, "shm" otherwise
        """
        return "tmpfs" if self.is_root else "shm"

    def list_ram_disks(self) -> list[dict]:
        """List all RAM disks managed by this backend.

        Returns:
            List of dicts with name, path, and size info
        """
        results = []

        # Check for tmpfs mounts we created
        if self.is_root and self.DEFAULT_MOUNT_BASE.exists():
            for child in self.DEFAULT_MOUNT_BASE.iterdir():
                if child.is_dir() and self._is_mountpoint(child):
                    try:
                        stat = os.statvfs(child)
                        size_mb = (stat.f_blocks * stat.f_frsize) / (1024 * 1024)
                        results.append({
                            "name": child.name,
                            "path": str(child),
                            "size_mb": round(size_mb, 2),
                            "type": "tmpfs"
                        })
                    except OSError:
                        pass

        # Check for /dev/shm directories we created
        if self.DEV_SHM_PATH.exists():
            for child in self.DEV_SHM_PATH.iterdir():
                if child.is_dir() and child.name.startswith("ram-disk-"):
                    name = child.name.replace("ram-disk-", "")
                    results.append({
                        "name": name,
                        "path": str(child),
                        "size_mb": None,  # Size not tracked for shm dirs
                        "type": "shm"
                    })

        return results
