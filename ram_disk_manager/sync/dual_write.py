"""Dual-write controller for RAM Disk Manager.

Philosophy: DISK IS TRUTH, RAM IS CACHE.

Write order: Disk first (must succeed), RAM second (best effort).
Read order: RAM first (fast), disk fallback (guaranteed).

Thread-safe implementation with failure callbacks.
"""

import shutil
import threading
import logging
from pathlib import Path
from typing import Optional, Callable, Any, Union
from dataclasses import dataclass

from ram_disk_manager.config import RamDiskConfig

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Result of a dual-write operation."""
    
    success: bool
    disk_written: bool
    ram_written: bool
    bytes_written: int
    error: Optional[str] = None
    
    @property
    def partial(self) -> bool:
        """True if disk succeeded but RAM failed."""
        return self.disk_written and not self.ram_written


class DualWriteController:
    """Thread-safe controller for writing to both disk and RAM.
    
    DISK IS TRUTH, RAM IS CACHE.
    
    Write operations always write to disk first. If disk write fails,
    the operation fails entirely. If RAM write fails, the operation
    succeeds (data is safe on disk) but triggers a callback.
    
    Read operations try RAM first for speed, falling back to disk
    if RAM read fails.
    
    Attributes:
        config: RamDiskConfig with paths
        on_ram_failure: Callback when RAM write fails (receives relative_path, error)
        on_sync_needed: Callback when RAM needs resync (receives relative_path)
    """
    
    def __init__(
        self,
        config: RamDiskConfig,
        on_ram_failure: Optional[Callable[[str, Exception], None]] = None,
        on_sync_needed: Optional[Callable[[str], None]] = None,
    ):
        """Initialize dual-write controller.
        
        Args:
            config: Configuration for this RAM disk
            on_ram_failure: Called when RAM write fails
            on_sync_needed: Called when RAM needs resync with disk
        """
        self.config = config
        self.disk_path = Path(config.disk_path)
        self.ram_path = Path(config.ram_path) if config.ram_path else None
        
        self.on_ram_failure = on_ram_failure
        self.on_sync_needed = on_sync_needed
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Track paths that need resync (RAM write failed)
        self._needs_resync: set = set()
    
    def write(
        self,
        relative_path: str,
        content: Union[str, bytes],
        encoding: str = "utf-8"
    ) -> WriteResult:
        """Write content to both disk and RAM.
        
        DISK FIRST (must succeed), RAM SECOND (best effort).
        
        Args:
            relative_path: Path relative to disk_path/ram_path
            content: Content to write (str or bytes)
            encoding: Encoding for string content
            
        Returns:
            WriteResult with operation details
        """
        with self._lock:
            result = WriteResult(
                success=False,
                disk_written=False,
                ram_written=False,
                bytes_written=0,
            )
            
            # Normalize path
            relative_path = relative_path.replace("\\", "/")
            
            # Convert content to bytes
            if isinstance(content, str):
                content_bytes = content.encode(encoding)
            else:
                content_bytes = content
            
            result.bytes_written = len(content_bytes)
            
            # STEP 1: Write to DISK (truth) - MUST succeed
            disk_file = self.disk_path / relative_path
            try:
                disk_file.parent.mkdir(parents=True, exist_ok=True)
                disk_file.write_bytes(content_bytes)
                result.disk_written = True
                logger.debug(f"Disk write success: {relative_path}")
            except OSError as e:
                result.error = f"Disk write failed: {e}"
                logger.error(result.error)
                return result  # Total failure - disk write failed
            
            # STEP 2: Write to RAM (cache) - best effort
            if self.ram_path:
                ram_file = self.ram_path / relative_path
                try:
                    ram_file.parent.mkdir(parents=True, exist_ok=True)
                    ram_file.write_bytes(content_bytes)
                    result.ram_written = True
                    logger.debug(f"RAM write success: {relative_path}")
                    
                    # Remove from needs_resync if it was there
                    self._needs_resync.discard(relative_path)
                    
                except OSError as e:
                    # RAM write failed - data is safe on disk but RAM is stale
                    logger.warning(f"RAM write failed (disk is safe): {relative_path}: {e}")
                    self._needs_resync.add(relative_path)
                    
                    if self.on_ram_failure:
                        try:
                            self.on_ram_failure(relative_path, e)
                        except Exception as cb_error:
                            logger.error(f"on_ram_failure callback error: {cb_error}")
            
            # Success if disk write succeeded (RAM failure is acceptable)
            result.success = result.disk_written
            return result
    
    def write_file(
        self,
        relative_path: str,
        source_path: Union[str, Path]
    ) -> WriteResult:
        """Copy a file to both disk and RAM.
        
        DISK FIRST (must succeed), RAM SECOND (best effort).
        
        Args:
            relative_path: Destination path relative to disk_path/ram_path
            source_path: Path to source file
            
        Returns:
            WriteResult with operation details
        """
        with self._lock:
            result = WriteResult(
                success=False,
                disk_written=False,
                ram_written=False,
                bytes_written=0,
            )
            
            source_path = Path(source_path)
            relative_path = relative_path.replace("\\", "/")
            
            if not source_path.exists():
                result.error = f"Source file not found: {source_path}"
                return result
            
            result.bytes_written = source_path.stat().st_size
            
            # STEP 1: Copy to DISK (truth) - MUST succeed
            disk_file = self.disk_path / relative_path
            try:
                disk_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, disk_file)
                result.disk_written = True
                logger.debug(f"Disk copy success: {relative_path}")
            except OSError as e:
                result.error = f"Disk copy failed: {e}"
                logger.error(result.error)
                return result
            
            # STEP 2: Copy to RAM (cache) - best effort
            if self.ram_path:
                ram_file = self.ram_path / relative_path
                try:
                    ram_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, ram_file)
                    result.ram_written = True
                    logger.debug(f"RAM copy success: {relative_path}")
                    self._needs_resync.discard(relative_path)
                except OSError as e:
                    logger.warning(f"RAM copy failed (disk is safe): {relative_path}: {e}")
                    self._needs_resync.add(relative_path)
                    
                    if self.on_ram_failure:
                        try:
                            self.on_ram_failure(relative_path, e)
                        except Exception as cb_error:
                            logger.error(f"on_ram_failure callback error: {cb_error}")
            
            result.success = result.disk_written
            return result
    
    def read(
        self,
        relative_path: str,
        encoding: Optional[str] = "utf-8"
    ) -> Optional[Union[str, bytes]]:
        """Read content from RAM first, disk fallback.
        
        RAM FIRST (fast), DISK FALLBACK (guaranteed).
        
        Args:
            relative_path: Path relative to disk_path/ram_path
            encoding: If provided, decode bytes to string. None for raw bytes.
            
        Returns:
            File content (str if encoding provided, bytes otherwise)
            None if file doesn't exist in either location
        """
        with self._lock:
            relative_path = relative_path.replace("\\", "/")
            
            # STEP 1: Try RAM first (fast)
            if self.ram_path and relative_path not in self._needs_resync:
                ram_file = self.ram_path / relative_path
                if ram_file.exists():
                    try:
                        content = ram_file.read_bytes()
                        logger.debug(f"RAM read success: {relative_path}")
                        if encoding:
                            return content.decode(encoding)
                        return content
                    except OSError as e:
                        logger.warning(f"RAM read failed, falling back to disk: {e}")
            
            # STEP 2: Fallback to DISK (guaranteed)
            disk_file = self.disk_path / relative_path
            if disk_file.exists():
                try:
                    content = disk_file.read_bytes()
                    logger.debug(f"Disk read success (fallback): {relative_path}")
                    
                    # Notify that RAM needs resync
                    if self.ram_path and self.on_sync_needed:
                        try:
                            self.on_sync_needed(relative_path)
                        except Exception as cb_error:
                            logger.error(f"on_sync_needed callback error: {cb_error}")
                    
                    if encoding:
                        return content.decode(encoding)
                    return content
                except OSError as e:
                    logger.error(f"Disk read failed: {relative_path}: {e}")
            
            return None
    
    def read_bytes(self, relative_path: str) -> Optional[bytes]:
        """Read raw bytes from RAM first, disk fallback.
        
        Args:
            relative_path: Path relative to disk_path/ram_path
            
        Returns:
            File content as bytes, None if not found
        """
        return self.read(relative_path, encoding=None)
    
    def read_text(
        self,
        relative_path: str,
        encoding: str = "utf-8"
    ) -> Optional[str]:
        """Read text from RAM first, disk fallback.
        
        Args:
            relative_path: Path relative to disk_path/ram_path
            encoding: Text encoding
            
        Returns:
            File content as string, None if not found
        """
        return self.read(relative_path, encoding=encoding)
    
    def delete(self, relative_path: str) -> WriteResult:
        """Delete file from both disk and RAM.
        
        DISK FIRST (must succeed), RAM SECOND (best effort).
        
        Args:
            relative_path: Path relative to disk_path/ram_path
            
        Returns:
            WriteResult with operation details
        """
        with self._lock:
            result = WriteResult(
                success=False,
                disk_written=False,
                ram_written=False,
                bytes_written=0,
            )
            
            relative_path = relative_path.replace("\\", "/")
            
            # STEP 1: Delete from DISK (truth) - MUST succeed
            disk_file = self.disk_path / relative_path
            if disk_file.exists():
                try:
                    disk_file.unlink()
                    result.disk_written = True
                    logger.debug(f"Disk delete success: {relative_path}")
                except OSError as e:
                    result.error = f"Disk delete failed: {e}"
                    logger.error(result.error)
                    return result
            else:
                # File doesn't exist on disk - that's fine
                result.disk_written = True
            
            # STEP 2: Delete from RAM (cache) - best effort
            if self.ram_path:
                ram_file = self.ram_path / relative_path
                if ram_file.exists():
                    try:
                        ram_file.unlink()
                        result.ram_written = True
                        logger.debug(f"RAM delete success: {relative_path}")
                    except OSError as e:
                        logger.warning(f"RAM delete failed: {relative_path}: {e}")
                else:
                    result.ram_written = True
            
            # Remove from needs_resync
            self._needs_resync.discard(relative_path)
            
            result.success = result.disk_written
            return result
    
    def exists(self, relative_path: str) -> bool:
        """Check if file exists (checks disk as source of truth).
        
        Args:
            relative_path: Path relative to disk_path
            
        Returns:
            True if file exists on disk
        """
        relative_path = relative_path.replace("\\", "/")
        return (self.disk_path / relative_path).exists()
    
    def get_needs_resync(self) -> list:
        """Get list of paths that need resync (RAM write failed).
        
        Returns:
            List of relative paths that need resync
        """
        with self._lock:
            return list(self._needs_resync)
    
    def clear_needs_resync(self) -> None:
        """Clear the needs_resync set (call after successful full sync)."""
        with self._lock:
            self._needs_resync.clear()
    
    def resync_path(self, relative_path: str) -> WriteResult:
        """Resync a specific path from disk to RAM.
        
        Args:
            relative_path: Path to resync
            
        Returns:
            WriteResult with operation details
        """
        with self._lock:
            result = WriteResult(
                success=False,
                disk_written=True,  # Disk is source, not written to
                ram_written=False,
                bytes_written=0,
            )
            
            relative_path = relative_path.replace("\\", "/")
            disk_file = self.disk_path / relative_path
            
            if not disk_file.exists():
                # File doesn't exist on disk - delete from RAM if present
                if self.ram_path:
                    ram_file = self.ram_path / relative_path
                    if ram_file.exists():
                        try:
                            ram_file.unlink()
                            result.ram_written = True
                        except OSError as e:
                            result.error = f"RAM delete failed: {e}"
                            return result
                self._needs_resync.discard(relative_path)
                result.success = True
                return result
            
            # Copy from disk to RAM
            if self.ram_path:
                ram_file = self.ram_path / relative_path
                try:
                    ram_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(disk_file, ram_file)
                    result.ram_written = True
                    result.bytes_written = disk_file.stat().st_size
                    self._needs_resync.discard(relative_path)
                    logger.debug(f"Resync success: {relative_path}")
                except OSError as e:
                    result.error = f"RAM copy failed: {e}"
                    logger.error(result.error)
                    return result
            
            result.success = True
            return result
