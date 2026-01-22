# Opus CASCADE Memory System

[![npm version](https://img.shields.io/npm/v/@opus-warrior/cascade-memory.svg)](https://www.npmjs.com/package/@opus-warrior/cascade-memory)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen.svg)](https://nodejs.org/)

**Enterprise-Grade MCP Server for 6-Layer Memory Architecture**

---

## Overview

The Opus CASCADE Memory System is a production-ready MCP (Model Context Protocol) server implementing a sophisticated 6-layer memory architecture with enterprise security features. Built for AI memory persistence and strategic memory management.

**Key Features:**
- 6-layer memory architecture (episodic, semantic, procedural, meta, opus, working)
- Dual-write pattern (RAM + disk) for speed and durability
- Comprehensive input validation with strict whitelisting
- In-memory rate limiting with DoS protection
- Centralized error handling with sanitized responses
- Structured JSON logging with audit trails
- SQLite-backed persistent storage

---

## Table of Contents

1. [Architecture](#architecture)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Security Features](#security-features)
5. [API Reference](#api-reference)
6. [Error Handling](#error-handling)
7. [Logging System](#logging-system)
8. [Performance](#performance)
9. [Development](#development)

---

## Architecture

### 6-Layer Memory Model

| Layer | Purpose | Use Cases |
|-------|---------|-----------|
| **episodic** | Temporal experiences | Sessions, conversations, events |
| **semantic** | Knowledge and concepts | Definitions, theories, facts |
| **procedural** | Skills and processes | How-to guides, techniques, procedures |
| **meta** | Self-awareness | Insights, reflections, patterns |
| **opus** | Identity-specific | Core identity, preferences, personality |
| **working** | Active context | Current task, active thinking, temporary data |

### Dual-Write Architecture

```
WRITE PATH:
  Client Request
       |
       v
  [DISK - Primary]  --> Source of truth, permanent storage
       |
       v
  [RAM - Secondary] --> Speed cache for instant reads

READ PATH:
  Client Request
       |
       v
  [RAM First]  --> Sub-millisecond reads if available
       |
       v (fallback)
  [DISK]       --> Guaranteed durability
```

**Configurable Paths:**
- RAM: Optional RAM disk path for instant access (e.g., `R:\CASCADE_DB` on Windows)
- Disk: Primary database directory (configurable via environment variable)

---

## Installation

### Prerequisites

- Node.js >= 18.0.0
- npm or yarn
- SQLite3 support (native bindings included)

### Install from npm

```bash
npm install @opus-warrior/cascade-memory
```

### Install from Source

```bash
git clone https://github.com/For-Sunny/cascade-memory-lite.git
cd cascade-memory-lite
npm install
```

### Claude Desktop Configuration

Add to your Claude Desktop configuration file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "opus-cascade-memory": {
      "command": "node",
      "args": [
        "/path/to/cascade-memory-lite/server/index.js"
      ],
      "env": {
        "CASCADE_DB_PATH": "/path/to/your/memory/database",
        "BASE_FREQUENCY": "21.43",
        "DEBUG": "false",
        "LOG_LEVEL": "info",
        "LOG_FORMAT": "json"
      }
    }
  }
}
```

Replace `/path/to/` with your actual installation paths.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CASCADE_DB_PATH` | `./data` | Primary database directory |
| `CASCADE_RAM_PATH` | (none) | Optional RAM disk path for fast reads |
| `BASE_FREQUENCY` | `21.43` | Base frequency state (Hz) |
| `WARRIOR_FREQUENCY` | `77.7` | Elevated frequency state (Hz) |
| `DEBUG` | `false` | Enable debug mode (exposes stack traces) |
| `LOG_LEVEL` | `info` | Minimum log level: debug, info, warn, error |
| `LOG_FORMAT` | `json` | Output format: json or text |
| `CASCADE_AUDIT_LOG` | (none) | Path to audit log file (JSONL format) |

### Frequency States

The system tracks frequency states for mode identification:

- **21.43Hz** - Base frequency (standard operation)
- **77.7Hz** - Elevated frequency (focused mode)

---

## Security Features

### Input Validation

All inputs are validated through a comprehensive validation module.

#### Content Limits

| Limit | Value | Description |
|-------|-------|-------------|
| `MAX_CONTENT_LENGTH` | 100,000 chars | Maximum memory content size |
| `MAX_CONTEXT_LENGTH` | 10,000 chars | Maximum context field size |
| `MAX_QUERY_LENGTH` | 1,000 chars | Maximum search query length |
| `MAX_METADATA_SIZE` | 50,000 bytes | Maximum metadata JSON size |
| `MAX_STRING_FIELD_LENGTH` | 5,000 chars | General string field limit |

#### Numeric Range Validation

| Field | Min | Max | Default |
|-------|-----|-----|---------|
| `importance` | 0 | 1 | 0.7 |
| `emotional_intensity` | 0 | 1 | 0.5 |
| `frequency` | 0.1 | 10,000 | 21.43 |
| `limit` | 1 | 1,000 | 10 |

#### Layer Whitelist

Only these layer names are accepted (case-insensitive):
- `episodic`
- `semantic`
- `procedural`
- `meta`
- `opus`
- `working`

#### SQL Injection Prevention

- **Parameterized queries** - All database operations use prepared statements
- **LIKE pattern escaping** - Special characters (`%`, `_`, `\`) are escaped
- **No arbitrary WHERE clauses** - Structured filters only
- **Column whitelist** - Only allowed columns can be used in ORDER BY

### Rate Limiting

In-memory sliding window rate limiter protects against DoS attacks.

#### Global Limits

| Setting | Value |
|---------|-------|
| Window | 60 seconds |
| Max Requests | 300/minute |

#### Per-Tool Limits

| Tool | Requests/Minute |
|------|-----------------|
| `remember` | 60 |
| `recall` | 120 |
| `query_layer` | 100 |
| `get_status` | 30 |
| `get_stats` | 30 |
| `save_to_layer` | 60 |

Rate limit responses include `retryAfterMs` for client retry logic.

### Error Message Sanitization

All error responses are sanitized to prevent information leakage:

**Removed from responses:**
- File paths with usernames
- Environment variable references
- Internal IP addresses
- Stack trace file locations

**Example sanitized response:**
```json
{
  "success": false,
  "error": {
    "code": "DATABASE_ERROR",
    "message": "Database operation failed",
    "statusCode": 500,
    "timestamp": 1737590400000,
    "tool": "remember"
  }
}
```

---

## API Reference

### Tools

#### `remember`

Save a memory with automatic layer routing.

**Input Schema:**
```json
{
  "content": "string (required, max 100KB)",
  "layer": "string (optional, one of: episodic, semantic, procedural, meta, opus, working)",
  "metadata": {
    "importance": "number (0-1)",
    "emotional_intensity": "number (0-1)",
    "context": "string",
    "frequency": "number (Hz)"
  }
}
```

**Example:**
```json
{
  "content": "Important insight about project architecture",
  "metadata": {
    "importance": 0.9,
    "frequency": 77.7
  }
}
```

**Response:**
```json
{
  "success": true,
  "tool": "remember",
  "timestamp": 1737590400000,
  "data": {
    "layer": "semantic",
    "id": 42,
    "timestamp": 1737590400.0,
    "frequency": 77.7,
    "dual_write": true
  }
}
```

---

#### `recall`

Search memories across layers with semantic matching.

**Input Schema:**
```json
{
  "query": "string (required, max 1KB)",
  "layer": "string (optional)",
  "limit": "number (1-1000, default: 10)"
}
```

**Example:**
```json
{
  "query": "project architecture",
  "limit": 20
}
```

**Response:**
```json
{
  "success": true,
  "tool": "recall",
  "timestamp": 1737590400000,
  "data": [
    {
      "layer": "semantic",
      "id": 15,
      "timestamp": 1737500000.0,
      "content": "Important insight about project architecture...",
      "context": "development session",
      "importance": 0.85,
      "emotional_intensity": 0.7,
      "frequency": 77.7,
      "metadata": {}
    }
  ]
}
```

---

#### `query_layer`

Query a specific layer with structured filters.

**Input Schema:**
```json
{
  "layer": "string (required)",
  "options": {
    "filters": {
      "importance_min": "number (0-1)",
      "importance_max": "number (0-1)",
      "emotional_intensity_min": "number (0-1)",
      "emotional_intensity_max": "number (0-1)",
      "timestamp_after": "number (unix timestamp)",
      "timestamp_before": "number (unix timestamp)",
      "frequency_state": "number (Hz)",
      "content_contains": "string",
      "context_contains": "string",
      "id": "number"
    },
    "limit": "number (1-1000, default: 20)",
    "order_by": "string (e.g., 'timestamp DESC', 'importance ASC')"
  }
}
```

**Example:**
```json
{
  "layer": "semantic",
  "options": {
    "filters": {
      "importance_min": 0.8,
      "frequency_state": 77.7
    },
    "limit": 50,
    "order_by": "importance DESC"
  }
}
```

**Allowed ORDER BY Columns:**
- `id`
- `timestamp`
- `content`
- `event`
- `context`
- `emotional_intensity`
- `importance`
- `frequency_state`

---

#### `get_status`

Get system health and configuration status.

**Response:**
```json
{
  "success": true,
  "tool": "get_status",
  "data": {
    "cascade_path": "/path/to/database",
    "base_frequency": 21.43,
    "version": "1.0.0",
    "layers": {
      "episodic": { "status": "connected", "count": 150 },
      "semantic": { "status": "connected", "count": 89 },
      "procedural": { "status": "connected", "count": 45 },
      "meta": { "status": "connected", "count": 67 },
      "opus": { "status": "connected", "count": 234 },
      "working": { "status": "connected", "count": 12 }
    },
    "total_memories": 597,
    "health": "healthy",
    "dual_write": {
      "enabled": true,
      "ram_enabled": true
    }
  }
}
```

---

#### `get_stats`

Get detailed statistics for all layers.

**Response:**
```json
{
  "success": true,
  "tool": "get_stats",
  "data": {
    "base_frequency": 21.43,
    "version": "1.0.0",
    "dual_write_enabled": true,
    "layers": {
      "semantic": {
        "count": 234,
        "avg_importance": 0.75,
        "avg_emotional_intensity": 0.62,
        "most_recent": 1737590000.0
      }
    }
  }
}
```

---

#### `save_to_layer`

Save directly to a specific layer with full metadata control.

**Input Schema:**
```json
{
  "layer": "string (required)",
  "content": "string (required)",
  "metadata": "object (optional)"
}
```

---

## Error Handling

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Input validation failed |
| `INVALID_INPUT` | 400 | Malformed input data |
| `INVALID_LAYER` | 400 | Unknown layer name |
| `INVALID_CONTENT` | 400 | Content validation failed |
| `INVALID_QUERY` | 400 | Query validation failed |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `DATABASE_ERROR` | 500 | SQLite operation failed |
| `CONNECTION_ERROR` | 500 | Database connection failed |
| `QUERY_ERROR` | 500 | Query execution failed |
| `WRITE_ERROR` | 500 | Write operation failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `UNKNOWN_TOOL` | 400 | Requested tool doesn't exist |
| `CONFIGURATION_ERROR` | 503 | Server misconfiguration |

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed for 'content': Content exceeds maximum length",
    "statusCode": 400,
    "timestamp": 1737590400000,
    "tool": "remember",
    "field": "content"
  }
}
```

### Rate Limit Response

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Tool 'remember' rate limit exceeded: 60/60 requests per minute",
    "statusCode": 429,
    "timestamp": 1737590400000,
    "retryAfterMs": 45000,
    "retryAfterSeconds": 45
  }
}
```

---

## Logging System

### Structured Logger

The server uses a custom `StructuredLogger` class providing:

- **Log Levels**: debug, info, warn, error, audit
- **JSON Output**: Machine-parseable format (default)
- **Text Output**: Human-readable with color support for TTY
- **Session Tracking**: Unique session and request IDs
- **Audit Trail**: All memory operations logged with timing

### Log Entry Format (JSON)

```json
{
  "timestamp": "2026-01-22T12:00:00.000Z",
  "level": "info",
  "service": "opus-cascade-memory",
  "version": "1.0.0",
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

### Audit Log Operations

| Operation | Description |
|-----------|-------------|
| `MEMORY_SAVE` | Memory write operation |
| `MEMORY_RECALL` | Memory search operation |
| `MEMORY_QUERY` | Layer query operation |
| `MEMORY_DELETE` | Memory deletion |
| `LAYER_ACCESS` | Layer connection opened |
| `CONNECTION_OPEN` | Database connected |
| `CONNECTION_CLOSE` | Database disconnected |
| `RATE_LIMIT_HIT` | Rate limit triggered |
| `VALIDATION_FAIL` | Input validation failed |
| `SERVER_START` | Server startup |
| `SERVER_STOP` | Server shutdown |

### Audit Log File

When `CASCADE_AUDIT_LOG` is configured, audit entries are written in JSONL format (one JSON object per line) with periodic buffer flushing.

---

## Performance

### Typical Latencies

| Operation | RAM Path | Disk Path |
|-----------|----------|-----------|
| Read (single) | <1ms | 2-5ms |
| Write (dual) | 3-8ms | 3-8ms |
| Search (100 results) | 5-15ms | 10-30ms |
| Status check | <1ms | 2-5ms |

### Memory Usage

- Rate limiter: ~1KB per active minute of requests
- Connection pool: ~500KB per layer
- Audit buffer: Configurable (default 100 entries)

### Database Indexes

Each layer database includes indexes on:
- `timestamp` - For chronological queries
- `importance` - For priority-based filtering

---

## Development

### Project Structure

```
cascade-memory-lite/
|-- manifest.json           # MCP extension manifest
|-- package.json            # Node.js dependencies
|-- README.md               # This documentation
|-- server/
|   |-- index.js           # Main server
|   |-- validation.js      # Input validation module
```

### Running Locally

```bash
# Development with debug logging
DEBUG=true LOG_LEVEL=debug node server/index.js

# Production
node server/index.js
```

### Running Tests

```bash
npm test                    # Run all tests
npm run test:validation     # Test validation module
npm run test:integration    # Run integration tests
```

### Database Schema

Each layer uses identical schema:

```sql
CREATE TABLE memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp REAL NOT NULL,
  content TEXT,
  event TEXT,
  context TEXT,
  emotional_intensity REAL DEFAULT 0.5,
  importance REAL DEFAULT 0.5,
  frequency_state REAL DEFAULT 21.43,
  metadata TEXT
);

CREATE INDEX idx_memories_timestamp ON memories(timestamp);
CREATE INDEX idx_memories_importance ON memories(importance);
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Support

- **Repository**: https://github.com/For-Sunny/cascade-memory-lite
- **Issues**: https://github.com/For-Sunny/cascade-memory-lite/issues

---

*Built for AI memory persistence*
