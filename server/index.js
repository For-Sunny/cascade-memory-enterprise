#!/usr/bin/env node

/**
 * CASCADE Memory System
 * Copyright (c) 2025-2026 CIPS Corp (C.I.P.S. LLC)
 * Commercial License - See LICENSE file
 *
 * https://cipscorps.io
 * Contact: glass@cipscorps.io
 *
 * MCP Server - 6-Layer Structured Memory Architecture
 *
 * REFACTORED: January 22, 2026
 * Split into modular architecture:
 * - database.js: Connection pool, schema, dual-write pattern
 * - tools.js: Tool definitions and handlers
 * - index.js: Thin entry point (this file)
 *
 * DUAL-WRITE Architecture:
 * - RAM disk for instant reads
 * - Disk storage for permanent truth
 * - WRITE: Disk first (truth) -> RAM second (cache)
 * - READ: RAM first (instant) -> Disk fallback
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { EventEmitter } from 'events';
import fs from 'fs';

// Import validation module
import {
  ValidationError,
  VALID_LAYERS,
  CONTENT_LIMITS,
  NUMERIC_LIMITS
} from './validation.js';

// Import database module
import {
  CascadeDatabase,
  CascadeError,
  DatabaseError,
  ConfigurationError,
  ErrorCodes,
  StatusCodes,
  READ_PATH,
  WRITE_PATHS,
  CASCADE_DB_PATH,
  DISK_DB_PATH,
  RAM_DB_PATH,
  USE_RAM,
  DEBUG,
  DECAY_CONFIG,
  MEMORY_LAYERS,
  sanitizeErrorMessage,
  sanitizeDetails
} from './database.js';

// Import decay engine
import { DecayEngine } from './decay.js';

// Import tools module
import {
  TOOLS,
  RateLimiter,
  RateLimitError,
  RATE_LIMIT_CONFIG,
  handleError,
  createSuccessResponse,
  saveMemory,
  recallMemories,
  queryLayer,
  getStatus,
  getStats
} from './tools.js';

// ============================================
// STRUCTURED LOGGING SYSTEM
// ============================================

/**
 * Log levels with numeric priority for filtering
 */
const LogLevel = Object.freeze({
  DEBUG: { name: 'debug', priority: 10, color: '\x1b[36m' },
  INFO: { name: 'info', priority: 20, color: '\x1b[32m' },
  WARN: { name: 'warn', priority: 30, color: '\x1b[33m' },
  ERROR: { name: 'error', priority: 40, color: '\x1b[31m' },
  AUDIT: { name: 'audit', priority: 50, color: '\x1b[35m' }
});

/**
 * Operation types for audit logging
 */
const AuditOperation = Object.freeze({
  MEMORY_SAVE: 'MEMORY_SAVE',
  MEMORY_RECALL: 'MEMORY_RECALL',
  MEMORY_QUERY: 'MEMORY_QUERY',
  MEMORY_DELETE: 'MEMORY_DELETE',
  MEMORY_DECAY: 'MEMORY_DECAY',
  LAYER_ACCESS: 'LAYER_ACCESS',
  CONNECTION_OPEN: 'CONNECTION_OPEN',
  CONNECTION_CLOSE: 'CONNECTION_CLOSE',
  RATE_LIMIT_HIT: 'RATE_LIMIT_HIT',
  VALIDATION_FAIL: 'VALIDATION_FAIL',
  SERVER_START: 'SERVER_START',
  SERVER_STOP: 'SERVER_STOP',
  CONFIG_CHANGE: 'CONFIG_CHANGE'
});

/**
 * Structured Logger Class
 */
class StructuredLogger extends EventEmitter {
  constructor(options = {}) {
    super();
    this.serviceName = options.serviceName || 'cascade-memory';
    this.version = options.version || '2.1.0';
    this.minLevel = this._parseLevel(options.minLevel || (process.env.LOG_LEVEL || 'info'));
    this.jsonOutput = options.jsonOutput !== false;
    this.colorOutput = options.colorOutput !== false && process.stderr.isTTY;
    this.includeTimestamp = options.includeTimestamp !== false;
    this.includeContext = options.includeContext !== false;

    this.auditEnabled = options.auditEnabled !== false;
    this.auditLogPath = options.auditLogPath || null;
    this.auditBuffer = [];
    this.auditBufferSize = options.auditBufferSize || 100;
    this.auditFlushInterval = options.auditFlushInterval || 30000;

    this.sessionId = this._generateSessionId();
    this.requestCounter = 0;

    if (this.auditLogPath) {
      this._startAuditFlushTimer();
    }
  }

  _parseLevel(level) {
    if (typeof level === 'object' && level.priority !== undefined) {
      return level;
    }
    const levelName = String(level).toLowerCase();
    const found = Object.values(LogLevel).find(l => l.name === levelName);
    return found || LogLevel.INFO;
  }

  _generateSessionId() {
    return `${Date.now().toString(36)}-${Math.random().toString(36).substr(2, 9)}`;
  }

  _generateRequestId() {
    return `${this.sessionId}-${++this.requestCounter}`;
  }

  _formatTimestamp() {
    return new Date().toISOString();
  }

  _buildLogEntry(level, message, context = {}) {
    const entry = {
      timestamp: this._formatTimestamp(),
      level: level.name,
      service: this.serviceName,
      version: this.version,
      sessionId: this.sessionId,
      message: message
    };

    if (context && Object.keys(context).length > 0) {
      entry.context = context;
    }

    if (context.error instanceof Error) {
      entry.error = {
        name: context.error.name,
        message: context.error.message,
        code: context.error.code || undefined,
        stack: context.error.stack ?
          context.error.stack.split('\n').slice(0, 5).map(l => l.trim()) :
          undefined
      };
      delete entry.context.error;
    }

    return entry;
  }

  _formatOutput(entry, level) {
    if (this.jsonOutput) {
      return JSON.stringify(entry);
    }

    let output = '';

    if (this.colorOutput) {
      output += level.color;
    }

    output += `[${entry.timestamp}] `;
    output += `[${entry.level.toUpperCase().padEnd(5)}] `;
    output += `[${entry.service}] `;
    output += entry.message;

    if (entry.context && Object.keys(entry.context).length > 0) {
      output += ` | ${JSON.stringify(entry.context)}`;
    }

    if (this.colorOutput) {
      output += '\x1b[0m';
    }

    return output;
  }

  _write(level, message, context = {}) {
    if (level.priority < this.minLevel.priority) {
      return;
    }

    const entry = this._buildLogEntry(level, message, context);
    const output = this._formatOutput(entry, level);

    console.error(output);
    this.emit('log', entry, level);

    return entry;
  }

  debug(message, context = {}) {
    return this._write(LogLevel.DEBUG, message, context);
  }

  info(message, context = {}) {
    return this._write(LogLevel.INFO, message, context);
  }

  warn(message, context = {}) {
    return this._write(LogLevel.WARN, message, context);
  }

  error(message, context = {}) {
    return this._write(LogLevel.ERROR, message, context);
  }

  audit(operation, details = {}) {
    const entry = {
      timestamp: this._formatTimestamp(),
      level: 'audit',
      service: this.serviceName,
      sessionId: this.sessionId,
      requestId: details.requestId || this._generateRequestId(),
      operation: operation,
      details: {
        ...details,
        requestId: undefined
      },
      durationMs: details.durationMs || undefined,
      success: details.success !== false,
      errorCode: details.errorCode || undefined
    };

    Object.keys(entry).forEach(key => entry[key] === undefined && delete entry[key]);
    Object.keys(entry.details).forEach(key => entry.details[key] === undefined && delete entry.details[key]);

    this._write(LogLevel.AUDIT, `AUDIT: ${operation}`, entry.details);

    if (this.auditEnabled) {
      this.auditBuffer.push(entry);

      if (this.auditBuffer.length >= this.auditBufferSize) {
        this._flushAuditBuffer();
      }
    }

    this.emit('audit', entry);

    return entry;
  }

  _startAuditFlushTimer() {
    this.auditFlushTimer = setInterval(() => {
      this._flushAuditBuffer();
    }, this.auditFlushInterval);

    if (this.auditFlushTimer.unref) {
      this.auditFlushTimer.unref();
    }
  }

  async _flushAuditBuffer() {
    if (!this.auditLogPath || this.auditBuffer.length === 0) {
      return;
    }

    const entries = [...this.auditBuffer];
    this.auditBuffer = [];

    try {
      const content = entries.map(e => JSON.stringify(e)).join('\n') + '\n';
      await fs.promises.appendFile(this.auditLogPath, content, 'utf8');
    } catch (error) {
      this.auditBuffer.unshift(...entries);
      this.error('Failed to flush audit buffer', { error, entriesLost: entries.length });
    }
  }

  child(context = {}) {
    const childLogger = Object.create(this);
    childLogger.defaultContext = { ...this.defaultContext, ...context };

    ['debug', 'info', 'warn', 'error'].forEach(method => {
      const original = this[method].bind(this);
      childLogger[method] = (message, ctx = {}) => {
        return original(message, { ...childLogger.defaultContext, ...ctx });
      };
    });

    return childLogger;
  }

  log(level, ...args) {
    const message = args.join(' ');
    const levelObj = this._parseLevel(level);
    return this._write(levelObj, message);
  }

  getAuditStats() {
    return {
      sessionId: this.sessionId,
      requestCount: this.requestCounter,
      pendingAuditEntries: this.auditBuffer.length,
      auditEnabled: this.auditEnabled,
      auditLogPath: this.auditLogPath
    };
  }

  async shutdown() {
    if (this.auditFlushTimer) {
      clearInterval(this.auditFlushTimer);
      this.auditFlushTimer = null;
    }

    await this._flushAuditBuffer();

    this.info('Logger shutdown complete');
  }
}

// ============================================
// INITIALIZATION
// ============================================

// Initialize logger
const LOG_LEVEL = process.env.LOG_LEVEL || (process.env.DEBUG === 'true' ? 'debug' : 'info');
const AUDIT_LOG_PATH = process.env.CASCADE_AUDIT_LOG || null;

const logger = new StructuredLogger({
  serviceName: 'cascade-memory',
  version: '2.2.0',
  minLevel: LOG_LEVEL,
  jsonOutput: process.env.LOG_FORMAT !== 'text',
  auditEnabled: true,
  auditLogPath: AUDIT_LOG_PATH
});

// Initialize database manager with dual-write paths
const dbManager = new CascadeDatabase(READ_PATH, WRITE_PATHS, logger);

// Initialize decay engine
const decayEngine = new DecayEngine(dbManager, logger);

// Initialize rate limiter
const rateLimiter = new RateLimiter(logger);

// ============================================
// MCP SERVER
// ============================================

/**
 * Initialize MCP Server
 */
const server = new Server(
  {
    name: "cascade-memory",
    version: "2.2.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

/**
 * List available tools
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools: TOOLS };
});

/**
 * Handle tool calls with rate limiting and centralized error handling
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  // Rate limit check
  const rateLimitCheck = rateLimiter.checkLimit(name);

  if (!rateLimitCheck.allowed) {
    logger.audit(AuditOperation.RATE_LIMIT_HIT, {
      tool: name,
      reason: rateLimitCheck.reason,
      retryAfterMs: rateLimitCheck.retryAfterMs,
      currentStatus: rateLimiter.getStatus()
    });

    logger.warn('Rate limit exceeded', {
      tool: name,
      reason: rateLimitCheck.reason,
      retryAfterMs: rateLimitCheck.retryAfterMs
    });

    const rateLimitError = new RateLimitError(rateLimitCheck.reason, rateLimitCheck.retryAfterMs);
    return handleError(rateLimitError, name, logger);
  }

  rateLimiter.recordRequest(name);

  try {
    switch (name) {
      case "remember": {
        const result = await saveMemory(
          dbManager,
          args.content,
          args.layer || null,
          args.metadata || {},
          logger,
          AuditOperation
        );
        return createSuccessResponse(result, name);
      }

      case "recall": {
        const memories = await recallMemories(
          dbManager,
          args.query,
          args.layer || null,
          args.limit || 10,
          logger,
          AuditOperation,
          { decayEngine, include_decayed: args.include_decayed === true }
        );
        return createSuccessResponse(memories, name);
      }

      case "query_layer": {
        const results = await queryLayer(
          dbManager,
          args.layer,
          args.options || {},
          logger,
          AuditOperation,
          { decayEngine, include_decayed: args.include_decayed === true }
        );
        return createSuccessResponse(results, name);
      }

      case "get_status": {
        const status = await getStatus(dbManager, logger, decayEngine);
        return createSuccessResponse(status, name);
      }

      case "get_stats": {
        const stats = await getStats(dbManager, logger);
        return createSuccessResponse(stats, name);
      }

      case "save_to_layer": {
        const result = await saveMemory(
          dbManager,
          args.content,
          args.layer,
          args.metadata || {},
          logger,
          AuditOperation
        );
        return createSuccessResponse(result, name);
      }

      default:
        throw new CascadeError(
          `Unknown tool: ${name}`,
          ErrorCodes.UNKNOWN_TOOL,
          StatusCodes.BAD_REQUEST
        );
    }
  } catch (error) {
    return handleError(error, name, logger);
  }
});

// ============================================
// SERVER STARTUP
// ============================================

/**
 * Start server
 */
async function main() {
  const startTime = Date.now();

  logger.info('============================================');
  logger.info('CASCADE Enterprise Memory MCP Server v2.2.0');
  logger.info('============================================');

  logger.info('Server configuration loaded', {
    debugMode: DEBUG,
    logLevel: LOG_LEVEL,
    auditLogPath: AUDIT_LOG_PATH
  });

  logger.info('Validation configuration', {
    maxContentLength: CONTENT_LIMITS.MAX_CONTENT_LENGTH,
    maxQueryLength: CONTENT_LIMITS.MAX_QUERY_LENGTH,
    validLayers: VALID_LAYERS,
    limitRange: `${NUMERIC_LIMITS.MIN_LIMIT}-${NUMERIC_LIMITS.MAX_LIMIT}`
  });

  logger.info('Dual-write configuration', {
    ramDiskEnabled: USE_RAM,
    readPath: READ_PATH,
    writePaths: WRITE_PATHS,
    diskPath: DISK_DB_PATH,
    ramPath: RAM_DB_PATH
  });

  logger.info('Rate limiting configuration', {
    globalLimit: RATE_LIMIT_CONFIG.GLOBAL_MAX_REQUESTS,
    globalWindowMs: RATE_LIMIT_CONFIG.GLOBAL_WINDOW_MS,
    toolLimits: RATE_LIMIT_CONFIG.TOOL_MAX_REQUESTS,
    cleanupIntervalMs: RATE_LIMIT_CONFIG.CLEANUP_INTERVAL_MS
  });

  logger.info('Logging configuration', {
    sessionId: logger.sessionId,
    logLevel: LOG_LEVEL,
    jsonOutput: logger.jsonOutput,
    auditEnabled: logger.auditEnabled,
    auditLogPath: AUDIT_LOG_PATH
  });

  // Verify directories exist
  for (const writePath of WRITE_PATHS) {
    if (!fs.existsSync(writePath)) {
      logger.info('Creating directory', { path: writePath });
      fs.mkdirSync(writePath, { recursive: true });
    }
  }

  // Initialize all databases
  const initializedLayers = [];
  const failedLayers = [];

  for (const layer of Object.keys(MEMORY_LAYERS)) {
    try {
      await dbManager.getConnection(layer);
      initializedLayers.push(layer);

      logger.audit(AuditOperation.CONNECTION_OPEN, {
        layer,
        success: true
      });
    } catch (e) {
      failedLayers.push({ layer, error: e.message });
      logger.error('Failed to initialize layer', {
        layer,
        error: e
      });

      logger.audit(AuditOperation.CONNECTION_OPEN, {
        layer,
        success: false,
        errorMessage: e.message
      });
    }
  }

  // Start decay engine after all layers are initialized
  decayEngine.start();

  logger.info('Decay engine configuration', {
    enabled: DECAY_CONFIG.ENABLED,
    baseRate: DECAY_CONFIG.BASE_RATE,
    threshold: DECAY_CONFIG.THRESHOLD,
    immortalThreshold: DECAY_CONFIG.IMMORTAL_THRESHOLD,
    sweepIntervalMinutes: DECAY_CONFIG.SWEEP_INTERVAL_MINUTES
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);

  const startupDurationMs = Date.now() - startTime;

  logger.audit(AuditOperation.SERVER_START, {
    initializedLayers,
    failedLayers: failedLayers.length > 0 ? failedLayers : undefined,
    startupDurationMs,
    configuration: {
      dualWriteEnabled: WRITE_PATHS.length > 1,
      ramDiskEnabled: USE_RAM,
      rateLimitingEnabled: true,
      auditLoggingEnabled: logger.auditEnabled
    },
    success: failedLayers.length === 0
  });

  logger.info('============================================');
  logger.info('CASCADE Enterprise v2.2.0 ready!', {
    startupDurationMs,
    layersInitialized: initializedLayers.length,
    layersFailed: failedLayers.length,
    sessionId: logger.sessionId
  });
  logger.info('DoS protection ENGAGED!');
  logger.info('Centralized error handling ACTIVE!');
  logger.info('Structured logging ACTIVE!');
  logger.info('Audit trail ENABLED!');
  logger.info(`Temporal decay ${DECAY_CONFIG.ENABLED ? 'ACTIVE' : 'DISABLED'}!`);
  logger.info('============================================');
}

// ============================================
// SHUTDOWN HANDLERS
// ============================================

process.on('SIGINT', async () => {
  logger.info('Received SIGINT signal - initiating shutdown');

  logger.audit(AuditOperation.SERVER_STOP, {
    signal: 'SIGINT',
    auditStats: logger.getAuditStats()
  });

  decayEngine.stop();
  rateLimiter.stop();
  await logger.shutdown();
  await dbManager.closeAll();

  logger.info('Shutdown complete');
  process.exit(0);
});

process.on('SIGTERM', async () => {
  logger.info('Received SIGTERM signal - initiating shutdown');

  logger.audit(AuditOperation.SERVER_STOP, {
    signal: 'SIGTERM',
    auditStats: logger.getAuditStats()
  });

  decayEngine.stop();
  rateLimiter.stop();
  await logger.shutdown();
  await dbManager.closeAll();

  logger.info('Shutdown complete');
  process.exit(0);
});

// Start the server
main().catch((error) => {
  logger.audit(AuditOperation.SERVER_STOP, {
    signal: 'FATAL_ERROR',
    success: false,
    errorMessage: error?.message || 'Unknown fatal error'
  });

  logger.error('Fatal server error', {
    error,
    message: error?.message || 'Unknown fatal error'
  });

  process.exit(1);
});

// ============================================
// EXPORTS (for external use)
// ============================================

export {
  // Logger
  logger,
  StructuredLogger,
  LogLevel,
  AuditOperation,

  // Error classes
  CascadeError,
  DatabaseError,
  ConfigurationError,
  ErrorCodes,
  StatusCodes,

  // Decay
  DecayEngine,
  decayEngine,

  // Utilities
  sanitizeErrorMessage,
  handleError,
  createSuccessResponse
};
