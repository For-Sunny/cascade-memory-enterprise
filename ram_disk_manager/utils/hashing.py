"""Fast file and directory hashing utilities.

Uses xxhash for speed when available, falls back to md5.
Designed for sync operations where speed matters more than cryptographic security.
"""

import hashlib
from pathlib import Path
from typing import Dict, Optional

try:
    import xxhash
    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False

# Buffer size for file reading (64KB is good for most filesystems)
BUFFER_SIZE = 65536


def fast_hash_file(file_path: Path, algorithm: str = "auto") -> str:
    """Compute a fast hash of a file.

    Args:
        file_path: Path to the file to hash
        algorithm: Hash algorithm ("auto", "xxhash", "md5", "sha256")
                   "auto" uses xxhash if available, else md5

    Returns:
        Hex digest of the file hash

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    # Select hasher
    if algorithm == "auto":
        if XXHASH_AVAILABLE:
            hasher = xxhash.xxh64()
        else:
            hasher = hashlib.md5()
    elif algorithm == "xxhash":
        if not XXHASH_AVAILABLE:
            raise ImportError("xxhash not installed. Install with: pip install xxhash")
        hasher = xxhash.xxh64()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # Read and hash in chunks
    with open(file_path, "rb") as f:
        while True:
            data = f.read(BUFFER_SIZE)
            if not data:
                break
            hasher.update(data)

    return hasher.hexdigest()


def hash_directory(
    directory: Path,
    patterns: Optional[list] = None,
    algorithm: str = "auto"
) -> Dict[str, str]:
    """Hash all files in a directory, returning relative path -> hash mapping.

    Args:
        directory: Directory to hash
        patterns: Glob patterns to filter files (default: ["*"] for all)
        algorithm: Hash algorithm to use

    Returns:
        Dict mapping relative file paths (as strings) to their hashes

    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    patterns = patterns or ["*"]
    result: Dict[str, str] = {}

    # Collect files matching any pattern
    files_to_hash = set()
    for pattern in patterns:
        # Handle recursive patterns
        if "**" in pattern:
            matched = directory.glob(pattern)
        else:
            # For simple patterns, search recursively
            matched = directory.rglob(pattern)

        for path in matched:
            if path.is_file():
                files_to_hash.add(path)

    # Hash all matched files
    for file_path in sorted(files_to_hash):
        try:
            relative_path = file_path.relative_to(directory)
            # Use forward slashes for consistency across platforms
            key = str(relative_path).replace("\\", "/")
            result[key] = fast_hash_file(file_path, algorithm)
        except (PermissionError, OSError):
            # Skip files we can't read
            pass

    return result


def compare_hashes(
    source_hashes: Dict[str, str],
    target_hashes: Dict[str, str]
) -> Dict[str, list]:
    """Compare two hash dictionaries to find differences.

    Args:
        source_hashes: Hash dict from source directory
        target_hashes: Hash dict from target directory

    Returns:
        Dict with keys:
            - "added": Files in source but not target
            - "removed": Files in target but not source
            - "modified": Files in both but with different hashes
            - "unchanged": Files identical in both
    """
    source_keys = set(source_hashes.keys())
    target_keys = set(target_hashes.keys())

    added = list(source_keys - target_keys)
    removed = list(target_keys - source_keys)

    common = source_keys & target_keys
    modified = []
    unchanged = []

    for key in common:
        if source_hashes[key] != target_hashes[key]:
            modified.append(key)
        else:
            unchanged.append(key)

    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "modified": sorted(modified),
        "unchanged": sorted(unchanged),
    }
