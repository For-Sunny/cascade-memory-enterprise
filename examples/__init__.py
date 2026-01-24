"""Example scripts for RAM Disk Manager.

Available examples:

basic_usage.py
    Basic RAM disk operations: register, mount, use, unmount, recover.
    Start here to understand the core workflow.

dual_write_example.py
    Dual-write pattern: disk first, RAM second.
    Shows how to maintain data safety while getting RAM speed.

incremental_sync.py
    Hash-based incremental sync strategy.
    Only syncs changed files for maximum efficiency.

cascade_integration.py
    SQLite database integration pattern.
    Shows how to use RAM disk with databases for sub-ms access.

Run any example:
    python examples/basic_usage.py
    python examples/dual_write_example.py
    python examples/incremental_sync.py
    python examples/cascade_integration.py
"""
