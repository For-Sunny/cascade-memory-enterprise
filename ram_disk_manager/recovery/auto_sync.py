"""Automatic recovery orchestration for RAM disk content.

RecoveryManager coordinates crash detection, integrity verification,
and automatic synchronization to restore RAM disk content after
unclean shutdowns.
"""

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ram_disk_manager.config import RamDiskConfig, ManagerConfig, SyncStrategy
from ram_disk_manager.recovery.detector import (
    was_clean_shutdown,
    mark_clean_shutdown,
    clear_shutdown_marker,
    get_shutdown_info,
)
from ram_disk_manager.recovery.integrity import verify_integrity, IntegrityResult


@dataclass
class RecoveryResult:
    """Result of recovery operation.

    Attributes:
        recovery_needed: Whether recovery was performed
        clean_shutdown: Whether the previous shutdown was clean
        integrity_before: Integrity status before recovery (if checked)
        integrity_after: Integrity status after recovery (if performed)
        files_synced: Number of files synced during recovery
        files_copied: List of files that were copied
        files_failed: List of files that failed to copy
        duration_ms: Recovery duration in milliseconds
        error: Error message if recovery failed
    """
    recovery_needed: bool = False
    clean_shutdown: bool = True
    integrity_before: Optional[IntegrityResult] = None
    integrity_after: Optional[IntegrityResult] = None
    files_synced: int = 0
    files_copied: List[str] = field(default_factory=list)
    files_failed: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if recovery completed successfully."""
        return self.error is None and len(self.files_failed) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "recovery_needed": self.recovery_needed,
            "clean_shutdown": self.clean_shutdown,
            "success": self.success,
            "files_synced": self.files_synced,
            "files_copied": self.files_copied,
            "files_failed": self.files_failed,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "integrity_before": self.integrity_before.to_dict() if self.integrity_before else None,
            "integrity_after": self.integrity_after.to_dict() if self.integrity_after else None,
        }


class RecoveryManager:
    """Manages crash detection and recovery for RAM disk content.

    Usage:
        manager = RecoveryManager()
        result = manager.recover(ram_config)
        if result.recovery_needed:
            print(f"Recovered {result.files_synced} files")
    """

    def __init__(self, manager_config: Optional[ManagerConfig] = None):
        """Initialize recovery manager.

        Args:
            manager_config: Optional manager configuration
        """
        self.manager_config = manager_config or ManagerConfig()

    def recover(
        self,
        config: RamDiskConfig,
        force_full_sync: bool = False,
        verify_after: bool = True
    ) -> RecoveryResult:
        """Perform recovery if needed.

        Checks for clean shutdown marker, verifies integrity,
        and performs full sync if crash detected or integrity fails.

        Args:
            config: RAM disk configuration
            force_full_sync: Force sync regardless of shutdown status
            verify_after: Verify integrity after recovery

        Returns:
            RecoveryResult with recovery statistics
        """
        import time
        start_time = time.perf_counter()

        result = RecoveryResult()

        # Check clean shutdown status
        result.clean_shutdown = was_clean_shutdown(config, self.manager_config)

        # Determine if recovery is needed
        if force_full_sync:
            result.recovery_needed = True
        elif not result.clean_shutdown:
            # Crash detected - recovery needed
            result.recovery_needed = True
        else:
            # Clean shutdown - check integrity anyway
            if config.verify_integrity and config.ram_path and config.ram_path.exists():
                result.integrity_before = verify_integrity(config)
                if result.integrity_before.needs_recovery:
                    result.recovery_needed = True

        # Clear shutdown marker for this session
        clear_shutdown_marker(config, self.manager_config)

        # Perform recovery if needed
        if result.recovery_needed:
            try:
                synced, copied, failed = self._sync_disk_to_ram(config)
                result.files_synced = synced
                result.files_copied = copied
                result.files_failed = failed
            except Exception as e:
                result.error = str(e)

        # Verify after recovery
        if verify_after and result.recovery_needed and result.error is None:
            if config.ram_path and config.ram_path.exists():
                result.integrity_after = verify_integrity(config)

        # Calculate duration
        result.duration_ms = (time.perf_counter() - start_time) * 1000

        return result

    def _sync_disk_to_ram(self, config: RamDiskConfig) -> tuple:
        """Sync content from disk to RAM.

        Args:
            config: RAM disk configuration

        Returns:
            Tuple of (files_synced, files_copied, files_failed)
        """
        if config.ram_path is None:
            raise ValueError("RAM path not configured")

        if not config.disk_path.exists():
            raise ValueError(f"Disk path does not exist: {config.disk_path}")

        # Ensure RAM directory exists
        config.ram_path.mkdir(parents=True, exist_ok=True)

        files_copied: List[str] = []
        files_failed: List[str] = []

        # Full sync: copy all matching files from disk to RAM
        for pattern in config.patterns:
            for disk_file in config.disk_path.glob(pattern):
                if not disk_file.is_file():
                    continue

                rel_path = disk_file.relative_to(config.disk_path)
                ram_file = config.ram_path / rel_path

                try:
                    # Create parent directories
                    ram_file.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    shutil.copy2(disk_file, ram_file)
                    files_copied.append(str(rel_path))

                except (OSError, IOError) as e:
                    files_failed.append(str(rel_path))

        return len(files_copied), files_copied, files_failed

    def prepare_shutdown(self, config: RamDiskConfig) -> bool:
        """Prepare for clean shutdown.

        Syncs RAM content to disk and writes shutdown marker.
        Call this before unmounting the RAM disk.

        Args:
            config: RAM disk configuration

        Returns:
            True if shutdown preparation succeeded
        """
        success = True

        # Sync RAM to disk if configured
        if config.persist_on_shutdown and config.ram_path and config.ram_path.exists():
            try:
                self._sync_ram_to_disk(config)
            except Exception:
                success = False

        # Write clean shutdown marker
        if success:
            success = mark_clean_shutdown(config, self.manager_config)

        return success

    def _sync_ram_to_disk(self, config: RamDiskConfig) -> tuple:
        """Sync content from RAM to disk.

        Args:
            config: RAM disk configuration

        Returns:
            Tuple of (files_synced, files_copied, files_failed)
        """
        if config.ram_path is None:
            raise ValueError("RAM path not configured")

        files_copied: List[str] = []
        files_failed: List[str] = []

        # Copy all matching files from RAM to disk
        for pattern in config.patterns:
            for ram_file in config.ram_path.glob(pattern):
                if not ram_file.is_file():
                    continue

                rel_path = ram_file.relative_to(config.ram_path)
                disk_file = config.disk_path / rel_path

                try:
                    # Create parent directories
                    disk_file.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    shutil.copy2(ram_file, disk_file)
                    files_copied.append(str(rel_path))

                except (OSError, IOError) as e:
                    files_failed.append(str(rel_path))

        return len(files_copied), files_copied, files_failed

    def check_status(self, config: RamDiskConfig) -> dict:
        """Check current recovery status without performing recovery.

        Args:
            config: RAM disk configuration

        Returns:
            Dict with status information
        """
        clean = was_clean_shutdown(config, self.manager_config)
        shutdown_info = get_shutdown_info(config, self.manager_config)

        status = {
            "clean_shutdown": clean,
            "recovery_needed": not clean,
            "shutdown_info": shutdown_info,
            "disk_path_exists": config.disk_path.exists(),
            "ram_path_exists": config.ram_path.exists() if config.ram_path else False,
        }

        # Add integrity info if RAM exists
        if status["ram_path_exists"] and config.ram_path:
            try:
                integrity = verify_integrity(config)
                status["integrity"] = integrity.to_dict()
                if integrity.needs_recovery:
                    status["recovery_needed"] = True
            except Exception as e:
                status["integrity_error"] = str(e)

        return status
