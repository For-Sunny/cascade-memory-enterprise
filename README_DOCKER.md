# Deploying CASCADE Enterprise via Docker

Run **CASCADE Enterprise** as an isolated, containerized memory service. Production-ready deployment in one command.

## Prerequisites

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine
* `docker-compose` (included with Docker Desktop)

## Quick Start

1. **Build and Run:**
   ```bash
   docker-compose up -d --build
   ```

2. **Verify Running:**
   ```bash
   docker ps
   ```
   You should see `cascade-memory-enterprise` running.

3. **Check Logs:**
   ```bash
   docker logs cascade-memory-enterprise
   ```

## Persistence

Your memory database is persisted in the `./data` directory on your host machine.

* **Backup:** Copy `./data/cascade.db`
* **Restore:** Replace `./data/cascade.db` with your backup

## Integration

### MCP (StdIO)
CASCADE uses the MCP stdio protocol. The container keeps stdin open for communication with AI agents.

### Future: HTTP/SSE Support
*Coming in v2.1*: A built-in SSE adapter will allow remote access over HTTP (Port 3000), enabling integration with Claude Desktop, LangChain, and remote agents.

---
**C.I.P.S. Corp** | *Ship AI code with confidence.*
