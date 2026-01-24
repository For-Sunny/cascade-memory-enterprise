# Changelog

All notable changes to cascade-memory will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-23

### Changed
- Simplified to disk-only architecture for public release
- Streamlined database module to single-path writes
- Updated documentation to reflect disk-only performance

### Kept
- Full 6-layer memory architecture
- Enterprise security (input validation, SQL injection prevention, rate limiting)
- Structured logging with audit trail
- Error sanitization
- All MCP tools (remember, recall, query_layer, save_to_layer, get_status, get_stats)

## [1.4.0] - 2026-01-22

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

## [1.3.0] - 2026-01-20

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

## [1.2.0] - 2026-01-18

### Added
- Rate limiting per client connection
- Configurable rate limits via environment variables
- Rate limit headers in responses

### Changed
- High-frequency callers throttled gracefully
- Burst allowance for legitimate use patterns

## [1.1.0] - 2026-01-15

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

## [1.0.0] - 2025-12-01

### Added
- Initial release of cascade-memory MCP server
- 6-layer memory architecture (episodic, semantic, procedural, meta, identity, working)
- SQLite backend with sub-millisecond access
- `remember` tool for saving memories with automatic layer routing
- `recall` tool for semantic memory search
- `query_layer` tool for direct layer access
- `get_status` tool for system health
- `get_stats` tool for memory statistics
- `save_to_layer` tool for explicit layer targeting
- Temporal decay with importance scoring

### Technical
- MCP protocol compliance
- Async operation support
- Connection pooling for performance
