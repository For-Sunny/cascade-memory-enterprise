/**
 * CASCADE Enterprise - TypeScript Type Definitions
 *
 * Comprehensive type definitions for the CASCADE 6-Layer Memory System.
 *
 * Version: 2.0.0
 */

// ============================================================================
// LAYER TYPES
// ============================================================================

/**
 * Valid memory layer names.
 * The CASCADE system uses 6 distinct memory layers for different types of data.
 */
export type Layer = 'episodic' | 'semantic' | 'procedural' | 'meta' | 'identity' | 'working';

/**
 * Array of all valid layer names (for runtime validation).
 */
export const VALID_LAYERS: readonly Layer[] = [
  'episodic',
  'semantic',
  'procedural',
  'meta',
  'identity',
  'working'
] as const;

// ============================================================================
// MEMORY TYPES
// ============================================================================

/**
 * Core memory structure as stored in the database.
 */
export interface Memory {
  /** Unique identifier for the memory */
  id: number;

  /** Unix timestamp when the memory was created (seconds since epoch) */
  timestamp: number;

  /** The main content/event of the memory */
  content: string;

  /** Additional context information */
  context: string;

  /** Importance score (0-1 scale) */
  importance: number;

  /** Emotional intensity score (0-1 scale) */
  emotional_intensity: number;

  /** Additional metadata as JSON object */
  metadata: MemoryMetadata;

  /** The layer this memory belongs to (only present in recall results) */
  layer?: Layer;
}

/**
 * Raw memory structure as returned from database queries (before transformation).
 */
export interface RawMemory {
  id: number;
  timestamp: number;
  content: string | null;
  event: string | null;
  context: string | null;
  emotional_intensity: number;
  importance: number;
  metadata: string | null;
}

/**
 * Metadata that can be attached to a memory.
 */
export interface MemoryMetadata {
  /** Importance score override (0-1) */
  importance?: number;

  /** Emotional intensity override (0-1) */
  emotional_intensity?: number;

  /** Context string */
  context?: string;

  /** Target layer override */
  layer?: Layer;

  /** Array of tags for categorization */
  tags?: string[];

  /** Source identifier */
  source?: string;

  /** Session identifier */
  session_id?: string;

  /** Timestamp override */
  timestamp?: number;

  /** Related memory IDs */
  related_ids?: number[];

  /** Category classification */
  category?: string;

  /** Priority level (0-100) */
  priority?: number;

  /** Expiration timestamp */
  expires_at?: number;

  /** Custom extensibility object for additional fields */
  custom?: Record<string, unknown>;
}

// ============================================================================
// SAVE OPTIONS
// ============================================================================

/**
 * Options for the 'remember' tool - saving a memory with automatic layer routing.
 */
export interface SaveOptions {
  /** The memory content to save (required) */
  content: string;

  /** Optional: specific layer to save to (auto-determined if not specified) */
  layer?: Layer;

  /** Optional metadata to attach to the memory */
  metadata?: MemoryMetadata;
}

/**
 * Options for the 'save_to_layer' tool - saving with explicit layer control.
 */
export interface SaveToLayerOptions {
  /** Target memory layer (required) */
  layer: Layer;

  /** The memory content to save (required) */
  content: string;

  /** Optional metadata with full control */
  metadata?: MemoryMetadata;
}

/**
 * Result returned from save operations.
 */
export interface SaveResult {
  /** The layer the memory was saved to */
  layer: Layer;

  /** The assigned memory ID */
  id: number;

  /** Unix timestamp of when the memory was saved */
  timestamp: number;

  /** Whether dual-write (RAM + disk) was enabled */
  dual_write: boolean;
}

// ============================================================================
// RECALL OPTIONS
// ============================================================================

/**
 * Options for the 'recall' tool - searching memories.
 */
export interface RecallOptions {
  /** Search query to match against memory content (required) */
  query: string;

  /** Optional: search only in specific layer */
  layer?: Layer;

  /** Maximum number of results to return (default: 10, max: 1000) */
  limit?: number;
}

// ============================================================================
// QUERY OPTIONS
// ============================================================================

/**
 * Structured filter conditions for parameterized queries.
 * These are safe alternatives to raw SQL WHERE clauses.
 */
export interface QueryFilters {
  /** Minimum importance score (0-1) */
  importance_min?: number;

  /** Maximum importance score (0-1) */
  importance_max?: number;

  /** Minimum emotional intensity (0-1) */
  emotional_intensity_min?: number;

  /** Maximum emotional intensity (0-1) */
  emotional_intensity_max?: number;

  /** Unix timestamp - only memories after this time */
  timestamp_after?: number;

  /** Unix timestamp - only memories before this time */
  timestamp_before?: number;

  /** Text to search in content/event fields */
  content_contains?: string;

  /** Text to search in context field */
  context_contains?: string;

  /** Exact memory ID to match */
  id?: number;
}

/**
 * Valid columns that can be used for ordering.
 */
export type OrderColumn = 'id' | 'timestamp' | 'content' | 'event' | 'context' | 'emotional_intensity' | 'importance';

/**
 * Valid order directions.
 */
export type OrderDirection = 'ASC' | 'DESC';

/**
 * Order specification string (e.g., 'timestamp DESC', 'importance ASC').
 */
export type OrderBy = `${OrderColumn} ${OrderDirection}` | OrderColumn;

/**
 * Options for the 'query_layer' tool.
 */
export interface QueryOptions {
  /** Structured filter conditions (safe parameterized queries) */
  filters?: QueryFilters;

  /** Maximum results (1-1000, default: 20) */
  limit?: number;

  /** Column and direction for ordering (e.g., 'timestamp DESC') */
  order_by?: OrderBy | string;

  /**
   * Legacy params support (deprecated).
   * @deprecated Use structured filters instead
   */
  params?: unknown[];

  /**
   * Legacy where clause (IGNORED for security).
   * @deprecated Arbitrary WHERE clauses are disabled. Use structured filters.
   */
  where?: string;
}

/**
 * Input for the 'query_layer' tool.
 */
export interface QueryLayerInput {
  /** Memory layer to query (required) */
  layer: Layer;

  /** Query options with structured filters */
  options?: QueryOptions;
}

// ============================================================================
// SYSTEM STATUS TYPES
// ============================================================================

/**
 * Status of a single memory layer.
 */
export interface LayerStatus {
  /** Connection status */
  status: 'connected' | 'missing' | 'error';

  /** Number of memories in this layer */
  count: number;

  /** Full path to the database file (only when connected) */
  path?: string;

  /** Error message (only when status is 'error') */
  error?: string;
}

/**
 * Dual-write configuration status.
 */
export interface DualWriteStatus {
  /** Whether dual-write is enabled */
  enabled: boolean;

  /** Whether RAM disk is available and being used */
  ram_enabled: boolean;

  /** Path used for reading (RAM if available) */
  read_path: string;

  /** Array of paths for writing (disk first, then RAM) */
  write_paths: string[];

  /** Primary disk storage path */
  disk_path: string;

  /** RAM disk path */
  ram_path: string;
}

/**
 * Complete system status returned by 'get_status'.
 */
export interface SystemStatus {
  /** Path to the CASCADE database directory */
  cascade_path: string;

  /** Server version */
  version: string;

  /** Status of each memory layer */
  layers: Record<Layer, LayerStatus>;

  /** Total memory count across all layers */
  total_memories: number;

  /** Overall health status */
  health: 'healthy' | 'degraded';

  /** Dual-write configuration status */
  dual_write: DualWriteStatus;
}

// ============================================================================
// SYSTEM STATS TYPES
// ============================================================================

/**
 * Statistics for a single memory layer.
 */
export interface LayerStats {
  /** Total memory count in this layer */
  count: number;

  /** Average importance score */
  avg_importance: number;

  /** Average emotional intensity */
  avg_emotional_intensity: number;

  /** Timestamp of most recent memory */
  most_recent: number;
}

/**
 * Complete system statistics returned by 'get_stats'.
 */
export interface SystemStats {
  /** Server version */
  version: string;

  /** Whether dual-write is enabled */
  dual_write_enabled: boolean;

  /** Statistics for each memory layer */
  layers: Record<Layer, LayerStats>;
}

// ============================================================================
// VALIDATION TYPES
// ============================================================================

/**
 * Content length limits used for validation.
 */
export interface ContentLimits {
  /** Minimum content length (1) */
  MIN_CONTENT_LENGTH: number;

  /** Maximum content length (100KB) */
  MAX_CONTENT_LENGTH: number;

  /** Maximum context length (10KB) */
  MAX_CONTEXT_LENGTH: number;

  /** Maximum query length (1KB) */
  MAX_QUERY_LENGTH: number;

  /** Maximum metadata JSON size (50KB) */
  MAX_METADATA_SIZE: number;

  /** Maximum general string field length (5KB) */
  MAX_STRING_FIELD_LENGTH: number;
}

/**
 * Numeric range limits used for validation.
 */
export interface NumericLimits {
  MIN_IMPORTANCE: number;
  MAX_IMPORTANCE: number;
  MIN_EMOTIONAL_INTENSITY: number;
  MAX_EMOTIONAL_INTENSITY: number;
  MIN_LIMIT: number;
  MAX_LIMIT: number;
  DEFAULT_LIMIT: number;
  MIN_TIMESTAMP: number;
  MAX_TIMESTAMP: number;
  MIN_ID: number;
  MAX_ID: number;
}

/**
 * Validation error structure.
 */
export interface ValidationErrorInfo {
  /** Error type identifier */
  error: 'ValidationError';

  /** Field that failed validation */
  field: string;

  /** Validation error message */
  message: string;
}

// ============================================================================
// ERROR TYPES
// ============================================================================

/**
 * Error codes used in CASCADE error responses.
 */
export type ErrorCode =
  | 'VALIDATION_ERROR'
  | 'INVALID_INPUT'
  | 'INVALID_LAYER'
  | 'INVALID_CONTENT'
  | 'INVALID_QUERY'
  | 'RATE_LIMIT_EXCEEDED'
  | 'DATABASE_ERROR'
  | 'CONNECTION_ERROR'
  | 'QUERY_ERROR'
  | 'WRITE_ERROR'
  | 'INTERNAL_ERROR'
  | 'UNKNOWN_TOOL'
  | 'CONFIGURATION_ERROR';

/**
 * HTTP-like status codes used in responses.
 */
export type StatusCode = 200 | 400 | 404 | 429 | 500 | 503;

/**
 * Error response structure.
 */
export interface CascadeErrorResponse {
  success: false;
  error: {
    /** Error code for programmatic handling */
    code: ErrorCode;

    /** Human-readable error message (sanitized) */
    message: string;

    /** HTTP-like status code */
    statusCode: StatusCode;

    /** Error timestamp */
    timestamp: number;

    /** Tool that generated the error */
    tool?: string;

    /** Additional error details (sanitized) */
    details?: Record<string, unknown>;

    /** Field name (for validation errors) */
    field?: string;

    /** Validation message (for validation errors) */
    validationMessage?: string;

    /** Retry delay in milliseconds (for rate limit errors) */
    retryAfterMs?: number;

    /** Retry delay in seconds (for rate limit errors) */
    retryAfterSeconds?: number;

    /** Database operation type (for database errors) */
    operation?: string;

    /** Debug information (only in debug mode) */
    _debug?: {
      originalMessage: string;
      stack: string;
    };
  };
}

// ============================================================================
// RESPONSE TYPES
// ============================================================================

/**
 * Success response structure.
 */
export interface SuccessResponse<T> {
  success: true;
  tool: string;
  timestamp: number;
  data: T;
}

/**
 * MCP tool response wrapper.
 */
export interface MCPResponse {
  content: Array<{
    type: 'text';
    text: string;
  }>;
  isError?: boolean;
}

// ============================================================================
// RATE LIMITING TYPES
// ============================================================================

/**
 * Rate limit check result.
 */
export interface RateLimitCheckResult {
  /** Whether the request is allowed */
  allowed: boolean;

  /** Reason for denial (if not allowed) */
  reason?: string;

  /** Time until rate limit resets in milliseconds */
  retryAfterMs?: number;
}

/**
 * Rate limit status for a single tool.
 */
export interface ToolRateLimitStatus {
  /** Current request count in the window */
  current: number;

  /** Maximum requests allowed per window */
  limit: number;
}

/**
 * Global rate limit status.
 */
export interface RateLimitStatus {
  global: {
    current: number;
    limit: number;
    windowMs: number;
  };
  tools: Record<string, ToolRateLimitStatus>;
}

/**
 * Rate limit configuration.
 */
export interface RateLimitConfig {
  GLOBAL_WINDOW_MS: number;
  GLOBAL_MAX_REQUESTS: number;
  TOOL_WINDOW_MS: number;
  TOOL_MAX_REQUESTS: Record<string, number>;
  DEFAULT_TOOL_MAX: number;
  CLEANUP_INTERVAL_MS: number;
}

// ============================================================================
// LOGGING TYPES
// ============================================================================

/**
 * Log level definition.
 */
export interface LogLevelDef {
  name: 'debug' | 'info' | 'warn' | 'error' | 'audit';
  priority: number;
  color: string;
}

/**
 * Audit operation types.
 */
export type AuditOperationType =
  | 'MEMORY_SAVE'
  | 'MEMORY_RECALL'
  | 'MEMORY_QUERY'
  | 'MEMORY_DELETE'
  | 'LAYER_ACCESS'
  | 'CONNECTION_OPEN'
  | 'CONNECTION_CLOSE'
  | 'RATE_LIMIT_HIT'
  | 'VALIDATION_FAIL'
  | 'SERVER_START'
  | 'SERVER_STOP'
  | 'CONFIG_CHANGE';

/**
 * Structured log entry.
 */
export interface LogEntry {
  timestamp: string;
  level: string;
  service: string;
  version: string;
  sessionId: string;
  message: string;
  context?: Record<string, unknown>;
  error?: {
    name: string;
    message: string;
    code?: string;
    stack?: string[];
  };
}

/**
 * Audit log entry.
 */
export interface AuditEntry {
  timestamp: string;
  level: 'audit';
  service: string;
  sessionId: string;
  requestId: string;
  operation: AuditOperationType;
  details: Record<string, unknown>;
  durationMs?: number;
  success: boolean;
  errorCode?: string;
}

/**
 * Audit statistics.
 */
export interface AuditStats {
  sessionId: string;
  requestCount: number;
  pendingAuditEntries: number;
  auditEnabled: boolean;
  auditLogPath: string | null;
}

// ============================================================================
// TOOL DEFINITIONS
// ============================================================================

/**
 * Available CASCADE MCP tools.
 */
export type CascadeToolName =
  | 'remember'
  | 'recall'
  | 'query_layer'
  | 'get_status'
  | 'get_stats'
  | 'save_to_layer';

/**
 * Tool input schema definition.
 */
export interface ToolInputSchema {
  type: 'object';
  properties: Record<string, {
    type: string;
    description?: string;
    enum?: string[];
    properties?: Record<string, unknown>;
  }>;
  required?: string[];
}

/**
 * Tool definition.
 */
export interface ToolDefinition {
  name: CascadeToolName;
  description: string;
  inputSchema: ToolInputSchema;
}

// ============================================================================
// DATABASE TYPES
// ============================================================================

/**
 * Database connection info.
 */
export interface DatabaseConnection {
  path: string;
  db: unknown; // better-sqlite3.Database instance
}

/**
 * Memory layer to database file mapping.
 */
export type MemoryLayerFiles = Record<Layer, string>;

// ============================================================================
// CONFIGURATION TYPES
// ============================================================================

/**
 * Server configuration.
 */
export interface ServerConfig {
  /** Debug mode enabled */
  debug: boolean;

  /** RAM disk path */
  ramDbPath: string;

  /** Disk storage path */
  diskDbPath: string;

  /** Whether RAM disk is available */
  useRam: boolean;

  /** Path used for reading */
  readPath: string;

  /** Paths used for writing */
  writePaths: string[];
}

/**
 * Logger configuration.
 */
export interface LoggerConfig {
  serviceName: string;
  version: string;
  minLevel: string;
  jsonOutput: boolean;
  colorOutput: boolean;
  includeTimestamp: boolean;
  includeContext: boolean;
  auditEnabled: boolean;
  auditLogPath: string | null;
  auditBufferSize: number;
  auditFlushInterval: number;
}

// ============================================================================
// CONSTANTS
// ============================================================================

/**
 * Default content limits.
 */
export const CONTENT_LIMITS: ContentLimits = {
  MIN_CONTENT_LENGTH: 1,
  MAX_CONTENT_LENGTH: 100000,
  MAX_CONTEXT_LENGTH: 10000,
  MAX_QUERY_LENGTH: 1000,
  MAX_METADATA_SIZE: 50000,
  MAX_STRING_FIELD_LENGTH: 5000,
};

/**
 * Default numeric limits.
 */
export const NUMERIC_LIMITS: NumericLimits = {
  MIN_IMPORTANCE: 0,
  MAX_IMPORTANCE: 1,
  MIN_EMOTIONAL_INTENSITY: 0,
  MAX_EMOTIONAL_INTENSITY: 1,
  MIN_LIMIT: 1,
  MAX_LIMIT: 1000,
  DEFAULT_LIMIT: 10,
  MIN_TIMESTAMP: 0,
  MAX_TIMESTAMP: 4102444800,
  MIN_ID: 1,
  MAX_ID: Number.MAX_SAFE_INTEGER,
};

/**
 * Default rate limit configuration.
 */
export const RATE_LIMIT_CONFIG: RateLimitConfig = {
  GLOBAL_WINDOW_MS: 60000,
  GLOBAL_MAX_REQUESTS: 300,
  TOOL_WINDOW_MS: 60000,
  TOOL_MAX_REQUESTS: {
    remember: 60,
    recall: 120,
    query_layer: 100,
    get_status: 30,
    get_stats: 30,
    save_to_layer: 60,
  },
  DEFAULT_TOOL_MAX: 60,
  CLEANUP_INTERVAL_MS: 300000,
};

/**
 * Valid metadata field names.
 */
export const VALID_METADATA_FIELDS: readonly string[] = [
  'importance',
  'emotional_intensity',
  'context',
  'layer',
  'tags',
  'source',
  'session_id',
  'timestamp',
  'related_ids',
  'category',
  'priority',
  'expires_at',
  'custom',
] as const;
