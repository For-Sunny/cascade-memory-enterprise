"""CLI entry point for RAM Disk Manager.

Usage:
    python -m ram_disk_manager init [--name NAME] [--disk-path PATH] [--size SIZE_MB]
    python -m ram_disk_manager status [--name NAME]
    python -m ram_disk_manager sync [--name NAME] [--direction to-ram|to-disk]
    python -m ram_disk_manager destroy [--name NAME] [--no-persist]

Commands:
    init      Create and mount a RAM disk
    status    Show status of managed RAM disks
    sync      Synchronize between RAM and persistent storage
    destroy   Unmount and destroy a RAM disk
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from ram_disk_manager import RamDiskManager, RamDiskConfig, ManagerConfig, SyncStrategy


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_init(args: argparse.Namespace) -> int:
    """Handle the 'init' command - create and mount a RAM disk.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    manager = RamDiskManager()

    config = RamDiskConfig(
        name=args.name,
        disk_path=Path(args.disk_path),
        size_mb=args.size,
        sync_strategy=SyncStrategy(args.strategy) if args.strategy else SyncStrategy.FULL,
    )

    if args.ram_path:
        config.ram_path = Path(args.ram_path)

    try:
        manager.register(config)
        ram_path = manager.mount(args.name)
        print(f"RAM disk '{args.name}' mounted at: {ram_path}")
        print(f"  Size: {args.size} MB")
        print(f"  Disk path: {args.disk_path}")
        print(f"  Strategy: {config.sync_strategy.value}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Handle the 'status' command - show RAM disk status.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    manager = RamDiskManager()

    # If a specific disk is named, check if it exists at the expected path
    if args.name and args.disk_path:
        config = RamDiskConfig(
            name=args.name,
            disk_path=Path(args.disk_path),
        )
        if args.ram_path:
            config.ram_path = Path(args.ram_path)
        manager.register(config)

    status = manager.status()

    if args.json:
        print(json.dumps(status, indent=2, default=str))
    else:
        print(f"Platform: {status['platform']}")
        print(f"Backend available: {status['backend_available']}")
        print(f"Backend: {status['backend_message']}")
        print()

        if status["disks"]:
            for name, disk_info in status["disks"].items():
                print(f"  [{name}]")
                print(f"    Mounted: {disk_info['mounted']}")
                print(f"    Disk path: {disk_info['disk_path']}")
                print(f"    RAM path: {disk_info['ram_path']}")
                print(f"    Size: {disk_info['size_mb']} MB")
                print(f"    Strategy: {disk_info['sync_strategy']}")
                print(f"    Sync count: {disk_info['sync_count']}")
                if disk_info.get("usage"):
                    usage = disk_info["usage"]
                    print(f"    Usage: {usage['used_mb']} / {usage['total_mb']} MB ({usage['percent_used']:.1f}%)")
                print()
        else:
            print("  No disks registered.")

    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Handle the 'sync' command - synchronize RAM and disk.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    manager = RamDiskManager()

    if not args.disk_path:
        print("Error: --disk-path is required for sync", file=sys.stderr)
        return 1

    config = RamDiskConfig(
        name=args.name,
        disk_path=Path(args.disk_path),
    )
    if args.ram_path:
        config.ram_path = Path(args.ram_path)

    manager.register(config)

    try:
        if args.direction == "to-ram":
            result = manager.sync_to_ram(args.name, force_full=args.full)
        elif args.direction == "to-disk":
            result = manager.sync_to_disk(args.name)
        else:
            print(f"Error: Unknown direction '{args.direction}'", file=sys.stderr)
            return 1

        if result.get("success"):
            print(f"Sync {args.direction} complete:")
            print(f"  Files synced: {result['files_synced']}")
            print(f"  Bytes synced: {result['bytes_synced']:,}")
            print(f"  Duration: {result['duration_ms']:.1f} ms")
            return 0
        else:
            print(f"Sync failed: {result.get('error', 'Unknown error')}", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_destroy(args: argparse.Namespace) -> int:
    """Handle the 'destroy' command - unmount and destroy RAM disk.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    manager = RamDiskManager()

    if not args.disk_path:
        print("Error: --disk-path is required for destroy", file=sys.stderr)
        return 1

    config = RamDiskConfig(
        name=args.name,
        disk_path=Path(args.disk_path),
        persist_on_shutdown=not args.no_persist,
    )
    if args.ram_path:
        config.ram_path = Path(args.ram_path)

    manager.register(config)

    # Mark as mounted so unmount will process it
    if args.name in manager.disks:
        manager.disks[args.name].mounted = True

    try:
        success = manager.unmount(args.name, persist=not args.no_persist)
        if success:
            print(f"RAM disk '{args.name}' destroyed successfully.")
            if not args.no_persist:
                print(f"  Data persisted to: {args.disk_path}")
            return 0
        else:
            print(f"Failed to destroy RAM disk '{args.name}'", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="ram_disk_manager",
        description="CASCADE RAM Disk Manager - Cross-platform high-performance RAM disk management",
        epilog="For more information, see: https://cipscorps.io/cascade-enterprise",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s 2.2.0"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Create and mount a RAM disk")
    init_parser.add_argument("--name", default="default", help="RAM disk name (default: 'default')")
    init_parser.add_argument("--disk-path", required=True, help="Persistent storage path (source of truth)")
    init_parser.add_argument("--ram-path", help="RAM disk mount path (auto-detected if not specified)")
    init_parser.add_argument("--size", type=int, default=512, help="RAM disk size in MB (default: 512)")
    init_parser.add_argument(
        "--strategy", choices=["full", "incremental", "pattern"],
        default="full", help="Sync strategy (default: full)"
    )

    # status command
    status_parser = subparsers.add_parser("status", help="Show RAM disk status")
    status_parser.add_argument("--name", help="Specific disk name to check")
    status_parser.add_argument("--disk-path", help="Disk path for the named disk")
    status_parser.add_argument("--ram-path", help="RAM path for the named disk")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Synchronize RAM and disk")
    sync_parser.add_argument("--name", default="default", help="RAM disk name")
    sync_parser.add_argument("--disk-path", required=True, help="Persistent storage path")
    sync_parser.add_argument("--ram-path", help="RAM disk path")
    sync_parser.add_argument(
        "--direction", choices=["to-ram", "to-disk"],
        default="to-ram", help="Sync direction (default: to-ram)"
    )
    sync_parser.add_argument("--full", action="store_true", help="Force full sync")

    # destroy command
    destroy_parser = subparsers.add_parser("destroy", help="Unmount and destroy RAM disk")
    destroy_parser.add_argument("--name", default="default", help="RAM disk name")
    destroy_parser.add_argument("--disk-path", required=True, help="Persistent storage path")
    destroy_parser.add_argument("--ram-path", help="RAM disk path")
    destroy_parser.add_argument(
        "--no-persist", action="store_true",
        help="Do NOT persist RAM contents to disk before destroying"
    )

    return parser


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    setup_logging(verbose=args.verbose)

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "sync": cmd_sync,
        "destroy": cmd_destroy,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
