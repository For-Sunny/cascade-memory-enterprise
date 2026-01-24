"""Hash-based integrity verification for RAM disk content.

Compares file hashes between disk (source of truth) and RAM
to detect corruption or missing files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ram_disk_manager.config import RamDiskConfig
from ram_disk_manager.utils.hashing import fast_hash_file, hash_directory


@dataclass
class IntegrityResult:
    """Result of integrity verification.

    Attributes:
        verified_count: Number of files that passed verification
        mismatched_files: Files with different hashes (disk vs RAM)
        missing_in_ram: Files on disk but not in RAM
        missing_on_disk: Files in RAM but not on disk (unexpected)
        errors: Files that couldn't be verified due to errors
        disk_hashes: Hash map of disk files
        ram_hashes: Hash map of RAM files
    """
    verified_count: int = 0
    mismatched_files: List[str] = field(default_factory=list)
    missing_in_ram: List[str] = field(default_factory=list)
    missing_on_disk: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    disk_hashes: Dict[str, str] = field(default_factory=dict)
    ram_hashes: Dict[str, str] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if integrity verification passed completely."""
        return (
            len(self.mismatched_files) == 0 and
            len(self.missing_in_ram) == 0 and
            len(self.errors) == 0
        )

    @property
    def total_files(self) -> int:
        """Total number of files checked."""
        return len(self.disk_hashes)

    @property
    def needs_recovery(self) -> bool:
        """Check if recovery sync is needed."""
        return not self.is_valid

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "verified_count": self.verified_count,
            "total_files": self.total_files,
            "is_valid": self.is_valid,
            "needs_recovery": self.needs_recovery,
            "mismatched_files": self.mismatched_files,
            "missing_in_ram": self.missing_in_ram,
            "missing_on_disk": self.missing_on_disk,
            "errors": self.errors,
        }


def verify_integrity(
    config: RamDiskConfig,
    patterns: Optional[List[str]] = None
) -> IntegrityResult:
    """Verify integrity between disk and RAM content.

    Compares file hashes to detect:
    - Mismatched content (hash differs)
    - Missing files in RAM (not synced or lost)
    - Extra files in RAM (not on disk - unusual)
    - Read errors

    Args:
        config: RAM disk configuration with disk_path and ram_path
        patterns: Optional glob patterns to filter files (uses config.patterns if None)

    Returns:
        IntegrityResult with verification statistics
    """
    result = IntegrityResult()

    # Validate paths
    if not config.disk_path.exists():
        result.errors.append(f"Disk path does not exist: {config.disk_path}")
        return result

    if config.ram_path is None or not config.ram_path.exists():
        result.errors.append(f"RAM path does not exist: {config.ram_path}")
        return result

    # Use provided patterns or config patterns
    check_patterns = patterns if patterns is not None else config.patterns

    # Hash both directories
    try:
        result.disk_hashes = hash_directory(config.disk_path, check_patterns)
    except Exception as e:
        result.errors.append(f"Failed to hash disk directory: {e}")
        return result

    try:
        result.ram_hashes = hash_directory(config.ram_path, check_patterns)
    except Exception as e:
        result.errors.append(f"Failed to hash RAM directory: {e}")
        return result

    # Compare hashes
    disk_files = set(result.disk_hashes.keys())
    ram_files = set(result.ram_hashes.keys())

    # Files missing in RAM
    result.missing_in_ram = list(disk_files - ram_files)

    # Files missing on disk (extra in RAM - unusual but track it)
    result.missing_on_disk = list(ram_files - disk_files)

    # Check matching files for hash differences
    common_files = disk_files & ram_files
    for rel_path in common_files:
        disk_hash = result.disk_hashes[rel_path]
        ram_hash = result.ram_hashes[rel_path]

        if disk_hash == ram_hash:
            result.verified_count += 1
        else:
            result.mismatched_files.append(rel_path)

    return result


def verify_single_file(
    config: RamDiskConfig,
    relative_path: str
) -> dict:
    """Verify integrity of a single file.

    Args:
        config: RAM disk configuration
        relative_path: Path relative to disk_path/ram_path

    Returns:
        Dict with verification result
    """
    disk_file = config.disk_path / relative_path
    ram_file = config.ram_path / relative_path if config.ram_path else None

    result = {
        "path": relative_path,
        "exists_on_disk": disk_file.exists(),
        "exists_in_ram": ram_file.exists() if ram_file else False,
        "disk_hash": None,
        "ram_hash": None,
        "match": False,
        "error": None,
    }

    try:
        if result["exists_on_disk"]:
            result["disk_hash"] = fast_hash_file(disk_file)

        if result["exists_in_ram"]:
            result["ram_hash"] = fast_hash_file(ram_file)

        result["match"] = (
            result["disk_hash"] is not None and
            result["ram_hash"] is not None and
            result["disk_hash"] == result["ram_hash"]
        )

    except Exception as e:
        result["error"] = str(e)

    return result
