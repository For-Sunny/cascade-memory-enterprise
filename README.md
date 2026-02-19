# CASCADE Enterprise RAM

**6-Layer Structured Memory for AI Systems**

Sub-millisecond access. Importance scoring. Dual-write persistence. Your AI remembers what matters.

---

## What It Does

CASCADE gives your AI a memory system with six specialized layers:

| Layer | Purpose |
|-------|---------|
| **working** | Current session context |
| **episodic** | Event-based memories with timestamps |
| **semantic** | Facts and knowledge |
| **procedural** | How-to and process memory |
| **meta** | Memory about memory (reflection) |
| **identity** | High-importance persistent storage |

Important memories persist based on the importance score you assign. Higher importance = longer retention when you implement your own retention policies.

---

## Features

- **Sub-millisecond access** via optional RAM disk acceleration
- **Importance scoring** - high-value memories persist based on score you assign
- **Dual-write** - RAM for speed, SQLite for persistence
- **MCP server** - native integration with Claude and other MCP clients
- **Six specialized layers** - right memory in the right place
- **Temporal decay** - memories fade over time unless accessed or marked important. Importance >= 0.9 makes a memory immortal.

---

## Platform Support

| Platform | Architecture | Status |
|----------|-------------|--------|
| Windows x64 | Intel/AMD | Supported |
| Windows ARM64 | Snapdragon/Qualcomm | Supported (v2.1.0+) |
| Linux x64 | Intel/AMD | Supported |
| Linux ARM64 | ARM servers, Raspberry Pi | Supported |
| macOS x64 | Intel | Supported |
| macOS ARM64 | Apple Silicon | Supported |

---

## Installation

Three paths. Pick what fits.

### Windows (Native)

Requirements: Node.js >= 18, Python >= 3.10, Admin access for RAM disk

```powershell
# Clone and install
git clone https://github.com/cipscorp/cascade-enterprise-ram.git
cd cascade-enterprise-ram
npm install
pip install .

# Create RAM disk (run as Administrator)
python -m ram_disk_manager init --disk-path ./data --size 512
```

### Linux / macOS (Native)

Requirements: Node.js >= 18, Python >= 3.10, sudo access for RAM disk

```bash
# Clone and install
git clone https://github.com/cipscorp/cascade-enterprise-ram.git
cd cascade-enterprise-ram
npm install

# Python dependencies (use virtual environment on modern Linux)
python3 -m venv .venv
source .venv/bin/activate
pip install .

# Create RAM disk (requires sudo - use full path to venv python)
sudo $(which python) -m ram_disk_manager init --disk-path ./data --size 512
```

RAM disk paths by platform:
- **Windows**: Uses ImDisk, mounts to `R:\` by default
- **Linux**: Uses tmpfs, mounts to `/mnt/ramdisk/`
- **macOS**: Uses diskutil, mounts to `/Volumes/RAMDisk/`

### Docker (Teams / Enterprise)

Requirements: Docker, docker-compose

```bash
docker-compose up -d --build
```

Data persists in `./data`. Container uses tmpfs internally. See `README_DOCKER.md` for details.

---

## MCP Client Configuration

CASCADE is an MCP server. It communicates via stdio, not HTTP.

### Claude Desktop

Add to your `claude_desktop_config.json`:

**Windows:**
```json
{
  "mcpServers": {
    "cascade-memory": {
      "command": "node",
      "args": ["C:\\path\\to\\cascade-enterprise-ram\\server\\index.js"],
      "env": {
        "CASCADE_DB_PATH": "C:\\path\\to\\cascade-enterprise-ram\\data",
        "CASCADE_RAM_PATH": "R:\\cascade"
      }
    }
  }
}
```

**macOS / Linux:**
```json
{
  "mcpServers": {
    "cascade-memory": {
      "command": "node",
      "args": ["/path/to/cascade-enterprise-ram/server/index.js"],
      "env": {
        "CASCADE_DB_PATH": "/path/to/cascade-enterprise-ram/data",
        "CASCADE_RAM_PATH": "/mnt/ramdisk/cascade"
      }
    }
  }
}
```

Restart your MCP client after config changes.

### Verify

Run the server directly to test:

```bash
node server/index.js
```

You should see output beginning with:
```
{"message":"CASCADE Enterprise Memory MCP Server v2.2.2"}
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Persistent database location (source of truth)
CASCADE_DB_PATH=./data

# RAM disk mount point (sub-millisecond reads)
# Windows: R:\cascade
# Linux: /mnt/ramdisk/cascade
# macOS: /Volumes/RAMDisk/cascade
CASCADE_RAM_PATH=

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
DEBUG=false

# Temporal Decay
DECAY_ENABLED=true              # Enable/disable temporal decay
DECAY_BASE_RATE=0.01            # Decay speed per day (higher = faster fade)
DECAY_THRESHOLD=0.1             # Effective importance below this hides memories
DECAY_IMMORTAL_THRESHOLD=0.9    # Importance at or above this never decays
DECAY_SWEEP_INTERVAL=60         # Minutes between decay sweeps
DECAY_SWEEP_BATCH_SIZE=1000     # Max memories processed per layer per sweep
```

---

## API Reference

CASCADE exposes seven MCP tools:

### remember

Store a memory in a specific layer.

```json
{
  "tool": "remember",
  "arguments": {
    "content": "User prefers dark mode interfaces",
    "layer": "semantic",
    "importance": 0.8,
    "metadata": {
      "source": "user_preference"
    }
  }
}
```

**Parameters:**
- `content` (required): The memory content
- `layer` (optional): episodic, semantic, procedural, meta, identity, working. Default: auto-determined from content (fallback: working)
- `importance` (optional): 0.0-1.0. Higher values indicate higher priority. Default: 0.7
- `metadata` (optional): Key-value pairs for additional context

### recall

Search memories across all layers or a specific layer.

```json
{
  "tool": "recall",
  "arguments": {
    "query": "user interface preferences",
    "layer": "semantic",
    "limit": 10
  }
}
```

**Parameters:**
- `query` (required): Search query
- `layer` (optional): Limit search to specific layer
- `limit` (optional): Maximum results. Default: 10
- `include_decayed` (optional): If true, include memories that have decayed below threshold. Default: false

### query_layer

Get all memories from a specific layer.

```json
{
  "tool": "query_layer",
  "arguments": {
    "layer": "working",
    "options": {
      "limit": 50,
      "order_by": "timestamp DESC"
    }
  }
}
```

**Parameters:**
- `layer` (required): Layer to query
- `options` (optional): Object with `filters`, `limit`, `order_by`
- `include_decayed` (optional): If true, include decayed memories. Default: false

Results include `effective_importance` (importance adjusted for decay) on each memory.

### get_status

Get system status and statistics.

```json
{
  "tool": "get_status",
  "arguments": {}
}
```

Returns memory counts per layer, health status, version, dual-write configuration, and decay engine status (enabled, sweep interval, thresholds).

### get_stats

Get detailed statistics for all memory layers.

```json
{
  "tool": "get_stats",
  "arguments": {}
}
```

Returns per-layer statistics including memory count, average importance, average emotional intensity, most recent timestamp, and decay counts (immortal, active, decayed).

### save_to_layer

Save memory to a specific layer with full control over metadata.

```json
{
  "tool": "save_to_layer",
  "arguments": {
    "layer": "semantic",
    "content": "Important fact to remember",
    "metadata": {
      "importance": 0.9,
      "emotional_intensity": 0.3,
      "context": "user knowledge base"
    }
  }
}
```

**Parameters:**
- `layer` (required): Target layer (episodic, semantic, procedural, meta, identity, working)
- `content` (required): The memory content to save
- `metadata` (optional): Full metadata control including importance, emotional_intensity, context

### get_echo_stats

Get CASCADE echo ratio health metrics. Read-only monitoring that shows how much of each layer's content is derived (echoed) versus original.

```json
{
  "tool": "get_echo_stats",
  "arguments": {}
}
```

Returns per-layer echo ratios, overall statistics, and warnings when any layer exceeds 40% derived content.

---

## RAM Disk Management

The Python package manages RAM disks across platforms.

**Windows (run as Administrator):**
```powershell
python -m ram_disk_manager init --disk-path ./data --size 512
python -m ram_disk_manager status
python -m ram_disk_manager sync --disk-path ./data --direction to-disk
python -m ram_disk_manager destroy --disk-path ./data
```

**Linux/macOS (with venv activated):**
```bash
# Create RAM disk (requires sudo with full python path)
sudo $(which python) -m ram_disk_manager init --disk-path ./data --size 512

# These don't need sudo
python -m ram_disk_manager status
python -m ram_disk_manager sync --disk-path ./data --direction to-disk
python -m ram_disk_manager destroy --disk-path ./data
```

RAM disk creation requires elevated privileges (Admin on Windows, sudo on Linux/macOS).

---

## Performance

### Benchmarks

Measured on a dedicated development machine. Your results will vary based on hardware, disk type, and system load.

| Operation | RAM Disk | Disk Only | Notes |
|-----------|----------|-----------|-------|
| Single read | <1ms | 2-5ms | RAM path uses tmpfs/ImDisk/diskutil |
| Single write | 3-8ms | 2-5ms | Dual-write: disk first, then RAM |
| Search (100 results) | 5-15ms | 10-30ms | SQLite LIKE query across layer |
| Decay sweep (1000 memories) | 50-150ms | 100-300ms | Batch UPDATE per layer |

### Benchmark Hardware

| Component | Spec |
|-----------|------|
| CPU | AMD/Intel x64 (multi-core) |
| RAM | 16GB+ (512MB allocated to RAM disk) |
| Disk | NVMe SSD |
| OS | Ubuntu 22.04 / Windows 11 |
| Node.js | v20 LTS |

### Methodology

Performance numbers were measured using the following approach:

1. **Read latency**: `console.time`/`console.timeEnd` around `better-sqlite3` `.get()` calls on a database with 1,000+ rows. Median of 100 iterations, measured after database is warm (first query excluded).

2. **Write latency**: End-to-end time for a `remember` operation including dual-write (disk + RAM). Measured from tool handler entry to return, 100 iterations, median reported.

3. **Search latency**: `recall` tool with `LIKE` query matching ~100 results across a layer with 1,000+ memories. Median of 50 iterations.

4. **RAM disk vs disk**: RAM disk performance assumes tmpfs (Linux), ImDisk (Windows), or diskutil (macOS) is mounted and `CASCADE_RAM_PATH` is set. Without RAM disk, all operations use disk path only.

### Reproducing Benchmarks

Run the server with `DEBUG=true` to see per-operation timing in structured logs:

```bash
DEBUG=true node server/index.js
```

Each tool invocation logs its duration in the audit trail. For systematic benchmarking, use the MCP client to issue repeated tool calls and collect the `durationMs` field from audit log entries.

---

## Troubleshooting

### Server won't start

Check that `npm install` completed successfully. Missing dependencies cause silent failures.

### MCP tools not appearing in Claude

1. Verify server runs standalone: `node server/index.js`
2. Check paths in config are absolute, not relative
3. Restart Claude Desktop after config changes
4. Check Claude Desktop logs for MCP connection errors

### "Database locked" errors

SQLite doesn't handle concurrent writes. Solutions:
1. Ensure only one CASCADE instance runs per database
2. Kill zombie node processes: `taskkill /F /IM node.exe` (Windows) or `pkill node` (Linux/macOS)

### Memories not persisting after restart

RAM disk contents are lost on reboot. Ensure `CASCADE_DB_PATH` points to persistent storage. The dual-write system writes to both locations, but you need the disk path configured.

### npm install fails on ARM64 Windows

Older versions (< 2.1.0) used the `sqlite3` npm package, which required native compilation via node-gyp. This failed on ARM64 Windows due to missing prebuilt binaries.

v2.1.0 replaced `sqlite3` with `better-sqlite3`, which ships prebuilt binaries for ARM64 Windows, x64 Windows, Linux, and macOS. Run `npm install` on v2.1.0+ and it works.

### RAM disk creation fails

- **Windows**: ImDisk driver required. The manager installs it automatically, but you need Admin rights.
- **Linux**: tmpfs is kernel built-in. Just need sudo.
- **macOS**: diskutil is built-in. Just need sudo.

---

## Support

- **Documentation:** [cipscorps.io](https://cipscorps.io)
- **Support:** support@cipscorps.io
- **Bug Reports:** Include CASCADE version, OS, and error output

---

## License

MIT License. See [LICENSE](./LICENSE) for terms.

---

**Made by [CIPS Corp](https://cipscorps.io)**

[Website](https://cipscorps.io) | [Store](https://store.cipscorps.io) | [GitHub](https://github.com/For-Sunny) | glass@cipscorps.io

Enterprise cognitive infrastructure for AI systems: [PyTorch Memory, Soul Matrix, CMM, and the full CIPS Stack](https://store.cipscorps.io).

Copyright (c) 2025-2026 C.I.P.S. LLC
