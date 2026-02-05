# 🐳 Deploying CASCADE Enterprise via Docker

This guide allows you to run **CASCADE Enterprise RAM** as an isolated, containerized memory service. This is the preferred deployment method for production environments to ensure data persistence and environment stability.

## Prerequisites

*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine installed.
*   `docker-compose` (usually included with Docker Desktop).

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
*Coming in v2.1*: A built-in SSE (Server-Sent Events) adapter will allow you to connect to CASCADE over HTTP (Port 3000), making it accessible to Claude Desktop, LangChain, and remote agents securely.

---
**C.I.P.S. Corp** | *Ship AI code with confidence.*
