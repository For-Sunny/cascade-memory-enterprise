"""macOS backend for RAM disk operations using diskutil.

This backend uses macOS built-in diskutil and hdiutil commands to create
RAM disks backed by memory. No third-party tools required.

Requirements:
    - macOS 10.13+ (High Sierra or later)
    - Administrator privileges for some operations (mounting at custom paths)

Typical usage:
    backend = MacOSBackend()
    if backend.is_available():
        result = backend.create(config)
        if result.success:
            print(f"RAM disk at {result.path}")
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .base import BackendResult, DiskUsage, RamDiskBackend
from ..config import RamDiskConfig


class MacOSBackend(RamDiskBackend):
    """macOS RAM disk backend using hdiutil and diskutil.

    This backend creates RAM disks on macOS using the native disk image
    tools. It handles:
    - Creating RAM-backed disk images via hdiutil
    - Formatting with APFS or HFS+
    - Mount/unmount operations
    - LaunchDaemon integration for persistence

    The approach:
    1. hdiutil attach -nomount ram://SECTORS  (allocates RAM)
    2. diskutil eraseDisk HFS+ NAME /dev/diskN (formats)
    3. Result is mounted at /Volumes/NAME

    Attributes:
        hdiutil_path: Path to hdiutil
        diskutil_path: Path to diskutil
    """

    # Default mount base
    DEFAULT_MOUNT_BASE = Path("/Volumes")

    # LaunchDaemon directory for persistence
    LAUNCH_DAEMON_DIR = Path("/Library/LaunchDaemons")

    # Plist identifier prefix
    PLIST_PREFIX = "com.cascade.ramdisk"

    def __init__(self):
        """Initialize macOS backend."""
        super().__init__()
        self.hdiutil_path: Optional[Path] = self._find_tool("hdiutil")
        self.diskutil_path: Optional[Path] = self._find_tool("diskutil")

    def _find_tool(self, name: str) -> Optional[Path]:
        """Locate a system tool.

        Args:
            name: Tool name to find

        Returns:
            Path to the tool or None if not found
        """
        tool_path = shutil.which(name)
        if tool_path:
            return Path(tool_path)
        # Check common macOS locations
        for prefix in ["/usr/bin", "/usr/sbin", "/bin", "/sbin"]:
            candidate = Path(prefix) / name
            if candidate.exists():
                return candidate
        return None

    def _is_admin(self) -> bool:
        """Check if running with root privileges."""
        return os.geteuid() == 0

    def _run_command(
        self,
        cmd: List[str],
        check: bool = False
    ) -> Tuple[int, str, str]:
        """Run a command and return results.

        Args:
            cmd: Command and arguments
            check: Raise exception on non-zero exit

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        self.logger.debug(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout or "", e.stderr or ""
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"

    def _mb_to_sectors(self, size_mb: int) -> int:
        """Convert megabytes to 512-byte sectors for hdiutil.

        Args:
            size_mb: Size in megabytes

        Returns:
            Number of 512-byte sectors
        """
        return size_mb * 2048  # 1 MB = 2048 sectors of 512 bytes

    def _get_ram_path(self, config: RamDiskConfig) -> Path:
        """Determine the mount path for the RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            Path where RAM disk will be mounted
        """
        if config.ram_path:
            return config.ram_path
        # Default: /Volumes/RAMDISK_<name>
        volume_name = f"RAMDISK_{config.name.upper()}"
        return self.DEFAULT_MOUNT_BASE / volume_name

    def _get_volume_name(self, config: RamDiskConfig) -> str:
        """Get the volume name for a RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            Volume name string
        """
        return f"RAMDISK_{config.name.upper()}"

    def _find_disk_device(self, volume_name: str) -> Optional[str]:
        """Find the disk device for a mounted volume.

        Args:
            volume_name: Name of the volume to find

        Returns:
            Device path (e.g., /dev/disk2) or None
        """
        code, stdout, stderr = self._run_command(
            [str(self.diskutil_path), "list"]
        )
        if code != 0:
            return None

        # Parse diskutil list output to find our volume
        current_disk = None
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("/dev/disk"):
                current_disk = line.split()[0]
            elif volume_name in line and current_disk:
                return current_disk

        # Alternative: check mount output
        code, stdout, stderr = self._run_command(["mount"])
        if code == 0:
            for line in stdout.splitlines():
                if f"/Volumes/{volume_name}" in line:
                    # Format: /dev/diskNsM on /Volumes/NAME (...)
                    parts = line.split()
                    if parts:
                        # Get the base disk device (strip partition suffix)
                        device = parts[0]
                        # /dev/disk2s1 -> /dev/disk2
                        import re
                        match = re.match(r"(/dev/disk\d+)", device)
                        if match:
                            return match.group(1)

        return None

    def is_available(self) -> bool:
        """Check if hdiutil and diskutil are available."""
        return (
            self.hdiutil_path is not None and
            self.diskutil_path is not None
        )

    def get_availability_message(self) -> str:
        """Get a message about tool availability."""
        if self.is_available():
            admin_status = "with root" if self._is_admin() else "without root"
            return f"hdiutil and diskutil available ({admin_status})"
        missing = []
        if not self.hdiutil_path:
            missing.append("hdiutil")
        if not self.diskutil_path:
            missing.append("diskutil")
        return f"Missing tools: {', '.join(missing)}. macOS system tools required."

    def ensure_config_path(self, config: RamDiskConfig) -> Path:
        """Generate a macOS path for the RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            Path to the RAM disk volume
        """
        return self._get_ram_path(config)

    def create(self, config: RamDiskConfig) -> BackendResult:
        """Create a RAM disk using hdiutil.

        Steps:
        1. Allocate RAM-backed device: hdiutil attach -nomount ram://SECTORS
        2. Format device: diskutil eraseDisk HFS+ NAME /dev/diskN
        3. Disk is automatically mounted at /Volumes/NAME

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result with path to the created RAM disk
        """
        error = self.validate_config(config)
        if error:
            return BackendResult(success=False, message=error)

        if not self.is_available():
            return BackendResult(
                success=False,
                message=self.get_availability_message()
            )

        # Check if already exists
        if self.exists(config):
            ram_path = self._get_ram_path(config)
            return BackendResult(
                success=True,
                message=f"RAM disk already exists at {ram_path}",
                path=ram_path
            )

        try:
            volume_name = self._get_volume_name(config)
            sectors = self._mb_to_sectors(config.size_mb)

            # Step 1: Create RAM-backed device
            code, stdout, stderr = self._run_command([
                str(self.hdiutil_path), "attach",
                "-nomount", f"ram://{sectors}"
            ])

            if code != 0:
                return BackendResult(
                    success=False,
                    message=f"Failed to allocate RAM device: {stderr.strip()}"
                )

            # stdout contains the device path, e.g., /dev/disk2
            device = stdout.strip()
            if not device.startswith("/dev/"):
                return BackendResult(
                    success=False,
                    message=f"Unexpected device path: {device}"
                )

            self.logger.info(f"Allocated RAM device: {device}")

            # Step 2: Format as HFS+
            code, stdout, stderr = self._run_command([
                str(self.diskutil_path), "eraseDisk",
                "HFS+", volume_name, device
            ])

            if code != 0:
                # Clean up: detach the device
                self._run_command([
                    str(self.hdiutil_path), "detach", device
                ])
                return BackendResult(
                    success=False,
                    message=f"Failed to format RAM disk: {stderr.strip()}"
                )

            # The disk is now mounted at /Volumes/VOLUME_NAME
            ram_path = self.DEFAULT_MOUNT_BASE / volume_name

            if ram_path.exists():
                config.ram_path = ram_path
                self.logger.info(
                    f"Created {config.size_mb}MB RAM disk at {ram_path}"
                )
                return BackendResult(
                    success=True,
                    message=f"Created {config.size_mb}MB RAM disk at {ram_path}",
                    path=ram_path
                )
            else:
                return BackendResult(
                    success=False,
                    message="RAM disk created but mount point not found"
                )

        except Exception as e:
            self.logger.error(f"Unexpected error creating RAM disk: {e}")
            return BackendResult(
                success=False,
                message=f"Error: {e}",
                error=e
            )

    def exists(self, config: RamDiskConfig) -> bool:
        """Check if the RAM disk exists and is mounted.

        Args:
            config: RAM disk configuration

        Returns:
            bool: True if RAM disk exists
        """
        ram_path = self._get_ram_path(config)
        return ram_path.exists() and ram_path.is_dir()

    def destroy(self, config: RamDiskConfig) -> BackendResult:
        """Destroy a RAM disk by ejecting/detaching the device.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the destroy operation
        """
        if not self.is_available():
            return BackendResult(
                success=False,
                message=self.get_availability_message()
            )

        ram_path = self._get_ram_path(config)
        volume_name = self._get_volume_name(config)

        if not self.exists(config):
            return BackendResult(
                success=True,
                message=f"RAM disk does not exist: {ram_path}"
            )

        try:
            # Find the device for this volume
            device = self._find_disk_device(volume_name)

            if device:
                # Detach using hdiutil (frees RAM)
                code, stdout, stderr = self._run_command([
                    str(self.hdiutil_path), "detach", device
                ])

                if code != 0:
                    # Try force detach
                    code, stdout, stderr = self._run_command([
                        str(self.hdiutil_path), "detach", "-force", device
                    ])

                    if code != 0:
                        return BackendResult(
                            success=False,
                            message=f"Failed to detach device: {stderr.strip()}"
                        )
            else:
                # Try ejecting by volume path
                code, stdout, stderr = self._run_command([
                    str(self.diskutil_path), "eject", str(ram_path)
                ])

                if code != 0:
                    return BackendResult(
                        success=False,
                        message=f"Failed to eject volume: {stderr.strip()}"
                    )

            self.logger.info(f"Destroyed RAM disk at {ram_path}")
            return BackendResult(
                success=True,
                message=f"Destroyed RAM disk at {ram_path}",
                path=ram_path
            )

        except Exception as e:
            self.logger.error(f"Error destroying RAM disk: {e}")
            return BackendResult(
                success=False,
                message=f"Error: {e}",
                error=e
            )

    def get_usage(self, config: RamDiskConfig) -> Optional[DiskUsage]:
        """Get disk usage statistics.

        Args:
            config: RAM disk configuration

        Returns:
            DiskUsage: Usage statistics, or None if disk does not exist
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
        """Configure a LaunchDaemon to recreate RAM disk on boot.

        Creates a plist in /Library/LaunchDaemons that runs on system
        startup to recreate the RAM disk.

        Requires root privileges.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the persistence setup
        """
        if not self._is_admin():
            return BackendResult(
                success=False,
                message="Root privileges required to create LaunchDaemon"
            )

        try:
            volume_name = self._get_volume_name(config)
            sectors = self._mb_to_sectors(config.size_mb)
            plist_name = f"{self.PLIST_PREFIX}.{config.name}.plist"
            plist_path = self.LAUNCH_DAEMON_DIR / plist_name

            # Create a shell script that creates the RAM disk
            script_content = f"""#!/bin/bash
DEVICE=$(hdiutil attach -nomount ram://{sectors})
diskutil eraseDisk HFS+ {volume_name} $DEVICE
"""

            script_path = Path(f"/usr/local/bin/ramdisk-{config.name}.sh")
            script_path.write_text(script_content)
            script_path.chmod(0o755)

            # Create LaunchDaemon plist
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.PLIST_PREFIX}.{config.name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/var/log/ramdisk-{config.name}.log</string>
</dict>
</plist>
"""

            plist_path.write_text(plist_content)
            plist_path.chmod(0o644)

            # Load the daemon
            self._run_command(["launchctl", "load", str(plist_path)])

            self.logger.info(f"Created LaunchDaemon for {config.name}")
            return BackendResult(
                success=True,
                message=f"Created LaunchDaemon '{plist_name}'"
            )

        except Exception as e:
            self.logger.error(f"Error creating LaunchDaemon: {e}")
            return BackendResult(
                success=False,
                message=f"Error: {e}",
                error=e
            )

    def remove_persistence(self, config: RamDiskConfig) -> BackendResult:
        """Remove the LaunchDaemon for a RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the removal
        """
        if not self._is_admin():
            return BackendResult(
                success=False,
                message="Root privileges required to remove LaunchDaemon"
            )

        try:
            plist_name = f"{self.PLIST_PREFIX}.{config.name}.plist"
            plist_path = self.LAUNCH_DAEMON_DIR / plist_name
            script_path = Path(f"/usr/local/bin/ramdisk-{config.name}.sh")

            # Unload the daemon
            if plist_path.exists():
                self._run_command(["launchctl", "unload", str(plist_path)])
                plist_path.unlink()

            # Remove the script
            if script_path.exists():
                script_path.unlink()

            self.logger.info(f"Removed LaunchDaemon for {config.name}")
            return BackendResult(
                success=True,
                message=f"Removed LaunchDaemon '{plist_name}'"
            )

        except Exception as e:
            self.logger.error(f"Error removing LaunchDaemon: {e}")
            return BackendResult(
                success=False,
                message=f"Error: {e}",
                error=e
            )

    def list_ram_disks(self) -> List[dict]:
        """List RAM disks created by this backend.

        Searches /Volumes for volumes matching the RAMDISK_ prefix.

        Returns:
            List of dicts with name, path, and size info
        """
        results = []

        if not self.DEFAULT_MOUNT_BASE.exists():
            return results

        for child in self.DEFAULT_MOUNT_BASE.iterdir():
            if child.is_dir() and child.name.startswith("RAMDISK_"):
                name = child.name.replace("RAMDISK_", "").lower()
                try:
                    stat = os.statvfs(child)
                    size_mb = (stat.f_blocks * stat.f_frsize) / (1024 * 1024)
                    results.append({
                        "name": name,
                        "path": str(child),
                        "size_mb": round(size_mb, 2),
                        "type": "hdiutil"
                    })
                except OSError:
                    results.append({
                        "name": name,
                        "path": str(child),
                        "size_mb": None,
                        "type": "hdiutil"
                    })

        return results
