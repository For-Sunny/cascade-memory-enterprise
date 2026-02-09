# 🐳 Deploying CASCADE Enterprise via Docker

This guide allows you to run **CASCADE Enterprise RAM** as an isolated, containerized memory service. This is the preferred deployment method for production environments to ensure data persistence and environment stability.

## Prerequisites

*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine installed.
*   `docker-compose` (usually included with Docker Desktop).

## Build Notes

As of v2.1.0, the Docker build no longer requires native compilation tools (python3, make, g++). The switch from `sqlite3` to `better-sqlite3` means prebuilt binaries are used. Faster builds, smaller images, no platform-specific failures.

## Quick Start

1.  **Build and Run:**
    ```bash
    docker-compose up -d --build
    ```

2.  **Verify Running:**
    ```bash
    docker ps
    ```
    You should see `cascade-memory` running.

3.  **Check Logs:**
    ```bash
    docker logs cascade-memory
    ```

## Persistence

Your memory database is persisted in the `./data` directory on your host machine (mapped to `/data/cascade` inside the container). CASCADE uses 6 separate layer files for organized memory storage:
*   **Backup:** Copy the entire `./data` directory (contains `episodic_memory.db`, `semantic_memory.db`, `procedural_memory.db`, `meta_memory.db`, `identity_memory.db`, `working_memory.db`).
*   **Migration:** Replace the entire `./data` directory to restore a previous memory state.

## Integration

### Connecting via MCP (StdIO)
If running inside a larger Docker network (e.g., alongside an AI Agent container), you can communicate via standard input/output streams if orchestrated together.

### Future: HTTP/SSE Support
*Planned for a future release*: A built-in SSE (Server-Sent Events) adapter will allow you to connect to CASCADE over HTTP (Port 3000), making it accessible to Claude Desktop, LangChain, and remote agents securely.

## Decay Configuration

v2.2.0 adds temporal memory decay. Memories fade over time unless accessed or marked important. Configure via environment variables in `docker-compose.yml`:

```yaml
environment:
  - DECAY_ENABLED=true              # Enable/disable decay
  - DECAY_BASE_RATE=0.01            # Decay speed per day
  - DECAY_THRESHOLD=0.1             # Below this, memories are hidden
  - DECAY_IMMORTAL_THRESHOLD=0.9    # At or above this, memories never decay
  - DECAY_SWEEP_INTERVAL=60         # Minutes between sweeps
  - DECAY_SWEEP_BATCH_SIZE=1000     # Max memories per layer per sweep
```

All values shown are defaults. Omit any variable to use its default.

---
**C.I.P.S. Corp** | *Ship AI code with confidence.*
