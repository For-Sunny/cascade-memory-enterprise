"""Windows backend for RAM disk operations using ImDisk.

This backend uses ImDisk Virtual Disk Driver to create RAM disks on Windows.
ImDisk is a free, open-source virtual disk driver that supports RAM disks.

Requirements:
    - ImDisk installed (https://sourceforge.net/projects/imdisk-toolkit/)
    - Administrator privileges for create/destroy operations

Typical usage:
    backend = WindowsBackend()
    if backend.is_available():
        result = backend.create(config)
        if result.success:
            print(f"RAM disk at {result.path}")
"""

import ctypes
import logging
import os
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import List, Optional, Tuple

from .base import BackendResult, DiskUsage, RamDiskBackend
from ..config import RamDiskConfig


class WindowsBackend(RamDiskBackend):
    """Windows RAM disk backend using ImDisk.

    This backend provides RAM disk operations on Windows using the ImDisk
    Virtual Disk Driver. It handles:
    - Finding ImDisk installation
    - Creating and formatting RAM disks
    - Mount/unmount operations
    - Task Scheduler integration for persistence

    Attributes:
        imdisk_path: Path to imdisk.exe if found
        imdisk_cli_path: Path to imdisk-cli.exe if found
    """

    # Common installation paths for ImDisk
    IMDISK_SEARCH_PATHS = [
        Path(r"C:\Windows\System32\imdisk.exe"),
        Path(r"C:\Program Files\ImDisk\imdisk.exe"),
        Path(r"C:\Program Files (x86)\ImDisk\imdisk.exe"),
    ]

    # Registry key for ImDisk
    IMDISK_REGISTRY_KEY = r"SYSTEM\CurrentControlSet\Services\ImDisk"

    # Preferred drive letters (in order of preference)
    PREFERRED_DRIVE_LETTERS = ["R", "Z", "Y", "X", "W", "V", "U", "T", "S"]

    def __init__(self):
        """Initialize Windows backend."""
        super().__init__()
        self.imdisk_path: Optional[Path] = None
        self._find_imdisk()

    def _find_imdisk(self) -> None:
        """Locate ImDisk installation."""
        # Try common paths first
        for path in self.IMDISK_SEARCH_PATHS:
            if path.exists():
                self.imdisk_path = path
                self.logger.debug(f"Found ImDisk at {path}")
                return

        # Try to find via registry
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self.IMDISK_REGISTRY_KEY) as key:
                image_path = winreg.QueryValueEx(key, "ImagePath")[0]
                # ImagePath points to the driver, derive imdisk.exe location
                driver_path = Path(image_path.replace("\\SystemRoot", str(Path(os.environ["SystemRoot"]))))
                imdisk_exe = driver_path.parent / "imdisk.exe"
                if imdisk_exe.exists():
                    self.imdisk_path = imdisk_exe
                    self.logger.debug(f"Found ImDisk via registry at {imdisk_exe}")
                    return
        except (FileNotFoundError, OSError) as e:
            self.logger.debug(f"Could not find ImDisk via registry: {e}")

        # Try PATH
        imdisk_in_path = shutil.which("imdisk")
        if imdisk_in_path:
            self.imdisk_path = Path(imdisk_in_path)
            self.logger.debug(f"Found ImDisk in PATH at {imdisk_in_path}")
            return

        self.logger.warning("ImDisk not found on system")

    def _is_admin(self) -> bool:
        """Check if running with administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _get_available_drive_letter(self) -> Optional[str]:
        """Find an available drive letter, preferring R:.

        Returns:
            str: Available drive letter (e.g., "R"), or None if none available
        """
        used_drives = set()

        # Get list of used drive letters
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                used_drives.add(chr(ord('A') + i))

        # Try preferred letters first
        for letter in self.PREFERRED_DRIVE_LETTERS:
            if letter not in used_drives:
                return letter

        # Fall back to any available letter
        for i in range(25, -1, -1):  # Z to A
            letter = chr(ord('A') + i)
            if letter not in used_drives and letter not in ['A', 'B', 'C']:  # Skip A, B, C
                return letter

        return None

    def _run_imdisk(self, args: List[str], check: bool = True) -> Tuple[int, str, str]:
        """Run an ImDisk command.

        Args:
            args: Command arguments
            check: Raise exception on non-zero exit code

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            RuntimeError: If ImDisk is not available
            subprocess.CalledProcessError: If check=True and command fails
        """
        if not self.imdisk_path:
            raise RuntimeError("ImDisk is not installed")

        cmd = [str(self.imdisk_path)] + args
        self.logger.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        self.logger.debug(f"Exit code: {result.returncode}")
        if result.stdout:
            self.logger.debug(f"stdout: {result.stdout}")
        if result.stderr:
            self.logger.debug(f"stderr: {result.stderr}")

        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return result.returncode, result.stdout, result.stderr

    def _format_drive(self, drive_letter: str, label: str = "RAMDISK") -> bool:
        """Format a drive as NTFS.

        Args:
            drive_letter: Drive letter (without colon)
            label: Volume label

        Returns:
            bool: True if formatting succeeded
        """
        try:
            # Use format command with NTFS
            cmd = [
                "format",
                f"{drive_letter}:",
                "/FS:NTFS",
                "/Q",  # Quick format
                f"/V:{label}",
                "/Y"  # Confirm
            ]
            self.logger.debug(f"Formatting: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode != 0:
                self.logger.error(f"Format failed: {result.stderr}")
                return False

            return True
        except Exception as e:
            self.logger.error(f"Format error: {e}")
            return False

    def is_available(self) -> bool:
        """Check if ImDisk is available."""
        return self.imdisk_path is not None and self.imdisk_path.exists()

    def get_availability_message(self) -> str:
        """Get a message about ImDisk availability."""
        if self.is_available():
            admin_status = "with admin" if self._is_admin() else "WITHOUT admin (limited)"
            return f"ImDisk available at {self.imdisk_path} ({admin_status})"
        return (
            "ImDisk is not installed. Install from: "
            "https://sourceforge.net/projects/imdisk-toolkit/"
        )

    def ensure_config_path(self, config: RamDiskConfig) -> Path:
        """Generate a Windows path for the RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            Path: Drive path (e.g., R:\\)
        """
        if config.ram_path:
            return config.ram_path

        # Find available drive letter
        letter = self._get_available_drive_letter()
        if not letter:
            raise RuntimeError("No available drive letters")

        return Path(f"{letter}:\\")

    def create(self, config: RamDiskConfig) -> BackendResult:
        """Create a RAM disk using ImDisk.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result with path to the created RAM disk
        """
        # Validate configuration
        error = self.validate_config(config)
        if error:
            return BackendResult(success=False, message=error)

        if not self.is_available():
            return BackendResult(
                success=False,
                message=self.get_availability_message()
            )

        if not self._is_admin():
            return BackendResult(
                success=False,
                message="Administrator privileges required to create RAM disk"
            )

        # Check if already exists
        if self.exists(config):
            ram_path = self.ensure_config_path(config)
            return BackendResult(
                success=True,
                message=f"RAM disk already exists at {ram_path}",
                path=ram_path
            )

        try:
            # Determine drive letter
            ram_path = self.ensure_config_path(config)
            drive_letter = str(ram_path)[0]

            # Check if drive letter is in use
            if ram_path.exists():
                return BackendResult(
                    success=False,
                    message=f"Drive {drive_letter}: is already in use"
                )

            # Calculate size in bytes for ImDisk
            size_bytes = config.size_mb * 1024 * 1024

            # Create RAM disk
            # -a: add/create
            # -s: size
            # -m: mount point
            # -p: format parameters
            # -o: options (rem = removable, fix = fixed)
            self._run_imdisk([
                "-a",
                "-s", str(size_bytes),
                "-m", f"{drive_letter}:",
                "-o", "rem",  # Mark as removable for clean eject
                "-p", "/fs:ntfs /q /y"  # Format as NTFS
            ])

            # Verify creation
            if not ram_path.exists():
                # Sometimes needs a moment
                import time
                time.sleep(1)

            if ram_path.exists():
                # Update config's ram_path
                config.ram_path = ram_path

                self.logger.info(f"Created {config.size_mb}MB RAM disk at {drive_letter}:")
                return BackendResult(
                    success=True,
                    message=f"Created {config.size_mb}MB RAM disk at {drive_letter}:",
                    path=ram_path
                )
            else:
                return BackendResult(
                    success=False,
                    message="RAM disk creation reported success but drive not accessible"
                )

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            self.logger.error(f"ImDisk error: {error_msg}")
            return BackendResult(
                success=False,
                message=f"ImDisk error: {error_msg}",
                error=e
            )
        except Exception as e:
            self.logger.error(f"Unexpected error creating RAM disk: {e}")
            return BackendResult(
                success=False,
                message=f"Error: {e}",
                error=e
            )

    def exists(self, config: RamDiskConfig) -> bool:
        """Check if the RAM disk exists and is accessible.

        Args:
            config: RAM disk configuration

        Returns:
            bool: True if RAM disk exists
        """
        try:
            ram_path = self.ensure_config_path(config)
            return ram_path.exists() and ram_path.is_dir()
        except Exception:
            return False

    def destroy(self, config: RamDiskConfig) -> BackendResult:
        """Destroy a RAM disk.

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

        if not self._is_admin():
            return BackendResult(
                success=False,
                message="Administrator privileges required to destroy RAM disk"
            )

        try:
            ram_path = self.ensure_config_path(config)
            drive_letter = str(ram_path)[0]

            if not self.exists(config):
                return BackendResult(
                    success=True,
                    message=f"RAM disk at {drive_letter}: does not exist"
                )

            # Remove RAM disk
            # -d: remove/delete
            # -m: mount point
            self._run_imdisk([
                "-d",
                "-m", f"{drive_letter}:"
            ])

            # Verify removal
            import time
            time.sleep(0.5)

            if not ram_path.exists():
                self.logger.info(f"Destroyed RAM disk at {drive_letter}:")
                return BackendResult(
                    success=True,
                    message=f"Destroyed RAM disk at {drive_letter}:",
                    path=ram_path
                )
            else:
                return BackendResult(
                    success=False,
                    message=f"RAM disk at {drive_letter}: still exists after destroy"
                )

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            self.logger.error(f"ImDisk error: {error_msg}")
            return BackendResult(
                success=False,
                message=f"ImDisk error: {error_msg}",
                error=e
            )
        except Exception as e:
            self.logger.error(f"Unexpected error destroying RAM disk: {e}")
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
            DiskUsage: Usage statistics, or None if disk doesn't exist
        """
        try:
            ram_path = self.ensure_config_path(config)

            if not self.exists(config):
                return None

            # Use shutil.disk_usage for cross-platform compatibility
            usage = shutil.disk_usage(ram_path)

            return DiskUsage(
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent_used=(usage.used / usage.total * 100) if usage.total > 0 else 0
            )

        except Exception as e:
            self.logger.error(f"Error getting disk usage: {e}")
            return None

    def _get_task_name(self, config: RamDiskConfig) -> str:
        """Get Task Scheduler task name for a config.

        Args:
            config: RAM disk configuration

        Returns:
            str: Task name
        """
        return f"RamDiskManager_{config.name}"

    def persist_config(self, config: RamDiskConfig) -> BackendResult:
        """Set up Task Scheduler task to recreate RAM disk on startup.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the persistence setup
        """
        if not self._is_admin():
            return BackendResult(
                success=False,
                message="Administrator privileges required to create scheduled task"
            )

        try:
            ram_path = self.ensure_config_path(config)
            drive_letter = str(ram_path)[0]
            task_name = self._get_task_name(config)
            size_bytes = config.size_mb * 1024 * 1024

            # Build the ImDisk command for the task
            imdisk_cmd = (
                f'"{self.imdisk_path}" -a -s {size_bytes} '
                f'-m {drive_letter}: -o rem -p "/fs:ntfs /q /y"'
            )

            # Create XML for the scheduled task
            task_xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>RAM Disk Manager - Create {config.name} RAM disk on startup</Description>
    <Author>RamDiskManager</Author>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c {imdisk_cmd}</Arguments>
    </Exec>
  </Actions>
</Task>'''

            # Write XML to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-16') as f:
                f.write(task_xml)
                xml_path = f.name

            try:
                # Create the scheduled task
                result = subprocess.run(
                    ['schtasks', '/create', '/tn', task_name, '/xml', xml_path, '/f'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                if result.returncode != 0:
                    return BackendResult(
                        success=False,
                        message=f"Failed to create scheduled task: {result.stderr}"
                    )

                self.logger.info(f"Created startup task '{task_name}'")
                return BackendResult(
                    success=True,
                    message=f"Created startup task '{task_name}' for {drive_letter}:"
                )

            finally:
                # Clean up temp file
                try:
                    os.unlink(xml_path)
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Error creating scheduled task: {e}")
            return BackendResult(
                success=False,
                message=f"Error: {e}",
                error=e
            )

    def remove_persistence(self, config: RamDiskConfig) -> BackendResult:
        """Remove the startup scheduled task.

        Args:
            config: RAM disk configuration

        Returns:
            BackendResult: Result of the removal
        """
        if not self._is_admin():
            return BackendResult(
                success=False,
                message="Administrator privileges required to remove scheduled task"
            )

        try:
            task_name = self._get_task_name(config)

            result = subprocess.run(
                ['schtasks', '/delete', '/tn', task_name, '/f'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Task might not exist, which is fine
            if result.returncode == 0 or "cannot find" in result.stderr.lower():
                self.logger.info(f"Removed startup task '{task_name}'")
                return BackendResult(
                    success=True,
                    message=f"Removed startup task '{task_name}'"
                )
            else:
                return BackendResult(
                    success=False,
                    message=f"Failed to remove scheduled task: {result.stderr}"
                )

        except Exception as e:
            self.logger.error(f"Error removing scheduled task: {e}")
            return BackendResult(
                success=False,
                message=f"Error: {e}",
                error=e
            )

    def list_ram_disks(self) -> List[dict]:
        """List all ImDisk RAM disks currently mounted.

        Returns:
            List of dicts with drive info
        """
        if not self.is_available():
            return []

        try:
            # ImDisk -l lists all virtual disks
            returncode, stdout, stderr = self._run_imdisk(["-l"], check=False)

            disks = []
            if returncode == 0 and stdout:
                # Parse output - format varies by version
                # Typically: "Device 0 is mounted at R:"
                for line in stdout.strip().split('\n'):
                    line = line.strip()
                    if "mounted at" in line.lower():
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if ':' in part and len(part) == 2:
                                drive = part[0].upper()
                                disks.append({
                                    "drive": drive,
                                    "path": f"{drive}:\\"
                                })

            return disks

        except Exception as e:
            self.logger.error(f"Error listing RAM disks: {e}")
            return []
