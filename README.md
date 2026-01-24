# CASCADE Enterprise + RAM Disk

Sub-millisecond memory for AI systems. Six cognitive layers. Dual-write architecture. Zero external dependencies.

```
WRITE: Disk (truth) ──> RAM (speed)
READ:  RAM (instant) ──> Disk (fallback)
```

Your AI remembers everything. Reads it back in under a millisecond.

---

## What This Is

An MCP (Model Context Protocol) memory server that gives your AI system persistent, structured memory across six cognitive layers -- backed by a RAM disk for sub-millisecond reads and SQLite for zero-configuration durability.

Two components work together:

1. **MCP Server** (Node.js) -- Exposes 6 memory tools to any MCP-compatible client
2. **RAM Disk Manager** (Python) -- Creates and manages RAM disks across Windows, Linux, and macOS with automatic disk-to-RAM synchronization

The dual-write pattern means you never choose between speed and safety. Writes hit disk first (your data survives power loss), then propagate to RAM (your reads stay instant).

---

## Performance

| Operation | With RAM Disk | Disk Only |
|-----------|:---:|:---:|
| Read (single memory) | <1ms | 2-5ms |
| Write (dual-write) | 3-8ms | 3-8ms |
| Search (100 results) | 5-15ms | 10-30ms |
| Content analysis/routing | <1ms | <1ms |

Writes take the same time either way -- disk is always the first write target. The RAM disk accelerates reads, which is where latency matters for interactive AI.

---

## The Six Layers

| Layer | Purpose | Example Content |
|-------|---------|-----------------|
| `episodic` | Temporal experiences | "User discussed project architecture on Jan 15" |
| `semantic` | Knowledge and facts | "Python's GIL prevents true thread parallelism" |
| `procedural` | Skills and processes | "To deploy: build, test, push, verify health check" |
| `meta` | Self-awareness | "I tend to over-explain technical concepts" |
| `identity` | Personal values, preferences, defining characteristics | "I am a coding assistant focused on Python" |
| `working` | Active context | "Currently debugging the auth middleware" |

When you save a memory without specifying a layer, the content analyzer routes it automatically based on linguistic patterns. Temporal language goes to `episodic`. How-to patterns go to `procedural`. Self-referential content goes to `meta`. The routing runs in under 1ms.

---

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.10+
- Administrator/root access (for RAM disk creation)

### 1. Install the MCP Server

```bash
cd cascade-enterprise-ram
npm install
```

### 2. Install the RAM Disk Manager

```bash
pip install .
```

### 3. Create the RAM Disk

```python
from ram_disk_manager import RamDiskManager, RamDiskConfig
from pathlib import Path

manager = RamDiskManager()
manager.register(RamDiskConfig(
    name="cascade",
    disk_path=Path.home() / ".cascade-memory" / "data",
    size_mb=256
))
ram_path = manager.mount("cascade")
print(f"RAM disk ready at: {ram_path}")
```

On Windows this creates an ImDisk RAM drive (default: `R:\CASCADE_DB`). On Linux it uses tmpfs. On macOS, diskutil.

### 4. Configure Your MCP Client

Add to your MCP client config file (path depends on your client). Example paths:

- Windows: `%APPDATA%\<client>\config.json`
- macOS: `~/Library/Application Support/<client>/config.json`
- Linux: `~/.config/<client>/config.json`

```json
{
  "mcpServers": {
    "cascade-memory": {
      "command": "node",
      "args": ["/absolute/path/to/cascade-enterprise-ram/server/index.js"],
      "env": {
        "CASCADE_DB_PATH": "/home/you/.cascade-memory/data",
        "CASCADE_RAM_PATH": "/mnt/ramdisk/cascade"
      }
    }
  }
}
```

Windows example:

```json
{
  "mcpServers": {
    "cascade-memory": {
      "command": "node",
      "args": ["C:\\cascade-enterprise-ram\\server\\index.js"],
      "env": {
        "CASCADE_DB_PATH": "C:\\Users\\you\\.cascade-memory\\data",
        "CASCADE_RAM_PATH": "R:\\CASCADE_DB"
      }
    }
  }
}
```

### 5. Verify

Once configured, your AI client has access to 6 new tools: `remember`, `recall`, `query_layer`, `save_to_layer`, `get_status`, and `get_stats`.

Test it:
> "Remember that I prefer TypeScript over JavaScript for new projects."

The memory saves to the `semantic` layer (auto-routed), writes to disk, caches in RAM.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MCP Client                         │
│         (Any MCP-compatible application)             │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Protocol (stdio)
                       ▼
┌─────────────────────────────────────────────────────┐
│              CASCADE MCP Server                      │
│                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Validator │  │   Content    │  │    Rate      │  │
│  │           │  │  Analyzer    │  │   Limiter    │  │
│  └──────────┘  └──────────────┘  └──────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │            Dual-Write Database                │   │
│  │                                               │   │
│  │  WRITE: Disk ────────────> RAM                │   │
│  │         (truth)            (cache)            │   │
│  │                                               │   │
│  │  READ:  RAM ──> Disk (fallback)               │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                       │                    │
            ┌──────────┘                    └──────────┐
            ▼                                          ▼
┌───────────────────┐                    ┌───────────────────┐
│   Disk Storage    │                    │    RAM Disk       │
│                   │                    │                   │
│ episodic_memory.db│                    │ episodic_memory.db│
│ semantic_memory.db│                    │ semantic_memory.db│
│ procedural_mem.db │                    │ procedural_mem.db │
│ meta_memory.db    │                    │ meta_memory.db    │
│ identity_memory.db    │                    │ identity_memory.db    │
│ working_memory.db │                    │ working_memory.db │
│                   │                    │                   │
│  DURABLE          │                    │  FAST (<1ms)      │
└───────────────────┘                    └───────────────────┘
```

### Why Dual-Write?

RAM is fast but volatile. Disk is durable but slow. The dual-write pattern gives you both:

- **Writes go to disk first.** Data survives reboots, crashes, power loss. Disk is truth.
- **Writes then propagate to RAM.** The cache stays current without a separate sync step.
- **Reads come from RAM.** Sub-millisecond access for the hot path.
- **If RAM is unavailable**, reads fall back to disk transparently. The system degrades gracefully -- you lose speed, not data.

No write-ahead logs. No eventual consistency. No distributed consensus. Simple, correct, fast.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CASCADE_DB_PATH` | `~/.cascade-memory/data` | Persistent storage path (source of truth) |
| `CASCADE_RAM_PATH` | `R:\CASCADE_DB` (Win) / `/mnt/ramdisk/cascade` (Linux) | RAM disk path (speed cache) |
| `LOG_LEVEL` | `info` | Logging verbosity: debug, info, warn, error |
| `LOG_FORMAT` | `json` | Log output format: json or text |
| `CASCADE_AUDIT_LOG` | *(none)* | Path for persistent audit log file (JSONL) |
| `DEBUG` | `false` | Enable debug mode (exposes stack traces in errors) |

### RAM Disk Manager Configuration

```python
from ram_disk_manager import RamDiskManager, RamDiskConfig, ManagerConfig
from ram_disk_manager.config import SyncStrategy, Platform
from pathlib import Path

# Global manager settings
manager = RamDiskManager(ManagerConfig(
    platform=Platform.AUTO,          # Auto-detect OS
    base_ram_path=Path("R:\\"),      # Windows RAM drive letter
    enable_dual_write=True,          # Enable dual-write controller
))

# Per-disk settings
manager.register(RamDiskConfig(
    name="cascade",
    disk_path=Path("C:/data/cascade"),
    ram_path=Path("R:/CASCADE_DB"),    # Auto-determined if omitted
    size_mb=256,                       # RAM allocation in MB
    patterns=["*.db"],                 # Only sync SQLite files
    sync_strategy=SyncStrategy.INCREMENTAL,  # Hash-based delta sync
    auto_sync_on_startup=True,         # Disk->RAM on mount
    persist_on_shutdown=True,          # RAM->Disk on unmount
    verify_integrity=True,             # Hash verification after sync
))
```

---

## API Reference

Six tools are exposed via MCP. All responses follow a consistent format:

```json
{
  "success": true,
  "tool": "tool_name",
  "timestamp": 1706000000000,
  "data": { ... }
}
```

---

### `remember`

Save a memory with automatic or explicit layer routing.

**Input:**

```json
{
  "content": "The deployment process requires running migrations before starting the app server",
  "layer": "procedural",
  "metadata": {
    "importance": 0.8,
    "emotional_intensity": 0.3,
    "context": "learned during production incident"
  }
}
```

| Parameter | Type | Required | Description |
|-----------|------|:---:|-------------|
| `content` | string | Yes | Memory content (max 100,000 chars) |
| `layer` | string | No | Target layer. Auto-routed if omitted. |
| `metadata.importance` | number | No | Priority weight, 0-1 (default: 0.7) |
| `metadata.emotional_intensity` | number | No | Emotional weight, 0-1 (default: 0.5) |
| `metadata.context` | string | No | Additional context for search |

**Response:**

```json
{
  "success": true,
  "data": {
    "layer": "procedural",
    "id": 42,
    "timestamp": 1706000000.0,
    "dual_write": true
  }
}
```

---

### `recall`

Search memories across one or all layers.

**Input:**

```json
{
  "query": "deployment process",
  "layer": "procedural",
  "limit": 5
}
```

| Parameter | Type | Required | Description |
|-----------|------|:---:|-------------|
| `query` | string | Yes | Search text (matched against content and context) |
| `layer` | string | No | Restrict to one layer. Searches all if omitted. |
| `limit` | number | No | Max results, 1-1000 (default: 10) |

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "layer": "procedural",
      "id": 42,
      "timestamp": 1706000000.0,
      "content": "The deployment process requires...",
      "context": "learned during production incident",
      "importance": 0.8,
      "emotional_intensity": 0.3,
      "metadata": {}
    }
  ]
}
```

---

### `query_layer`

Query a specific layer with structured filters. All filters use parameterized queries.

**Input:**

```json
{
  "layer": "episodic",
  "options": {
    "filters": {
      "importance_min": 0.7,
      "timestamp_after": 1705000000,
      "content_contains": "architecture"
    },
    "order_by": "importance DESC",
    "limit": 20
  }
}
```

**Available Filters:**

| Filter | Type | Description |
|--------|------|-------------|
| `importance_min` / `importance_max` | number | Importance bounds (0-1) |
| `emotional_intensity_min` / `emotional_intensity_max` | number | Emotional intensity bounds (0-1) |
| `timestamp_after` / `timestamp_before` | number | Unix timestamp bounds |
| `content_contains` | string | Text search in content |
| `context_contains` | string | Text search in context |
| `id` | number | Exact memory ID |

**Order By options:** `timestamp`, `importance`, `emotional_intensity`, `id` -- each with `ASC` or `DESC`.

---

### `save_to_layer`

Save directly to a specific layer with full metadata control. Bypasses auto-routing.

```json
{
  "layer": "identity",
  "content": "I am a Python-focused assistant with expertise in distributed systems",
  "metadata": {
    "importance": 1.0,
    "context": "core identity definition"
  }
}
```

---

### `get_status`

Returns system health, layer counts, dual-write configuration, and path information.

```json
{
  "success": true,
  "data": {
    "version": "2.0.0",
    "health": "healthy",
    "total_memories": 1247,
    "layers": {
      "episodic": { "status": "connected", "count": 523 },
      "semantic": { "status": "connected", "count": 312 },
      "procedural": { "status": "connected", "count": 89 },
      "meta": { "status": "connected", "count": 67 },
      "identity": { "status": "connected", "count": 45 },
      "working": { "status": "connected", "count": 211 }
    },
    "dual_write": {
      "enabled": true,
      "ram_enabled": true,
      "read_path": "R:\\CASCADE_DB",
      "disk_path": "C:\\Users\\you\\.cascade-memory\\data"
    }
  }
}
```

---

### `get_stats`

Returns per-layer statistics: memory counts, average importance, average emotional intensity, most recent timestamp.

---

## RAM Disk Manager

### Python API

```python
from ram_disk_manager import RamDiskManager, RamDiskConfig
from pathlib import Path

manager = RamDiskManager()

# Register and mount
manager.register(RamDiskConfig(
    name="cascade",
    disk_path=Path.home() / ".cascade-memory" / "data",
    size_mb=256
))
ram_path = manager.mount("cascade")

# Check status
status = manager.status()
print(f"Mounted: {status['disks']['cascade']['mounted']}")
print(f"Usage: {status['disks']['cascade']['usage']['percent_used']}%")

# Manual sync operations
manager.sync_to_ram("cascade")   # Disk -> RAM (refresh cache)
manager.sync_to_disk("cascade")  # RAM -> Disk (persist changes)

# Clean shutdown (persists automatically if configured)
manager.unmount("cascade", persist=True)
```

### Sync Strategies

| Strategy | Behavior | Best For |
|----------|----------|----------|
| `FULL` | Copies all matching files | First mount, disaster recovery |
| `INCREMENTAL` | Hash-based delta sync -- only changed files | Regular operation (fastest) |
| `PATTERN` | Strict glob matching | Selective sync of specific file types |

### Platform Backends

| Platform | Technology | Drive Letter / Mount Point | Admin Required |
|----------|-----------|---------------------------|:-:|
| Windows | ImDisk | Configurable (default: `R:\`) | Yes |
| Linux | tmpfs | Configurable (default: `/mnt/ramdisk`) | Yes (mount) |
| macOS | diskutil | Configurable | Yes |

### Automatic Recovery

The manager writes a clean shutdown marker on exit. If the marker is missing at next startup, it means the previous session crashed -- the manager automatically performs a full sync from disk to restore the RAM cache to a known-good state.

---

## Security

Hardened for production. Audited for enterprise deployment.

### Input Validation

- Content: max 100,000 characters
- Queries: max 1,000 characters
- Context: max 10,000 characters
- Metadata: max 50,000 bytes JSON
- Numerics: bounded ranges enforced (importance 0-1, limits 1-1000)
- Layer names: strict whitelist

### SQL Injection Prevention

- Parameterized statements for all queries
- LIKE patterns escaped (`%`, `_`, `\` handled)
- ORDER BY validated against column whitelist
- No raw SQL accepted from client input

### Rate Limiting

| Scope | Limit |
|-------|-------|
| Global | 300 requests/minute |
| `remember` | 60/min |
| `recall` | 120/min |
| `query_layer` | 100/min |
| `get_status` / `get_stats` | 30/min |
| `save_to_layer` | 60/min |

Rate-limited responses include `retryAfterMs` for client-side back-off.

### Error Sanitization

Production errors never expose:
- Filesystem paths
- Environment variable contents
- Internal IP addresses
- Stack traces (unless `DEBUG=true`)

### Audit Trail

Every memory operation is logged with:
- Unique request ID
- Operation type and parameters
- Duration in milliseconds
- Success/failure status
- Error codes (on failure)

Configure `CASCADE_AUDIT_LOG` for persistent JSONL audit output.

---

## Logging

### Structured Logger

All logs are JSON by default (machine-parseable). Set `LOG_FORMAT=text` for human-readable output with color support.

```json
{
  "timestamp": "2026-01-22T12:00:00.000Z",
  "level": "info",
  "service": "cascade-memory",
  "version": "2.0.0",
  "sessionId": "m1abc123-xyz789012",
  "message": "Memory saved successfully",
  "context": {
    "requestId": "m1abc123-xyz789012-42",
    "layer": "semantic",
    "memoryId": 156,
    "durationMs": 3
  }
}
```

### Log Levels

| Level | Priority | Use |
|-------|:---:|-----|
| `debug` | 10 | Internal state, detailed flow |
| `info` | 20 | Normal operations, startup, shutdown |
| `warn` | 30 | Degraded state, fallbacks triggered |
| `error` | 40 | Failed operations, exceptions |
| `audit` | 50 | Security-relevant events (always logged) |

---

## Database Schema

Each of the six layers uses an identical SQLite schema:

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    content TEXT,
    event TEXT,
    context TEXT,
    emotional_intensity REAL DEFAULT 0.5,
    importance REAL DEFAULT 0.5,
    metadata TEXT
);

CREATE INDEX idx_memories_timestamp ON memories(timestamp);
CREATE INDEX idx_memories_importance ON memories(importance);
```

Databases are created automatically on first write. No migrations required.

---

## Project Structure

```
cascade-enterprise-ram/
├── server/                     # Node.js MCP Server
│   ├── index.js                # Entry point, logging, MCP lifecycle
│   ├── database.js             # Dual-write layer, connection pool
│   ├── tools.js                # Tool handlers, rate limiting
│   ├── validation.js           # Input validation rules
│   └── content_analyzer.js     # Automatic layer routing (<1ms)
├── ram_disk_manager/           # Python RAM Disk Manager
│   ├── __init__.py             # Package exports
│   ├── manager.py              # High-level unified API
│   ├── config.py               # Configuration dataclasses
│   ├── backends/               # OS-specific RAM disk implementations
│   │   ├── base.py             # Abstract backend interface
│   │   ├── windows.py          # ImDisk backend
│   │   └── linux.py            # tmpfs backend
│   ├── sync/                   # Synchronization engines
│   │   ├── engine.py           # Sync orchestration
│   │   └── dual_write.py       # Dual-write controller
│   ├── recovery/               # Crash recovery
│   │   ├── detector.py         # Unclean shutdown detection
│   │   ├── integrity.py        # Hash verification
│   │   └── auto_sync.py        # Automatic recovery sync
│   └── utils/                  # Shared utilities
│       ├── hashing.py          # File hash computation (SHA-256)
│       ├── logging.py          # Log configuration
│       └── platform.py         # Platform detection
├── examples/                   # Working integration examples
│   ├── basic_usage.py
│   ├── cascade_integration.py
│   ├── dual_write_example.py
│   └── incremental_sync.py
├── tests/                      # Test suites (npm test / pytest)
├── package.json                # Node.js config (npm install)
├── pyproject.toml              # Python config (pip install .)
├── setup.py                    # Legacy pip support
├── SECURITY.md                 # Security policy
├── CHANGELOG.md                # Version history
└── LICENSE                     # Commercial license
```

---

## Development

### Running Locally

```bash
# Development mode (verbose logging)
DEBUG=true LOG_LEVEL=debug node server/index.js

# Production mode
node server/index.js
```

### Running Tests

```bash
# MCP Server tests
npm test                        # All tests
npm run test:validation         # Input validation
npm run test:integration        # End-to-end

# RAM Disk Manager tests
pip install ".[test]"
pytest
```

---

## Troubleshooting

### RAM disk not mounting

**Windows:** Install [ImDisk Toolkit](http://www.ltr-data.se/opencode.html/#ImDisk). Run your script as Administrator.

**Linux:** Ensure mount permissions. For persistent mount, add to `/etc/fstab`:
```
tmpfs /mnt/ramdisk/cascade tmpfs size=256M,mode=0755 0 0
```

**macOS:** Grant terminal Full Disk Access in System Preferences > Privacy & Security.

### MCP server not connecting

1. Use absolute paths in your MCP config (not relative)
2. Verify Node.js 18+: `node --version`
3. Run manually to see startup errors: `node server/index.js`
4. Check that `CASCADE_DB_PATH` exists and is writable

### Dual-write shows "ram_enabled: false"

The server auto-detects RAM disk availability at startup. If `CASCADE_RAM_PATH` doesn't exist and can't be created, it falls back to disk-only mode. This is safe -- you lose speed, not data.

Fix: mount the RAM disk *before* starting the MCP server.

### Sizing the RAM disk

Each SQLite database stays small under normal use (typically <50MB per layer). Allocate at least 2x your total expected database size for WAL files and write headroom.

- Typical use: 256MB
- Heavy workloads: 512MB
- Maximum observed per layer: ~200MB (50,000+ memories with long content)

### Rate limit errors (429)

Check for retry loops in your client. The error response includes `retryAfterMs` -- respect it. Default limits are generous for normal interactive use (300 requests/minute global).

---

## License and Guarantee

**CASCADE Enterprise + RAM Disk** is a commercial product of C.I.P.S. LLC.

| | |
|---|---|
| **Price** | $500 one-time purchase |
| **Updates** | Unlimited for 1 year from purchase |
| **License scope** | Single organization, unlimited developers |
| **Guarantee** | 90-day money-back, no questions asked |

If it doesn't meet your needs within 90 days, you get a full refund. Period.

**Contact:** glass@cipscorps.io
**Website:** [cipscorps.io](https://cipscorps.io)

---

*Sub-millisecond memory for AI systems that need to remember. Built by C.I.P.S. LLC.*
