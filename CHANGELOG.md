# Changelog

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

First commercial release. Persistent 6-layer memory for AI systems with sub-millisecond reads via RAM disk acceleration.

### Included

- 6-layer cognitive memory (episodic, semantic, procedural, meta, identity, working)
- Dual-write pattern: disk for truth, RAM for speed
- Cross-platform RAM disk manager (Windows, Linux, macOS)
- Enterprise security: input validation, SQL injection prevention, rate limiting
- Structured JSON logging with audit trail
- Automatic content-based layer routing
- Importance scoring for memory prioritization
- Full MCP tool suite: remember, recall, query_layer, save_to_layer, get_status, get_stats
- 90-day money-back guarantee

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
