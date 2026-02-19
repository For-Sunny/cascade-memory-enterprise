"""Main RamDiskManager class - unified interface for RAM disk operations.

This module provides the primary entry point for managing RAM disks across platforms.
It handles registration, mounting, syncing, and lifecycle management with automatic
cleanup on shutdown.

Example:
    from ram_disk_manager import RamDiskManager, RamDiskConfig

    manager = RamDiskManager()
    manager.register(RamDiskConfig(
        name="cache",
        disk_path=Path("/data/cache"),
        size_mb=256
    ))
    ram_path = manager.mount("cache")
    # ... use RAM disk ...
    manager.unmount("cache", persist=True)
"""

from __future__ import annotations

import atexit
import logging
import platform
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

from .config import RamDiskConfig, ManagerConfig, Platform, SyncStrategy
from .backends import get_backend
from .backends.base import RamDiskBackend, BackendResult, DiskUsage


# Set up module logger
logger = logging.getLogger(__name__)


@dataclass
class ManagedDisk:
    """Internal state for a managed RAM disk.

    Attributes:
        config: The disk configuration
        mounted: Whether the disk is currently mounted
        mount_time: When the disk was mounted (or None)
        last_sync_to_ram: Last sync from disk to RAM
        last_sync_to_disk: Last sync from RAM to disk
        sync_count: Number of syncs performed
        dual_write_controller: DualWriteController instance (if enabled)
    """
    config: RamDiskConfig
    mounted: bool = False
    mount_time: Optional[datetime] = None
    last_sync_to_ram: Optional[datetime] = None
    last_sync_to_disk: Optional[datetime] = None
    sync_count: int = 0
    dual_write_controller: Optional[Any] = None  # DualWriteController when implemented


class RamDiskManager:
    """Unified manager for RAM disk operations across platforms.

    The RamDiskManager provides a high-level interface for creating, managing,
    and synchronizing RAM disks. It handles:

    - Platform detection and backend selection (Windows/Linux/macOS)
    - RAM disk registration and configuration
    - Mount/unmount operations with automatic syncing
    - Dual-write controllers for concurrent RAM+disk writes
    - Automatic cleanup on process exit
    - Recovery from unclean shutdowns

    Attributes:
        config: Global manager configuration
        backend: Platform-specific RAM disk backend
        disks: Dictionary of registered RAM disks by name

    Example:
        # Basic usage
        manager = RamDiskManager()

        # Register a disk
        manager.register(RamDiskConfig(
            name="cache",
            disk_path=Path("/data/cache"),
            size_mb=512,
            sync_strategy=SyncStrategy.INCREMENTAL
        ))

        # Mount and use
        ram_path = manager.mount("cache")
        print(f"Cache mounted at: {ram_path}")

        # Get dual-write controller for safe writes
        writer = manager.get_dual_write("cache")
        writer.write_file(ram_path / "data.json", content)

        # Check status
        status = manager.status()
        print(f"Disk usage: {status['disks']['cache']['usage']['percent_used']}%")

        # Clean unmount with persistence
        manager.unmount("cache", persist=True)
    """

    def __init__(self, config: Optional[ManagerConfig] = None):
        """Initialize the RamDiskManager.

        Args:
            config: Manager configuration. If None, uses defaults with auto
                   platform detection.

        Raises:
            RuntimeError: If no suitable backend is available for the platform.
        """
        self.config = config or ManagerConfig()
        self._disks: Dict[str, ManagedDisk] = {}
        self._backend: Optional[RamDiskBackend] = None
        self._sync_engine: Optional[Any] = None  # SyncEngine when implemented
        self._recovery_manager: Optional[Any] = None  # RecoveryManager when implemented
        self._shutdown_registered = False

        # Configure logging
        self._setup_logging()

        # Detect platform and get backend
        self._detected_platform = self._detect_platform()
        logger.info(f"RamDiskManager initializing for platform: {self._detected_platform}")

        # Get the backend (lazy initialization)
        self._backend = self._get_backend()

        if not self._backend.is_available():
            msg = self._backend.get_availability_message()
            logger.warning(f"Backend not fully available: {msg}")

        # Register shutdown handler
        self._register_shutdown_handler()

        logger.info("RamDiskManager initialized successfully")

    def _setup_logging(self) -> None:
        """Configure logging based on manager config."""
        if self.config.log_file:
            handler = logging.FileHandler(self.config.log_file)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(handler)

    def _detect_platform(self) -> Platform:
        """Detect the current platform.

        Returns:
            Platform enum value for the current system.
        """
        if self.config.platform != Platform.AUTO:
            return self.config.platform

        system = platform.system().lower()
        if system == "windows":
            return Platform.WINDOWS
        elif system == "linux":
            return Platform.LINUX
        elif system == "darwin":
            return Platform.MACOS
        else:
            logger.warning(f"Unknown platform '{system}', defaulting to LINUX")
            return Platform.LINUX

    def _get_backend(self) -> RamDiskBackend:
        """Get the appropriate backend for the detected platform.

        Returns:
            RamDiskBackend instance for the current platform.

        Raises:
            NotImplementedError: If platform is not supported.
        """
        if self._backend is not None:
            return self._backend

        platform_str = self._detected_platform.value
        if platform_str == "auto":
            platform_str = platform.system().lower()

        return get_backend(platform_str)

    def _register_shutdown_handler(self) -> None:
        """Register the shutdown cleanup handler."""
        if not self._shutdown_registered:
            atexit.register(self._on_shutdown)
            self._shutdown_registered = True
            logger.debug("Shutdown handler registered")

    def _get_default_ram_path(self, name: str) -> Path:
        """Generate default RAM path for a disk.

        Args:
            name: Name of the disk

        Returns:
            Default path for the RAM disk mount point.
        """
        if self.config.base_ram_path:
            return self.config.base_ram_path / name

        if self._detected_platform == Platform.WINDOWS:
            return Path("R:\\") / name
        elif self._detected_platform == Platform.MACOS:
            return Path("/Volumes") / f"RAMDISK_{name.upper()}"
        else:
            return Path("/mnt/ramdisk") / name

    def register(self, config: RamDiskConfig) -> bool:
        """Register a RAM disk configuration.

        Registers a disk configuration without mounting it. This allows
        pre-configuring disks that can be mounted later.

        Args:
            config: RAM disk configuration to register.

        Returns:
            True if registration successful, False if name already exists.

        Raises:
            ValueError: If configuration is invalid.

        Example:
            manager.register(RamDiskConfig(
                name="app_data",
                disk_path=Path("/data/app"),
                size_mb=128,
                sync_strategy=SyncStrategy.FULL
            ))
        """
        if config.name in self._disks:
            logger.warning(f"Disk '{config.name}' already registered")
            return False

        # Validate configuration
        validation_error = self._backend.validate_config(config)
        if validation_error:
            raise ValueError(f"Invalid config for '{config.name}': {validation_error}")

        # Ensure ram_path is set
        if not config.ram_path:
            config.ram_path = self._get_default_ram_path(config.name)

        # Ensure disk_path exists
        if not config.disk_path.exists():
            logger.warning(f"Disk path does not exist: {config.disk_path}")

        # Create managed disk entry
        self._disks[config.name] = ManagedDisk(config=config)
        logger.info(f"Registered disk '{config.name}': {config.disk_path} -> {config.ram_path}")

        return True

    def mount(self, name: str) -> Path:
        """Create/mount a RAM disk and sync data from persistent storage.

        This method:
        1. Creates the RAM disk if it doesn't exist
        2. Syncs data from disk_path to ram_path (if auto_sync_on_startup)
        3. Returns the RAM path for use

        Args:
            name: Name of the registered disk to mount.

        Returns:
            Path to the mounted RAM disk.

        Raises:
            KeyError: If disk name is not registered.
            RuntimeError: If mount operation fails.

        Example:
            ram_path = manager.mount("cache")
            # Now read/write files at ram_path for maximum speed
        """
        if name not in self._disks:
            raise KeyError(f"Disk '{name}' is not registered")

        managed = self._disks[name]
        config = managed.config

        # Check if already mounted
        if managed.mounted and self._backend.exists(config):
            logger.info(f"Disk '{name}' already mounted at {config.ram_path}")
            return config.ram_path

        # Create the RAM disk
        logger.info(f"Mounting disk '{name}' ({config.size_mb}MB)...")

        # Check if RAM disk already exists (e.g., from previous session)
        if self._backend.exists(config):
            logger.info(f"RAM disk already exists at {config.ram_path}")
        else:
            result = self._backend.create(config)
            if not result.success:
                raise RuntimeError(f"Failed to create RAM disk '{name}': {result.message}")
            logger.info(f"Created RAM disk at {result.path}")

        # Sync from disk to RAM if configured
        if config.auto_sync_on_startup:
            sync_result = self.sync_to_ram(name, force_full=True)
            if not sync_result.get("success", False):
                logger.warning(f"Initial sync failed: {sync_result.get('error')}")

        # Update managed state
        managed.mounted = True
        managed.mount_time = datetime.now()

        # Initialize dual-write controller if enabled
        if self.config.enable_dual_write:
            try:
                managed.dual_write_controller = self._create_dual_write_controller(config)
            except (ImportError, ValueError, OSError) as e:
                logger.warning(f"Could not create dual-write controller: {e}")

        logger.info(f"Disk '{name}' mounted successfully at {config.ram_path}")
        return config.ram_path

    def unmount(self, name: str, persist: bool = True) -> bool:
        """Unmount a RAM disk, optionally persisting data.

        This method:
        1. Syncs data from RAM to disk (if persist=True)
        2. Destroys the RAM disk
        3. Updates internal state

        Args:
            name: Name of the disk to unmount.
            persist: If True, sync RAM contents to disk before unmounting.

        Returns:
            True if unmount successful, False otherwise.

        Raises:
            KeyError: If disk name is not registered.

        Example:
            # Persist changes before unmount
            manager.unmount("cache", persist=True)

            # Discard RAM contents (not recommended)
            manager.unmount("temp_cache", persist=False)
        """
        if name not in self._disks:
            raise KeyError(f"Disk '{name}' is not registered")

        managed = self._disks[name]
        config = managed.config

        if not managed.mounted:
            logger.warning(f"Disk '{name}' is not mounted")
            return True

        # Persist data if requested
        if persist and config.persist_on_shutdown:
            logger.info(f"Persisting disk '{name}' to {config.disk_path}")
            sync_result = self.sync_to_disk(name)
            if not sync_result.get("success", False):
                logger.error(f"Failed to persist '{name}': {sync_result.get('error')}")
                return False

        # Destroy the RAM disk
        result = self._backend.destroy(config)
        if not result.success:
            logger.error(f"Failed to destroy RAM disk '{name}': {result.message}")
            return False

        # Update state
        managed.mounted = False
        managed.dual_write_controller = None

        logger.info(f"Disk '{name}' unmounted successfully")
        return True

    def sync_to_ram(self, name: str, force_full: bool = False) -> dict:
        """Sync data from persistent storage to RAM disk.

        Args:
            name: Name of the disk to sync.
            force_full: If True, perform full sync regardless of strategy.

        Returns:
            Dict with sync results:
                - success: bool
                - files_synced: int
                - bytes_synced: int
                - duration_ms: float
                - error: str (if failed)

        Raises:
            KeyError: If disk name is not registered.
        """
        if name not in self._disks:
            raise KeyError(f"Disk '{name}' is not registered")

        managed = self._disks[name]
        config = managed.config

        start_time = time.time()
        result = {
            "success": False,
            "files_synced": 0,
            "bytes_synced": 0,
            "duration_ms": 0,
            "error": None,
        }

        try:
            # Ensure RAM path exists
            config.ram_path.mkdir(parents=True, exist_ok=True)

            # Determine strategy
            strategy = SyncStrategy.FULL if force_full else config.sync_strategy

            # Perform sync based on strategy
            if strategy == SyncStrategy.FULL:
                files_synced, bytes_synced = self._full_sync(
                    config.disk_path, config.ram_path, config.patterns
                )
            elif strategy == SyncStrategy.INCREMENTAL:
                files_synced, bytes_synced = self._incremental_sync(
                    config.disk_path, config.ram_path, config.patterns
                )
            elif strategy == SyncStrategy.PATTERN:
                files_synced, bytes_synced = self._pattern_sync(
                    config.disk_path, config.ram_path, config.patterns
                )
            else:
                raise ValueError(f"Unknown sync strategy: {strategy}")

            result["success"] = True
            result["files_synced"] = files_synced
            result["bytes_synced"] = bytes_synced

            # Update managed state
            managed.last_sync_to_ram = datetime.now()
            managed.sync_count += 1

            logger.info(f"Synced {files_synced} files ({bytes_synced:,} bytes) to RAM for '{name}'")

        except (OSError, IOError, ValueError, shutil.Error) as e:
            result["error"] = str(e)
            logger.error(f"Sync to RAM failed for '{name}': {e}")

        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def sync_to_disk(self, name: str) -> dict:
        """Sync data from RAM disk to persistent storage.

        Args:
            name: Name of the disk to sync.

        Returns:
            Dict with sync results (same format as sync_to_ram).

        Raises:
            KeyError: If disk name is not registered.
        """
        if name not in self._disks:
            raise KeyError(f"Disk '{name}' is not registered")

        managed = self._disks[name]
        config = managed.config

        start_time = time.time()
        result = {
            "success": False,
            "files_synced": 0,
            "bytes_synced": 0,
            "duration_ms": 0,
            "error": None,
        }

        try:
            # Ensure disk path exists
            config.disk_path.mkdir(parents=True, exist_ok=True)

            # Always use full sync for persistence (safety)
            files_synced, bytes_synced = self._full_sync(
                config.ram_path, config.disk_path, config.patterns
            )

            result["success"] = True
            result["files_synced"] = files_synced
            result["bytes_synced"] = bytes_synced

            # Update managed state
            managed.last_sync_to_disk = datetime.now()
            managed.sync_count += 1

            logger.info(f"Synced {files_synced} files ({bytes_synced:,} bytes) to disk for '{name}'")

        except (OSError, IOError, ValueError, shutil.Error) as e:
            result["error"] = str(e)
            logger.error(f"Sync to disk failed for '{name}': {e}")

        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def _full_sync(self, source: Path, target: Path, patterns: list) -> tuple[int, int]:
        """Perform a full directory sync.

        Args:
            source: Source directory
            target: Target directory
            patterns: Glob patterns to match

        Returns:
            Tuple of (files_synced, bytes_synced)
        """
        import shutil

        files_synced = 0
        bytes_synced = 0

        if not source.exists():
            logger.warning(f"Source path does not exist: {source}")
            return 0, 0

        # Collect files matching patterns
        matched_files = set()
        for pattern in patterns:
            if "**" in pattern:
                matched_files.update(source.rglob(pattern.replace("**/", "")))
            else:
                matched_files.update(source.glob(pattern))
                matched_files.update(source.rglob(pattern))

        # Copy each file
        for src_file in matched_files:
            if src_file.is_file():
                rel_path = src_file.relative_to(source)
                dst_file = target / rel_path

                # Create parent directories
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(src_file, dst_file)
                files_synced += 1
                bytes_synced += src_file.stat().st_size

        return files_synced, bytes_synced

    def _incremental_sync(self, source: Path, target: Path, patterns: list) -> tuple[int, int]:
        """Perform an incremental sync based on file hashes.

        Args:
            source: Source directory
            target: Target directory
            patterns: Glob patterns to match

        Returns:
            Tuple of (files_synced, bytes_synced)
        """
        import shutil
        from .utils.hashing import hash_directory, compare_hashes

        # Get hashes from both directories
        source_hashes = hash_directory(source, patterns)
        target_hashes = hash_directory(target, patterns)

        # Find differences
        diff = compare_hashes(source_hashes, target_hashes)
        added = diff["added"]
        modified = diff["modified"]
        deleted = diff["removed"]

        files_synced = 0
        bytes_synced = 0

        # Copy new and modified files
        for rel_path in added + modified:
            src_file = source / rel_path
            dst_file = target / rel_path

            if src_file.exists() and src_file.is_file():
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                files_synced += 1
                bytes_synced += src_file.stat().st_size

        # Delete removed files from target
        for rel_path in deleted:
            dst_file = target / rel_path
            if dst_file.exists():
                dst_file.unlink()

        return files_synced, bytes_synced

    def _pattern_sync(self, source: Path, target: Path, patterns: list) -> tuple[int, int]:
        """Sync only files matching specific patterns.

        Args:
            source: Source directory
            target: Target directory
            patterns: Glob patterns to match (used strictly)

        Returns:
            Tuple of (files_synced, bytes_synced)
        """
        # Pattern sync is essentially full sync with strict pattern matching
        return self._full_sync(source, target, patterns)

    def _create_dual_write_controller(self, config: RamDiskConfig) -> Any:
        """Create a dual-write controller for a disk.

        Args:
            config: RAM disk configuration

        Returns:
            DualWriteController instance
        """
        # Import here to avoid circular imports
        try:
            from .sync.dual_write import DualWriteController
            return DualWriteController(config)
        except ImportError:
            logger.debug("DualWriteController not yet implemented")
            return None

    def get_dual_write(self, name: str) -> Optional[Any]:
        """Get the dual-write controller for a disk.

        The dual-write controller allows writing to both RAM and disk
        simultaneously, ensuring data consistency.

        Args:
            name: Name of the disk.

        Returns:
            DualWriteController instance, or None if not available.

        Raises:
            KeyError: If disk name is not registered.

        Example:
            writer = manager.get_dual_write("cache")
            if writer:
                writer.write_file(path, content)
        """
        if name not in self._disks:
            raise KeyError(f"Disk '{name}' is not registered")

        return self._disks[name].dual_write_controller

    def status(self) -> dict:
        """Get status of all managed RAM disks.

        Returns:
            Dict containing:
                - platform: Current platform
                - backend_available: Whether backend is ready
                - disks: Dict of disk statuses by name

        Example:
            status = manager.status()
            for name, disk_status in status["disks"].items():
                print(f"{name}: {'mounted' if disk_status['mounted'] else 'unmounted'}")
        """
        result = {
            "platform": self._detected_platform.value,
            "backend_available": self._backend.is_available() if self._backend else False,
            "backend_message": self._backend.get_availability_message() if self._backend else "No backend",
            "disks": {},
        }

        for name, managed in self._disks.items():
            config = managed.config

            disk_status = {
                "mounted": managed.mounted,
                "disk_path": str(config.disk_path),
                "ram_path": str(config.ram_path),
                "size_mb": config.size_mb,
                "sync_strategy": config.sync_strategy.value,
                "mount_time": managed.mount_time.isoformat() if managed.mount_time else None,
                "last_sync_to_ram": managed.last_sync_to_ram.isoformat() if managed.last_sync_to_ram else None,
                "last_sync_to_disk": managed.last_sync_to_disk.isoformat() if managed.last_sync_to_disk else None,
                "sync_count": managed.sync_count,
                "dual_write_enabled": managed.dual_write_controller is not None,
                "usage": None,
            }

            # Get disk usage if mounted
            if managed.mounted:
                usage = self._backend.get_usage(config)
                if usage:
                    disk_status["usage"] = usage.to_dict()

            result["disks"][name] = disk_status

        return result

    def _on_shutdown(self) -> None:
        """Cleanup handler called on process exit.

        Persists all mounted disks with persist_on_shutdown=True.
        """
        logger.info("RamDiskManager shutdown initiated")

        for name, managed in list(self._disks.items()):
            if managed.mounted:
                try:
                    config = managed.config
                    if config.persist_on_shutdown:
                        logger.info(f"Persisting '{name}' on shutdown...")
                        self.sync_to_disk(name)

                    # Write clean shutdown marker
                    if self.config.recovery_marker_file:
                        marker_path = config.ram_path / self.config.recovery_marker_file
                        try:
                            marker_path.write_text(datetime.now().isoformat())
                        except (OSError, IOError):
                            pass  # Best effort

                except (OSError, IOError, RuntimeError) as e:
                    logger.error(f"Error during shutdown for '{name}': {e}")

        logger.info("RamDiskManager shutdown complete")

    def unregister(self, name: str) -> bool:
        """Unregister a RAM disk.

        The disk must be unmounted first.

        Args:
            name: Name of the disk to unregister.

        Returns:
            True if unregistered, False if disk was still mounted.

        Raises:
            KeyError: If disk name is not registered.
        """
        if name not in self._disks:
            raise KeyError(f"Disk '{name}' is not registered")

        managed = self._disks[name]
        if managed.mounted:
            logger.warning(f"Cannot unregister '{name}' - still mounted")
            return False

        del self._disks[name]
        logger.info(f"Unregistered disk '{name}'")
        return True

    @property
    def disks(self) -> Dict[str, ManagedDisk]:
        """Access to registered disks (read-only view)."""
        return dict(self._disks)

    @property
    def backend(self) -> RamDiskBackend:
        """Access to the platform backend."""
        return self._backend
