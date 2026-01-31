# CASCADE Enterprise RAM

**6-Layer Temporal Memory for AI Systems**

Sub-millisecond access. Temporal decay. Dual-write persistence. Your AI remembers what matters and forgets what doesn't.

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
| **opus** | High-importance persistent storage |

Memories decay over time unless reinforced. Important memories persist. Trivial ones fade. Like biological memory, but faster.

---

## Features

- **Sub-millisecond access** via optional RAM disk acceleration
- **Temporal decay** - memories fade naturally based on age and importance
- **Importance scoring** - high-value memories resist decay
- **Dual-write** - RAM for speed, SQLite for persistence
- **MCP server** - native integration with Claude and other MCP clients
- **Six specialized layers** - right memory in the right place

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
pip install .

# Create RAM disk (requires sudo)
sudo python -m ram_disk_manager init --disk-path ./data --size 512
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

You should see:
```
CASCADE Memory MCP Server started
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
```

---

## API Reference

CASCADE exposes four MCP tools:

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
- `layer` (optional): episodic, semantic, procedural, meta, opus, working. Default: episodic
- `importance` (optional): 0.0-1.0. Higher values resist decay. Default: 0.5
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

### query_layer

Get all memories from a specific layer.

```json
{
  "tool": "query_layer",
  "arguments": {
    "layer": "working",
    "include_decayed": false
  }
}
```

**Parameters:**
- `layer` (required): Layer to query
- `include_decayed` (optional): Include memories below decay threshold. Default: false

### get_status

Get system status and statistics.

```json
{
  "tool": "get_status",
  "arguments": {}
}
```

Returns memory counts per layer, decay status, and database size.

---

## RAM Disk Management

The Python package manages RAM disks across platforms.

```bash
# Create a RAM disk
python -m ram_disk_manager init --disk-path ./data --size 512

# Check status
python -m ram_disk_manager status

# Sync RAM to disk manually
python -m ram_disk_manager sync --disk-path ./data --direction to-disk

# Destroy (persists data first by default)
python -m ram_disk_manager destroy --disk-path ./data
```

RAM disk creation requires elevated privileges (Admin on Windows, sudo on Linux/macOS).

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

Proprietary software. See LICENSE file for terms.

Single-seat license included with purchase. For team or enterprise licensing, contact sales@cipscorps.io.

---

*Built by C.I.P.S. Corp*
