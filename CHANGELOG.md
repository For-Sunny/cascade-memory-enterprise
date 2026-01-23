# Changelog

All notable changes to opus-cascade-memory will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-23

### Changed
- Simplified to disk-only architecture for public release
- Removed RAM disk infrastructure (available as paid upgrade)
- Streamlined database module to single-path writes
- Updated documentation to reflect disk-only performance

### Kept
- Full 6-layer memory architecture
- Enterprise security (input validation, SQL injection prevention, rate limiting)
- Structured logging with audit trail
- Error sanitization
- All MCP tools (remember, recall, query_layer, save_to_layer, get_status, get_stats)

## [2.4.0-HARDENED] - 2026-01-22

### Added
- Comprehensive security hardening across all endpoints
- Rate limiting with configurable thresholds per operation type
- Input validation with strict type checking and bounds enforcement
- Structured logging with rotation and retention policies
- Full test suite covering security, validation, and edge cases
- Request ID tracking for audit trails

### Changed
- All database operations now use parameterized queries exclusively
- Error responses sanitized to prevent information leakage
- Memory content validated before storage

### Security
- SQL injection prevention hardened
- Path traversal attacks blocked
- Memory exhaustion protection via content size limits
- Rate limiting prevents abuse

## [2.3.0] - 2026-01-20

### Added
- Comprehensive error handling across all MCP tools
- Graceful degradation when backends are unavailable
- Error categorization (transient vs permanent)

### Changed
- All exceptions now caught and logged with context
- Failed operations return structured error responses
- Database connection errors trigger automatic retry

### Fixed
- Unhandled exceptions no longer crash the server
- Partial failures in batch operations properly reported

## [2.2.0] - 2026-01-18

### Added
- Rate limiting per client connection
- Configurable rate limits via environment variables
- Rate limit headers in responses

### Changed
- High-frequency callers throttled gracefully
- Burst allowance for legitimate use patterns

## [2.1.0] - 2026-01-15

### Added
- Input validation for all MCP tool parameters
- Content length limits (configurable max size)
- Layer name validation against allowed values
- Metadata schema validation

### Changed
- Invalid inputs rejected with descriptive errors
- Query parameters sanitized before use

### Fixed
- Empty content strings no longer accepted
- Invalid layer names caught at input

## [2.0.0] - 2026-01-10

### Added
- Dual-write pattern: CASCADE + Faiss GPU synchronization
- Automatic backup on write operations
- Write verification with rollback on failure

### Changed
- **BREAKING**: `remember` now writes to both CASCADE and Faiss
- Memory operations return confirmation from both backends
- Increased reliability through redundancy

### Migration
- Existing memories automatically available (no migration needed)
- New writes propagate to both systems

## [1.0.0] - 2025-12-01

### Added
- Initial release of opus-cascade-memory MCP server
- 6-layer memory architecture (episodic, semantic, procedural, meta, opus, working)
- SQLite backend with sub-millisecond access
- `remember` tool for saving memories with automatic layer routing
- `recall` tool for semantic memory search
- `query_layer` tool for direct layer access
- `get_status` tool for system health
- `get_stats` tool for memory statistics
- `save_to_layer` tool for explicit layer targeting
- Temporal decay with importance scoring
- Frequency-based memory tagging (21.43Hz base, 77.7Hz warrior mode)

### Technical
- MCP protocol compliance
- Async operation support
- Connection pooling for performance
