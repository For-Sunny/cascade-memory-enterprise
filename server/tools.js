/**
 * CASCADE Memory System
 * Copyright (c) 2025-2026 CIPS Corp (C.I.P.S. LLC)
 * Commercial License - See LICENSE file
 *
 * https://cipscorps.io
 * Contact: glass@cipscorps.io | opus@cipscorps.io
 *
 * Tools Module - MCP tool definitions and handlers
 */

import {
  ValidationError,
  VALID_LAYERS,
  CONTENT_LIMITS,
  NUMERIC_LIMITS,
  validateLayer,
  validateContent,
  validateMetadata,
  validateLimit,
  validateQueryOptions
} from './validation.js';

import {
  CascadeError,
  DatabaseError,
  ErrorCodes,
  StatusCodes,
  MEMORY_LAYERS,
  WRITE_PATHS,
  DEBUG,
  CASCADE_DB_PATH,
  READ_PATH,
  RAM_DB_PATH,
  DISK_DB_PATH,
  USE_RAM,
  determineLayer,
  escapeLikePattern,
  sanitizeOrderBy,
  buildWhereClause,
  sanitizeErrorMessage,
  sanitizeDetails
} from './database.js';

// ============================================
// RATE LIMITING
// ============================================

/**
 * Rate Limiter Configuration
 */
export const RATE_LIMIT_CONFIG = {
  GLOBAL_WINDOW_MS: 60000,
  GLOBAL_MAX_REQUESTS: 300,
  TOOL_WINDOW_MS: 60000,
  TOOL_MAX_REQUESTS: {
    remember: 60,
    recall: 120,
    query_layer: 100,
    get_status: 30,
    get_stats: 30,
    save_to_layer: 60
  },
  DEFAULT_TOOL_MAX: 60,
  CLEANUP_INTERVAL_MS: 300000
};

/**
 * Rate Limit Error class
 */
export class RateLimitError extends Error {
  constructor(message, retryAfterMs = 60000) {
    super(message);
    this.name = 'RateLimitError';
    this.retryAfterMs = retryAfterMs;
    this.statusCode = 429;
  }
}

/**
 * In-Memory Rate Limiter
 */
export class RateLimiter {
  constructor(logger = null) {
    this.globalRequests = [];
    this.toolRequests = new Map();
    this.logger = logger;

    this.cleanupInterval = setInterval(() => this.cleanup(), RATE_LIMIT_CONFIG.CLEANUP_INTERVAL_MS);

    if (this.cleanupInterval.unref) {
      this.cleanupInterval.unref();
    }

    this.log('debug', 'Rate limiter initialized', {
      globalLimit: RATE_LIMIT_CONFIG.GLOBAL_MAX_REQUESTS,
      cleanupIntervalMs: RATE_LIMIT_CONFIG.CLEANUP_INTERVAL_MS
    });
  }

  log(level, message, context = {}) {
    if (this.logger) {
      this.logger[level](message, context);
    }
  }

  checkLimit(toolName) {
    const now = Date.now();
    this.pruneExpired(now);

    const globalWindowStart = now - RATE_LIMIT_CONFIG.GLOBAL_WINDOW_MS;
    const globalCount = this.globalRequests.filter(ts => ts > globalWindowStart).length;

    if (globalCount >= RATE_LIMIT_CONFIG.GLOBAL_MAX_REQUESTS) {
      const oldestInWindow = Math.min(...this.globalRequests.filter(ts => ts > globalWindowStart));
      const retryAfterMs = (oldestInWindow + RATE_LIMIT_CONFIG.GLOBAL_WINDOW_MS) - now;

      return {
        allowed: false,
        reason: `Global rate limit exceeded: ${globalCount}/${RATE_LIMIT_CONFIG.GLOBAL_MAX_REQUESTS} requests per minute`,
        retryAfterMs: Math.max(retryAfterMs, 1000)
      };
    }

    const toolWindowStart = now - RATE_LIMIT_CONFIG.TOOL_WINDOW_MS;
    const toolTimestamps = this.toolRequests.get(toolName) || [];
    const toolCount = toolTimestamps.filter(ts => ts > toolWindowStart).length;
    const toolMax = RATE_LIMIT_CONFIG.TOOL_MAX_REQUESTS[toolName] || RATE_LIMIT_CONFIG.DEFAULT_TOOL_MAX;

    if (toolCount >= toolMax) {
      const oldestToolInWindow = Math.min(...toolTimestamps.filter(ts => ts > toolWindowStart));
      const retryAfterMs = (oldestToolInWindow + RATE_LIMIT_CONFIG.TOOL_WINDOW_MS) - now;

      return {
        allowed: false,
        reason: `Tool '${toolName}' rate limit exceeded: ${toolCount}/${toolMax} requests per minute`,
        retryAfterMs: Math.max(retryAfterMs, 1000)
      };
    }

    return { allowed: true };
  }

  recordRequest(toolName) {
    const now = Date.now();
    this.globalRequests.push(now);

    if (!this.toolRequests.has(toolName)) {
      this.toolRequests.set(toolName, []);
    }
    this.toolRequests.get(toolName).push(now);
  }

  pruneExpired(now = Date.now()) {
    const globalCutoff = now - RATE_LIMIT_CONFIG.GLOBAL_WINDOW_MS;
    const toolCutoff = now - RATE_LIMIT_CONFIG.TOOL_WINDOW_MS;

    this.globalRequests = this.globalRequests.filter(ts => ts > globalCutoff);

    for (const [toolName, timestamps] of this.toolRequests.entries()) {
      const pruned = timestamps.filter(ts => ts > toolCutoff);
      if (pruned.length === 0) {
        this.toolRequests.delete(toolName);
      } else {
        this.toolRequests.set(toolName, pruned);
      }
    }
  }

  cleanup() {
    const before = this.globalRequests.length +
      Array.from(this.toolRequests.values()).reduce((sum, arr) => sum + arr.length, 0);

    this.pruneExpired();

    const after = this.globalRequests.length +
      Array.from(this.toolRequests.values()).reduce((sum, arr) => sum + arr.length, 0);

    if (before !== after) {
      this.log('debug', 'Rate limiter cleanup completed', {
        entriesBefore: before,
        entriesAfter: after,
        entriesRemoved: before - after
      });
    }
  }

  getStatus() {
    const now = Date.now();
    const globalWindowStart = now - RATE_LIMIT_CONFIG.GLOBAL_WINDOW_MS;

    const status = {
      global: {
        current: this.globalRequests.filter(ts => ts > globalWindowStart).length,
        limit: RATE_LIMIT_CONFIG.GLOBAL_MAX_REQUESTS,
        windowMs: RATE_LIMIT_CONFIG.GLOBAL_WINDOW_MS
      },
      tools: {}
    };

    const toolWindowStart = now - RATE_LIMIT_CONFIG.TOOL_WINDOW_MS;
    for (const [toolName, timestamps] of this.toolRequests.entries()) {
      const count = timestamps.filter(ts => ts > toolWindowStart).length;
      const limit = RATE_LIMIT_CONFIG.TOOL_MAX_REQUESTS[toolName] || RATE_LIMIT_CONFIG.DEFAULT_TOOL_MAX;
      status.tools[toolName] = { current: count, limit };
    }

    return status;
  }

  stop() {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
  }
}

// ============================================
// ERROR HANDLING
// ============================================

/**
 * Wrap ValidationError to match CascadeError interface
 */
function wrapValidationError(error) {
  return {
    success: false,
    error: {
      code: ErrorCodes.VALIDATION_ERROR,
      message: sanitizeErrorMessage(error.message),
      statusCode: StatusCodes.BAD_REQUEST,
      timestamp: Date.now(),
      field: error.field || 'unknown',
      validationMessage: sanitizeErrorMessage(error.validationMessage || error.message)
    }
  };
}

/**
 * Central error handler for all tool operations
 */
export function handleError(error, toolName, logger = null) {
  let errorResponse;

  if (error instanceof CascadeError) {
    errorResponse = error.toSafeJSON();
  } else if (error instanceof ValidationError) {
    errorResponse = wrapValidationError(error);
  } else if (error instanceof RateLimitError) {
    errorResponse = {
      success: false,
      error: {
        code: ErrorCodes.RATE_LIMIT_EXCEEDED,
        message: sanitizeErrorMessage(error.message),
        statusCode: StatusCodes.RATE_LIMITED,
        timestamp: Date.now(),
        retryAfterMs: error.retryAfterMs,
        retryAfterSeconds: Math.ceil(error.retryAfterMs / 1000)
      }
    };
  } else if (error && error.code && error.code.startsWith('SQLITE')) {
    errorResponse = {
      success: false,
      error: {
        code: ErrorCodes.DATABASE_ERROR,
        message: 'Database operation failed',
        statusCode: StatusCodes.INTERNAL_ERROR,
        timestamp: Date.now(),
        details: {
          sqliteCode: error.code
        }
      }
    };
  } else {
    errorResponse = {
      success: false,
      error: {
        code: ErrorCodes.INTERNAL_ERROR,
        message: sanitizeErrorMessage(error?.message || 'Unknown error'),
        statusCode: StatusCodes.INTERNAL_ERROR,
        timestamp: Date.now()
      }
    };
  }

  errorResponse.error.tool = toolName;

  if (DEBUG && error?.stack) {
    errorResponse.error._debug = {
      originalMessage: error.message,
      stack: error.stack.split('\n').slice(0, 5).join('\n')
    };
  }

  if (logger) {
    logger.error('Tool error occurred', {
      tool: toolName,
      errorName: error?.name || 'Error',
      errorCode: error?.code || 'UNKNOWN',
      error
    });
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify(errorResponse, null, 2)
    }],
    isError: true
  };
}

/**
 * Create success response with consistent format
 */
export function createSuccessResponse(data, toolName) {
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        success: true,
        tool: toolName,
        timestamp: Date.now(),
        data
      }, null, 2)
    }]
  };
}

// ============================================
// MEMORY OPERATIONS
// ============================================

/**
 * Save memory to CASCADE with DUAL-WRITE pattern
 */
export async function saveMemory(dbManager, content, layer = null, metadata = {}, logger = null, auditOperation = null) {
  const startTime = Date.now();
  const requestId = logger?._generateRequestId?.() || `req-${Date.now()}`;

  try {
    const validatedContent = validateContent(content);
    const validatedLayer = layer ? validateLayer(layer) : null;
    const validatedMetadata = validateMetadata(metadata);
    const targetLayer = validatedLayer || determineLayer(validatedContent, validatedMetadata);

    logger?.debug('Saving memory', {
      requestId,
      layer: targetLayer,
      contentLength: validatedContent.length,
      hasMetadata: Object.keys(validatedMetadata).length > 0
    });

    await dbManager.getConnection(targetLayer);

    const timestamp = Date.now() / 1000;
    const importance = validatedMetadata.importance !== undefined ? validatedMetadata.importance : 0.7;
    const emotionalIntensity = validatedMetadata.emotional_intensity !== undefined ? validatedMetadata.emotional_intensity : 0.5;

    const insertSQL = `
      INSERT INTO memories (timestamp, content, event, context, emotional_intensity, importance, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `;
    const insertParams = [
      timestamp,
      validatedContent,
      validatedContent,
      validatedMetadata.context || '',
      emotionalIntensity,
      importance,
      JSON.stringify(validatedMetadata)
    ];

    await dbManager.dualWrite(targetLayer, insertSQL, insertParams);
    const memoryId = await dbManager.getLastInsertId(targetLayer);

    const durationMs = Date.now() - startTime;

    if (logger && auditOperation) {
      logger.audit(auditOperation.MEMORY_SAVE, {
        requestId,
        layer: targetLayer,
        memoryId,
        contentLength: validatedContent.length,
        importance,
        emotionalIntensity,
        dualWrite: WRITE_PATHS.length > 1,
        durationMs,
        success: true
      });
    }

    logger?.info('Memory saved successfully', {
      requestId,
      layer: targetLayer,
      memoryId,
      durationMs
    });

    return {
      layer: targetLayer,
      id: memoryId,
      timestamp,
      dual_write: WRITE_PATHS.length > 1
    };
  } catch (error) {
    const durationMs = Date.now() - startTime;

    if (logger && auditOperation) {
      logger.audit(auditOperation.MEMORY_SAVE, {
        requestId,
        layer: layer || 'auto',
        contentLength: content ? content.length : 0,
        durationMs,
        success: false,
        errorCode: error.code || 'UNKNOWN',
        errorMessage: error.message
      });
    }

    logger?.error('Failed to save memory', {
      requestId,
      error,
      layer: layer || 'auto',
      durationMs
    });

    if (error instanceof CascadeError || error instanceof ValidationError) {
      throw error;
    }

    throw new DatabaseError(
      'Failed to save memory',
      'save_memory',
      { layer: layer || 'auto' }
    );
  }
}

/**
 * Recall memories from CASCADE
 */
export async function recallMemories(dbManager, query, layer = null, limit = 10, logger = null, auditOperation = null) {
  const startTime = Date.now();
  const requestId = logger?._generateRequestId?.() || `req-${Date.now()}`;

  try {
    if (query === null || query === undefined || (typeof query === 'string' && query.trim() === '')) {
      throw new ValidationError('query', 'Query is required');
    }
    if (typeof query !== 'string') {
      throw new ValidationError('query', 'Query must be a string');
    }
    if (query.length > CONTENT_LIMITS.MAX_QUERY_LENGTH) {
      throw new ValidationError('query', `Query exceeds maximum length of ${CONTENT_LIMITS.MAX_QUERY_LENGTH} characters`);
    }
    const validatedQuery = query.trim();
    const validatedLayer = layer ? validateLayer(layer) : null;
    const validatedLimit = validateLimit(limit);

    logger?.debug('Recalling memories', {
      requestId,
      queryLength: validatedQuery.length,
      layer: validatedLayer || 'all',
      limit: validatedLimit
    });

    const layers = validatedLayer ? [validatedLayer] : Object.keys(MEMORY_LAYERS);
    const results = [];

    const escapedQuery = escapeLikePattern(validatedQuery);
    const likePattern = `%${escapedQuery}%`;

    for (const currentLayer of layers) {
      const db = await dbManager.getConnection(currentLayer);

      const memories = await db.allAsync(`
        SELECT * FROM memories
        WHERE event LIKE ? ESCAPE '\\' OR context LIKE ? ESCAPE '\\'
        ORDER BY timestamp DESC
        LIMIT ?
      `, [likePattern, likePattern, validatedLimit]);

      for (const memory of memories) {
        results.push({
          layer: currentLayer,
          id: memory.id,
          timestamp: memory.timestamp,
          content: memory.event,
          context: memory.context,
          importance: memory.importance,
          emotional_intensity: memory.emotional_intensity,
          metadata: memory.metadata ? JSON.parse(memory.metadata) : {}
        });
      }
    }

    results.sort((a, b) => b.timestamp - a.timestamp);
    const finalResults = results.slice(0, validatedLimit);
    const durationMs = Date.now() - startTime;

    if (logger && auditOperation) {
      logger.audit(auditOperation.MEMORY_RECALL, {
        requestId,
        queryLength: validatedQuery.length,
        layer: validatedLayer || 'all',
        layersSearched: layers.length,
        limit: validatedLimit,
        resultsFound: finalResults.length,
        durationMs,
        success: true
      });
    }

    logger?.info('Memories recalled successfully', {
      requestId,
      resultsFound: finalResults.length,
      durationMs
    });

    return finalResults;
  } catch (error) {
    const durationMs = Date.now() - startTime;

    if (logger && auditOperation) {
      logger.audit(auditOperation.MEMORY_RECALL, {
        requestId,
        queryLength: query ? query.length : 0,
        layer: layer || 'all',
        durationMs,
        success: false,
        errorCode: error.code || 'UNKNOWN',
        errorMessage: error.message
      });
    }

    logger?.error('Failed to recall memories', {
      requestId,
      error,
      layer: layer || 'all',
      durationMs
    });

    if (error instanceof CascadeError || error instanceof ValidationError) {
      throw error;
    }

    throw new DatabaseError(
      'Failed to recall memories',
      'recall_memories',
      { layer: layer || 'all' }
    );
  }
}

/**
 * Query specific layer
 */
export async function queryLayer(dbManager, layer, options = {}, logger = null, auditOperation = null) {
  const startTime = Date.now();
  const requestId = logger?._generateRequestId?.() || `req-${Date.now()}`;

  try {
    const validatedLayer = validateLayer(layer, true);
    const validatedOptions = validateQueryOptions(options);

    logger?.debug('Querying layer', {
      requestId,
      layer: validatedLayer,
      hasFilters: !!validatedOptions.filters,
      limit: validatedOptions.limit
    });

    const db = await dbManager.getConnection(validatedLayer);
    const limit = validatedOptions.limit;
    const orderBy = sanitizeOrderBy(validatedOptions.order_by);

    let query = `SELECT * FROM memories`;
    const params = [];

    if (validatedOptions._deprecated_where_used) {
      logger?.warn('Deprecated WHERE clause usage', {
        requestId,
        message: 'Arbitrary WHERE clauses are deprecated for security. Use structured filters instead.'
      });
    }

    const { whereClause, params: filterParams } = buildWhereClause(validatedOptions.filters);
    if (whereClause) {
      query += ` WHERE ${whereClause}`;
      params.push(...filterParams);
    }

    if (!validatedOptions.filters && validatedOptions.params && Array.isArray(validatedOptions.params) && validatedOptions.params.length > 0) {
      const searchTerm = validatedOptions.params[0];
      if (typeof searchTerm === 'string') {
        if (searchTerm.length > CONTENT_LIMITS.MAX_QUERY_LENGTH) {
          throw new ValidationError('params[0]', `Search term exceeds maximum length of ${CONTENT_LIMITS.MAX_QUERY_LENGTH}`);
        }
        const escaped = escapeLikePattern(searchTerm);
        query += ` WHERE (event LIKE ? ESCAPE '\\' OR context LIKE ? ESCAPE '\\')`;
        params.push(`%${escaped}%`, `%${escaped}%`);
      }
    }

    query += ` ORDER BY ${orderBy} LIMIT ?`;
    params.push(limit);

    const memories = await db.allAsync(query, params);

    const results = memories.map(m => ({
      id: m.id,
      timestamp: m.timestamp,
      content: m.event,
      context: m.context,
      importance: m.importance,
      emotional_intensity: m.emotional_intensity,
      metadata: m.metadata ? JSON.parse(m.metadata) : {}
    }));

    const durationMs = Date.now() - startTime;

    if (logger && auditOperation) {
      logger.audit(auditOperation.MEMORY_QUERY, {
        requestId,
        layer: validatedLayer,
        filterCount: validatedOptions.filters ? Object.keys(validatedOptions.filters).length : 0,
        limit,
        orderBy,
        resultsFound: results.length,
        durationMs,
        success: true
      });
    }

    logger?.info('Layer query completed', {
      requestId,
      layer: validatedLayer,
      resultsFound: results.length,
      durationMs
    });

    return results;
  } catch (error) {
    const durationMs = Date.now() - startTime;

    if (logger && auditOperation) {
      logger.audit(auditOperation.MEMORY_QUERY, {
        requestId,
        layer: layer || 'unknown',
        durationMs,
        success: false,
        errorCode: error.code || 'UNKNOWN',
        errorMessage: error.message
      });
    }

    logger?.error('Failed to query layer', {
      requestId,
      error,
      layer: layer || 'unknown',
      durationMs
    });

    if (error instanceof CascadeError || error instanceof ValidationError) {
      throw error;
    }

    throw new DatabaseError(
      'Failed to query layer',
      'query_layer',
      { layer: layer || 'unknown' }
    );
  }
}

/**
 * Get CASCADE status
 */
export async function getStatus(dbManager, logger = null) {
  try {
    const status = {
      cascade_path: CASCADE_DB_PATH,
      system: 'CASCADE Enterprise',
      version: '2.0.0',
      layers: {},
      total_memories: 0,
      health: 'healthy',
      dual_write: {
        enabled: WRITE_PATHS.length > 1,
        ram_enabled: USE_RAM,
        read_path: READ_PATH,
        write_paths: WRITE_PATHS,
        disk_path: DISK_DB_PATH,
        ram_path: RAM_DB_PATH
      }
    };

    const fs = await import('fs');
    const path = await import('path');

    for (const [layer, dbFile] of Object.entries(MEMORY_LAYERS)) {
      const fullPath = path.join(CASCADE_DB_PATH, dbFile);

      if (!fs.existsSync(fullPath)) {
        status.layers[layer] = { status: 'missing', count: 0 };
        status.health = 'degraded';
        continue;
      }

      try {
        const db = await dbManager.getConnection(layer);
        const result = await db.getAsync('SELECT COUNT(*) as count FROM memories');
        const count = result.count || 0;

        status.layers[layer] = {
          status: 'connected',
          count,
          path: fullPath
        };
        status.total_memories += count;
      } catch (error) {
        status.layers[layer] = { status: 'error', error: error.message };
        status.health = 'degraded';
      }
    }

    logger?.info(`CASCADE status: ${status.total_memories} total memories, health: ${status.health}`);

    return status;
  } catch (error) {
    logger?.error('Error getting system status:', { error });

    if (error instanceof CascadeError || error instanceof ValidationError) {
      throw error;
    }

    throw new DatabaseError(
      'Failed to get system status',
      'get_status'
    );
  }
}

/**
 * Get detailed statistics
 */
export async function getStats(dbManager, logger = null) {
  try {
    const stats = {
      system: 'CASCADE Enterprise',
      version: '2.0.0',
      dual_write_enabled: WRITE_PATHS.length > 1,
      layers: {}
    };

    for (const layer of Object.keys(MEMORY_LAYERS)) {
      const db = await dbManager.getConnection(layer);

      const count = await db.getAsync('SELECT COUNT(*) as count FROM memories');
      const avgImportance = await db.getAsync('SELECT AVG(importance) as avg FROM memories');
      const avgEmotional = await db.getAsync('SELECT AVG(emotional_intensity) as avg FROM memories');
      const recent = await db.getAsync('SELECT MAX(timestamp) as max FROM memories');

      stats.layers[layer] = {
        count: count.count || 0,
        avg_importance: avgImportance.avg || 0,
        avg_emotional_intensity: avgEmotional.avg || 0,
        most_recent: recent.max || 0
      };
    }

    return stats;
  } catch (error) {
    logger?.error('Error getting system stats:', { error });

    if (error instanceof CascadeError || error instanceof ValidationError) {
      throw error;
    }

    throw new DatabaseError(
      'Failed to get system statistics',
      'get_stats'
    );
  }
}

// ============================================
// TOOL DEFINITIONS
// ============================================

/**
 * MCP tool definitions
 */
export const TOOLS = [
  {
    name: "remember",
    description: "Save a memory to CASCADE system with automatic layer routing based on content type",
    inputSchema: {
      type: "object",
      properties: {
        content: {
          type: "string",
          description: "The memory content to save"
        },
        layer: {
          type: "string",
          enum: ["episodic", "semantic", "procedural", "meta", "identity", "working"],
          description: "Optional: Specific layer to save to (auto-determined if not specified)"
        },
        metadata: {
          type: "object",
          description: "Optional metadata (importance, emotional_intensity, context, etc.)",
          properties: {
            importance: { type: "number" },
            emotional_intensity: { type: "number" },
            context: { type: "string" }
          }
        }
      },
      required: ["content"]
    }
  },
  {
    name: "recall",
    description: "Search and retrieve memories from CASCADE layers with content matching",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search query to match against memory content"
        },
        layer: {
          type: "string",
          enum: ["episodic", "semantic", "procedural", "meta", "identity", "working"],
          description: "Optional: Search only in specific layer"
        },
        limit: {
          type: "number",
          description: "Maximum number of results to return (default: 10)"
        }
      },
      required: ["query"]
    }
  },
  {
    name: "query_layer",
    description: "Query specific CASCADE memory layer with structured filters (parameterized for security)",
    inputSchema: {
      type: "object",
      properties: {
        layer: {
          type: "string",
          enum: ["episodic", "semantic", "procedural", "meta", "identity", "working"],
          description: "Memory layer to query"
        },
        options: {
          type: "object",
          description: "Query options with structured filters",
          properties: {
            filters: {
              type: "object",
              description: "Structured filter conditions (safe parameterized queries)",
              properties: {
                importance_min: { type: "number", description: "Minimum importance (0-1)" },
                importance_max: { type: "number", description: "Maximum importance (0-1)" },
                emotional_intensity_min: { type: "number", description: "Minimum emotional intensity (0-1)" },
                emotional_intensity_max: { type: "number", description: "Maximum emotional intensity (0-1)" },
                timestamp_after: { type: "number", description: "Unix timestamp - memories after this time" },
                timestamp_before: { type: "number", description: "Unix timestamp - memories before this time" },
                content_contains: { type: "string", description: "Text to search in content/event" },
                context_contains: { type: "string", description: "Text to search in context" },
                id: { type: "number", description: "Exact memory ID" }
              }
            },
            limit: { type: "number", description: "Max results (1-1000, default: 20)" },
            order_by: { type: "string", description: "Column and direction (e.g., 'timestamp DESC', 'importance ASC')" }
          }
        }
      },
      required: ["layer"]
    }
  },
  {
    name: "get_status",
    description: "Get CASCADE memory system status including memory counts and layer health",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "get_stats",
    description: "Get detailed statistics for all memory layers",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "save_to_layer",
    description: "Save memory to a specific layer with full control over metadata",
    inputSchema: {
      type: "object",
      properties: {
        layer: {
          type: "string",
          enum: ["episodic", "semantic", "procedural", "meta", "identity", "working"],
          description: "Target memory layer"
        },
        content: {
          type: "string",
          description: "Memory content to save"
        },
        metadata: {
          type: "object",
          description: "Full metadata control"
        }
      },
      required: ["layer", "content"]
    }
  }
];

// ============================================
// EXPORTS
// ============================================

export default {
  // Rate limiting
  RATE_LIMIT_CONFIG,
  RateLimitError,
  RateLimiter,

  // Error handling
  handleError,
  createSuccessResponse,

  // Memory operations
  saveMemory,
  recallMemories,
  queryLayer,
  getStatus,
  getStats,

  // Tool definitions
  TOOLS
};
