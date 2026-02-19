# Changelog

## [2.2.2] - 2026-02-18

Documentation and configuration fixes applied during three-path verification.

### Fixed

- **server/tools.js**: `recallMemories` now orders results by `COALESCE(effective_importance, importance) DESC, timestamp DESC` instead of `timestamp DESC` alone — most important memories returned first, not just most recent
- **server/database.js**: `determineLayer` now classifies content containing 'victory', 'achievement', or 'milestone' as `episodic` (matching `content_analyzer.js` pattern behavior)
- **tests/index.test.js**: Updated `sanitizeErrorMessage` test group to match current whitelist implementation — tests now verify that file paths and IP addresses are blocked entirely (return `'An error occurred'`) rather than expecting inline `[REDACTED]` substitution from the old redact-then-pass-through design; added tests confirming safe patterns pass through
- **tests/index.test.js**, **tests/integration.test.js**: Updated hardcoded version assertions from `2.2.0` to `2.2.2`
- **examples/cascade_integration.py**: Added clarifying comment explaining that `cascade.db` is a generic demo SQLite filename; CASCADE's actual memory system uses 6 separate `{layer}_memory.db` files
- **server/index.js**, **server/tools.js**, **package.json**: Corrected version strings from `2.2.0` to `2.2.2` (version was not bumped when `2.2.1` changes were applied to CHANGELOG)
- **README.md**, **QUICKSTART.md**: Updated startup message example to match actual JSON log output
- **.env.example**: Added all 6 `DECAY_*` environment variables with defaults and descriptions
- **.gitattributes**: Created with LF enforcement for all text file types (`*.sh`, `*.ts`, `*.js`, `*.json`, `*.md`, `*.yml`, `*.py`); `*.db` marked as binary

---

## [2.2.1] - 2026-02-17

### Added

- Docker health check: `server/healthcheck.js` verifies SQLite database accessibility every 30s. Checks RAM path first, falls back to disk. Health check runs in both Dockerfile and docker-compose.yml with 10s start period and 3 retries.
- Performance benchmark documentation in README.md with methodology, hardware specs, and reproduction steps.

### Changed

- Dependency upper bounds added to prevent breaking changes from major version bumps:
  - `@modelcontextprotocol/sdk`: `>=1.0.4 <2.0.0` (was `^1.0.4`)
  - `better-sqlite3`: `>=11.7.0 <12.0.0` (was `^11.7.0`)
  - Node.js engine: `>=18.0.0 <25.0.0` (was `>=18.0.0`)
  - Python build deps: `setuptools>=61.0,<76.0`, `wheel>=0.37.0,<1.0.0`
  - All Python optional deps now have upper bounds (xxhash, pytest, black, mypy, etc.)

---

## [2.2.0] - 2026-02-09

### Added

- Temporal memory decay engine. Memories fade over time unless accessed or marked important.
- `DecayEngine` class with configurable sweep intervals and batch processing
- Memories with importance >= 0.9 are immortal (never decay)
- Schema migration adds `last_accessed`, `effective_importance`, `access_count` columns
- `recall` and `query_layer` filter decayed memories by default. Pass `include_decayed: true` to see all.
- Accessing a memory resets its decay clock
- 6 new environment variables for decay configuration (`DECAY_ENABLED`, `DECAY_BASE_RATE`, `DECAY_THRESHOLD`, `DECAY_IMMORTAL_THRESHOLD`, `DECAY_SWEEP_INTERVAL`, `DECAY_SWEEP_BATCH_SIZE`)
- `get_status` and `get_stats` now include decay information (immortal/active/decayed counts)
- 30 new decay-specific tests (all passing)

---

## [2.1.0] - 2026-02-07

### Changed

- Replaced `sqlite3` npm package with `better-sqlite3`. Resolves node-gyp build failures on ARM64 Windows (Snapdragon/Qualcomm). Prebuilt binaries now cover ARM64 Windows, x64 Windows, Linux, and macOS. No API changes.

### Fixed

- Installation on ARM64 Windows no longer requires native compilation toolchain (python3, make, g++)
- Eliminates transitive npm audit vulnerabilities from sqlite3 -> node-gyp -> tar dependency chain
- Docker image build no longer needs build-essential packages, reducing image size

---

## [2.0.0] - 2026-01-23

### Release: CASCADE Enterprise + RAM Disk

First release. Persistent 6-layer memory for AI systems with sub-millisecond reads via RAM disk acceleration.

### Included

- 6-layer cognitive memory (episodic, semantic, procedural, meta, identity, working)
- Dual-write pattern: disk for truth, RAM for speed
- Cross-platform RAM disk manager (Windows, Linux, macOS)
- Enterprise security: input validation, SQL injection prevention, rate limiting
- Structured JSON logging with audit trail
- Automatic content-based layer routing
- Importance scoring for memory prioritization
- Full MCP tool suite: remember, recall, query_layer, save_to_layer, get_status, get_stats
- MIT open-source license

### Performance

- <1ms reads from RAM
- 2-5ms disk fallback
- 3-8ms writes (dual-write)
- 5-15ms search across 100 results

---

## [1.0.0] - 2026-01-22

### Internal

- Initial architecture and security hardening
- Modular server split (database, tools, validation, content analyzer)
- Rate limiting and error sanitization
