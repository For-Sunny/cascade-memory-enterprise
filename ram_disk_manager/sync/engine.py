"""Sync engine for RAM Disk Manager.

Philosophy: DISK IS TRUTH, RAM IS CACHE.

SyncEngine handles bidirectional synchronization:
- disk_to_ram: Populate RAM cache from disk truth
- ram_to_disk: Persist RAM changes back to disk truth

Uses hash-based change detection for incremental syncs.
"""

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, List, Any
import logging

from ram_disk_manager.config import RamDiskConfig, SyncStrategy
from ram_disk_manager.utils.hashing import fast_hash_file, hash_directory, compare_hashes

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """Statistics from a sync operation."""
    
    success: bool = True
    strategy: str = "unknown"
    direction: str = "unknown"  # "disk_to_ram" or "ram_to_disk"
    
    # File counts
    files_copied: int = 0
    files_deleted: int = 0
    files_unchanged: int = 0
    files_failed: int = 0
    
    # Size stats
    bytes_copied: int = 0
    
    # Timing
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: float = 0.0
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "success": self.success,
            "strategy": self.strategy,
            "direction": self.direction,
            "files_copied": self.files_copied,
            "files_deleted": self.files_deleted,
            "files_unchanged": self.files_unchanged,
            "files_failed": self.files_failed,
            "bytes_copied": self.bytes_copied,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
        }


class SyncEngine:
    """Engine for synchronizing between disk (truth) and RAM (cache).
    
    DISK IS TRUTH, RAM IS CACHE.
    
    Attributes:
        config: RamDiskConfig with paths and sync settings
        hash_cache_path: Path to store hash cache for incremental syncs
    """
    
    def __init__(
        self,
        config: RamDiskConfig,
        hash_cache_path: Optional[Path] = None
    ):
        """Initialize sync engine.
        
        Args:
            config: Configuration for this RAM disk
            hash_cache_path: Where to store hash cache. 
                           Defaults to disk_path/.ram_disk_hashes.json
        """
        self.config = config
        self.disk_path = Path(config.disk_path)
        self.ram_path = Path(config.ram_path) if config.ram_path else None
        
        # Hash cache lives on DISK (truth) so it survives RAM loss
        self.hash_cache_path = hash_cache_path or (
            self.disk_path / ".ram_disk_hashes.json"
        )
        
        # In-memory hash cache
        self._hash_cache: Dict[str, str] = {}
        self._load_hash_cache()
    
    def _load_hash_cache(self) -> None:
        """Load hash cache from disk."""
        if self.hash_cache_path.exists():
            try:
                with open(self.hash_cache_path, "r") as f:
                    self._hash_cache = json.load(f)
                logger.debug(f"Loaded hash cache with {len(self._hash_cache)} entries")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load hash cache: {e}")
                self._hash_cache = {}
    
    def _save_hash_cache(self) -> None:
        """Save hash cache to disk."""
        try:
            with open(self.hash_cache_path, "w") as f:
                json.dump(self._hash_cache, f, indent=2)
            logger.debug(f"Saved hash cache with {len(self._hash_cache)} entries")
        except OSError as e:
            logger.warning(f"Failed to save hash cache: {e}")
    
    def disk_to_ram(self, force_full: bool = False) -> SyncStats:
        """Sync from disk (truth) to RAM (cache).
        
        Args:
            force_full: If True, always do full sync. 
                       If False, use config.sync_strategy.
        
        Returns:
            SyncStats with operation details
        """
        stats = SyncStats(
            direction="disk_to_ram",
            started_at=time.time()
        )
        
        if not self.ram_path:
            stats.success = False
            stats.errors.append("RAM path not configured")
            return self._finalize_stats(stats)
        
        if not self.disk_path.exists():
            stats.success = False
            stats.errors.append(f"Disk path does not exist: {self.disk_path}")
            return self._finalize_stats(stats)
        
        # Determine strategy
        if force_full or self.config.sync_strategy == SyncStrategy.FULL:
            stats.strategy = "full"
            stats = self._full_sync_to_ram(stats)
        else:
            stats.strategy = "incremental"
            stats = self._incremental_sync_to_ram(stats)
        
        # Verify integrity if configured
        if self.config.verify_integrity and stats.success:
            verified = self._verify_sync(self.disk_path, self.ram_path)
            if not verified:
                stats.errors.append("Integrity verification failed")
                # Don't mark as failure - files are there, just warn
        
        # Update hash cache after successful sync
        if stats.success:
            self._hash_cache = hash_directory(
                self.disk_path, 
                self.config.patterns
            )
            self._save_hash_cache()
        
        return self._finalize_stats(stats)
    
    def ram_to_disk(self) -> SyncStats:
        """Sync from RAM (cache) back to disk (truth).
        
        Use this to persist changes before unmounting RAM disk.
        
        Returns:
            SyncStats with operation details
        """
        stats = SyncStats(
            direction="ram_to_disk",
            strategy="full",
            started_at=time.time()
        )
        
        if not self.ram_path:
            stats.success = False
            stats.errors.append("RAM path not configured")
            return self._finalize_stats(stats)
        
        if not self.ram_path.exists():
            stats.success = False
            stats.errors.append(f"RAM path does not exist: {self.ram_path}")
            return self._finalize_stats(stats)
        
        # Ensure disk path exists
        self.disk_path.mkdir(parents=True, exist_ok=True)
        
        # Get current state of both
        ram_hashes = hash_directory(self.ram_path, self.config.patterns)
        disk_hashes = hash_directory(self.disk_path, self.config.patterns)
        
        # Compare to find changes
        diff = compare_hashes(ram_hashes, disk_hashes)
        
        # Copy new and modified files from RAM to disk
        for rel_path in diff["added"] + diff["modified"]:
            src = self.ram_path / rel_path
            dst = self.disk_path / rel_path
            
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                stats.files_copied += 1
                stats.bytes_copied += src.stat().st_size
            except OSError as e:
                stats.files_failed += 1
                stats.errors.append(f"Failed to copy {rel_path}: {e}")
        
        # Delete files from disk that were removed from RAM
        for rel_path in diff["removed"]:
            dst = self.disk_path / rel_path
            try:
                dst.unlink()
                stats.files_deleted += 1
            except OSError as e:
                stats.files_failed += 1
                stats.errors.append(f"Failed to delete {rel_path}: {e}")
        
        stats.files_unchanged = len(diff["unchanged"])
        
        # Update hash cache
        if stats.files_failed == 0:
            self._hash_cache = hash_directory(
                self.disk_path, 
                self.config.patterns
            )
            self._save_hash_cache()
        else:
            stats.success = False
        
        return self._finalize_stats(stats)
    
    def _full_sync_to_ram(self, stats: SyncStats) -> SyncStats:
        """Delete RAM contents and copy all from disk.
        
        Args:
            stats: Stats object to update
            
        Returns:
            Updated stats
        """
        # Clear RAM directory
        if self.ram_path.exists():
            for item in self.ram_path.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    stats.files_deleted += 1
                except OSError as e:
                    stats.errors.append(f"Failed to delete {item}: {e}")
        else:
            self.ram_path.mkdir(parents=True, exist_ok=True)
        
        # Copy all matching files from disk
        files_to_copy = set()
        for pattern in self.config.patterns:
            if "**" in pattern:
                matched = self.disk_path.glob(pattern)
            else:
                matched = self.disk_path.rglob(pattern)
            
            for path in matched:
                if path.is_file():
                    files_to_copy.add(path)
        
        for src in files_to_copy:
            try:
                rel_path = src.relative_to(self.disk_path)
                dst = self.ram_path / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                stats.files_copied += 1
                stats.bytes_copied += src.stat().st_size
            except OSError as e:
                stats.files_failed += 1
                stats.errors.append(f"Failed to copy {src}: {e}")
        
        if stats.files_failed > 0:
            stats.success = False
        
        return stats
    
    def _incremental_sync_to_ram(self, stats: SyncStats) -> SyncStats:
        """Only copy changed files based on hash comparison.
        
        Args:
            stats: Stats object to update
            
        Returns:
            Updated stats
        """
        # Hash current disk state
        current_disk_hashes = hash_directory(
            self.disk_path, 
            self.config.patterns
        )
        
        # Hash current RAM state (if exists)
        if self.ram_path.exists():
            current_ram_hashes = hash_directory(
                self.ram_path, 
                self.config.patterns
            )
        else:
            self.ram_path.mkdir(parents=True, exist_ok=True)
            current_ram_hashes = {}
        
        # Compare disk to RAM
        diff = compare_hashes(current_disk_hashes, current_ram_hashes)
        
        # Copy new and modified files
        for rel_path in diff["added"] + diff["modified"]:
            src = self.disk_path / rel_path
            dst = self.ram_path / rel_path
            
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                stats.files_copied += 1
                stats.bytes_copied += src.stat().st_size
            except OSError as e:
                stats.files_failed += 1
                stats.errors.append(f"Failed to copy {rel_path}: {e}")
        
        # Delete files from RAM that no longer exist on disk
        for rel_path in diff["removed"]:
            dst = self.ram_path / rel_path
            try:
                dst.unlink()
                stats.files_deleted += 1
            except OSError as e:
                stats.files_failed += 1
                stats.errors.append(f"Failed to delete {rel_path}: {e}")
        
        stats.files_unchanged = len(diff["unchanged"])
        
        if stats.files_failed > 0:
            stats.success = False
        
        return stats
    
    def _verify_sync(self, source: Path, target: Path) -> bool:
        """Verify that target matches source.
        
        Args:
            source: Source directory
            target: Target directory
            
        Returns:
            True if all files match, False otherwise
        """
        source_hashes = hash_directory(source, self.config.patterns)
        target_hashes = hash_directory(target, self.config.patterns)
        
        diff = compare_hashes(source_hashes, target_hashes)
        
        if diff["added"] or diff["removed"] or diff["modified"]:
            logger.warning(
                f"Verification failed: "
                f"{len(diff['added'])} added, "
                f"{len(diff['removed'])} removed, "
                f"{len(diff['modified'])} modified"
            )
            return False
        
        return True
    
    def _finalize_stats(self, stats: SyncStats) -> SyncStats:
        """Finalize stats with timing info.
        
        Args:
            stats: Stats object to finalize
            
        Returns:
            Finalized stats
        """
        stats.completed_at = time.time()
        stats.duration_ms = (stats.completed_at - stats.started_at) * 1000
        
        logger.info(
            f"Sync {stats.direction} ({stats.strategy}): "
            f"{stats.files_copied} copied, "
            f"{stats.files_deleted} deleted, "
            f"{stats.files_unchanged} unchanged, "
            f"{stats.files_failed} failed "
            f"in {stats.duration_ms:.1f}ms"
        )
        
        return stats
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status between disk and RAM.
        
        Returns:
            Dict with sync status info
        """
        result = {
            "disk_path": str(self.disk_path),
            "ram_path": str(self.ram_path) if self.ram_path else None,
            "disk_exists": self.disk_path.exists(),
            "ram_exists": self.ram_path.exists() if self.ram_path else False,
            "in_sync": False,
            "differences": None,
        }
        
        if not result["disk_exists"] or not result["ram_exists"]:
            return result
        
        disk_hashes = hash_directory(self.disk_path, self.config.patterns)
        ram_hashes = hash_directory(self.ram_path, self.config.patterns)
        
        diff = compare_hashes(disk_hashes, ram_hashes)
        
        result["in_sync"] = not (
            diff["added"] or diff["removed"] or diff["modified"]
        )
        result["differences"] = {
            "disk_only": diff["added"],
            "ram_only": diff["removed"],
            "modified": diff["modified"],
            "identical": len(diff["unchanged"]),
        }
        
        return result
