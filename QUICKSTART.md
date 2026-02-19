# Quickstart

Zero to running. Five minutes.

---

## Prerequisites

- Node.js >= 18
- Python >= 3.10
- Admin/root access (RAM disk creation requires it)

RAM disk drivers by platform:
- **Windows**: ImDisk (installed automatically)
- **Linux**: tmpfs (kernel built-in)
- **macOS**: diskutil (built-in)

---

## Install

```bash
npm install
pip install .
python -m ram_disk_manager init
```

The third command creates your RAM disk. Run it as admin (Windows) or with sudo (Linux/macOS).

---

## Configure Your MCP Client

Add to your MCP client config:

| Platform | Config Location (example) |
|----------|----------------|
| Windows | `%APPDATA%\<client>\config.json` |
| macOS | `~/Library/Application Support/<client>/config.json` |
| Linux | `~/.config/<client>/config.json` |

```json
{
  "mcpServers": {
    "cascade-memory": {
      "command": "node",
      "args": ["<install-path>/server/index.js"],
      "env": {
        "CASCADE_DB_PATH": "<install-path>/data",
        "CASCADE_RAM_PATH": "<ram-path>"
      }
    }
  }
}

```

Set `CASCADE_RAM_PATH` for your platform:

| Platform | RAM Path |
|----------|----------|
| Windows | `R:\\CASCADE_DB` |
| Linux | `/mnt/ramdisk/cascade` |
| macOS | `/Volumes/RAMDisk/cascade` |

Replace `<install-path>` with your actual install directory.

---

## Verify

```bash
node server/index.js
```

You should see output beginning with:

```
{"message":"CASCADE Enterprise Memory MCP Server v2.2.2"}
```

If you don't, check that `npm install` completed and your paths are correct.

---

## First Memory

Once your MCP client connects to the server, save a memory:

```
Save this to memory: "Project kickoff was January 23, 2026. Team size: 4."
```

Recall it:

```
What do you remember about the project kickoff?
```

The memory persists on disk. The RAM layer gives you sub-millisecond access. Both work together -- RAM for speed, disk for durability.

---

## What You Have

- **6-layer memory architecture** -- episodic, semantic, procedural, meta, identity, working
- **Sub-millisecond RAM access** with automatic disk persistence
- **Importance scoring** -- high-value memories persist; mark what matters
- **Cross-layer search** -- one query hits all layers
- **Temporal decay** -- memories fade unless accessed or marked important (importance >= 0.9 = immortal)

You're running. Build something.
