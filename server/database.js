/**
 * CASCADE Memory System
 * Copyright (c) 2025-2026 CIPS Corp (C.I.P.S. LLC)
 * Commercial License - See LICENSE file
 *
 * https://cipscorps.io
 * Contact: glass@cipscorps.io
 *
 * Database Module - Connection pool, schema management, and dual-write pattern
 *
 * DUAL-WRITE Architecture:
 * - RAM disk for instant reads
 * - Disk storage for permanent truth
 * - WRITE: Disk first (truth) -> RAM second (cache)
 * - READ: RAM first (instant) -> Disk fallback
 */

import sqlite3 from 'sqlite3';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs';

import {
  ValidationError,
  VALID_LAYERS,
  CONTENT_LIMITS,
  validateLayer,
  validateContent,
  validateMetadata,
  validateLimit
} from './validation.js';

// ============================================
// CONFIGURATION
// ============================================

// DUAL-WRITE Configuration
export const RAM_DB_PATH = process.env.CASCADE_RAM_PATH || 'R:\\CASCADE_DB';
export const DISK_DB_PATH = process.env.CASCADE_DB_PATH || path.join(
  process.env.HOME || process.env.USERPROFILE,
  '.cascade-memory',
  'data'
);

// Check if RAM directory exists (RAM disk may not always be mounted)
export const USE_RAM = fs.existsSync(RAM_DB_PATH) || (() => {
  try {
    fs.mkdirSync(RAM_DB_PATH, { recursive: true });
    return true;
  } catch (e) {
    return false;
  }
})();

// READ from RAM (fast) if available, WRITE to DISK first (truth) then RAM (cache)
export const READ_PATH = USE_RAM ? RAM_DB_PATH : DISK_DB_PATH;
export const WRITE_PATHS = USE_RAM ? [DISK_DB_PATH, RAM_DB_PATH] : [DISK_DB_PATH];
export const CASCADE_DB_PATH = READ_PATH;

export const DEBUG = process.env.DEBUG === 'true';

// Memory layer definitions
export const MEMORY_LAYERS = Object.freeze(
  VALID_LAYERS.reduce((acc, layer) => {
    acc[layer] = `${layer}_memory.db`;
    return acc;
  }, {})
);

// ============================================
// ERROR CLASSES
// ============================================

/**
 * Error codes for consistent identification
 */
export const ErrorCodes = Object.freeze({
  // Validation errors (4xx)
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  INVALID_INPUT: 'INVALID_INPUT',
  INVALID_LAYER: 'INVALID_LAYER',
  INVALID_CONTENT: 'INVALID_CONTENT',
  INVALID_QUERY: 'INVALID_QUERY',

  // Rate limiting (429)
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',

  // Database errors (5xx)
  DATABASE_ERROR: 'DATABASE_ERROR',
  CONNECTION_ERROR: 'CONNECTION_ERROR',
  QUERY_ERROR: 'QUERY_ERROR',
  WRITE_ERROR: 'WRITE_ERROR',

  // Internal errors (5xx)
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  UNKNOWN_TOOL: 'UNKNOWN_TOOL',
  CONFIGURATION_ERROR: 'CONFIGURATION_ERROR'
});

/**
 * HTTP-like status codes for MCP responses
 */
export const StatusCodes = Object.freeze({
  OK: 200,
  BAD_REQUEST: 400,
  NOT_FOUND: 404,
  RATE_LIMITED: 429,
  INTERNAL_ERROR: 500,
  SERVICE_UNAVAILABLE: 503
});

/**
 * Sensitive patterns to sanitize from error messages
 */
const SENSITIVE_PATTERNS = [
  /C:\\Users\\[^\\]+/gi,
  /[A-Z]:\\Users\\[^\\]+/gi,
  /\/home\/[^\/]+/gi,
  /\/Users\/[^\/]+/gi,
  /process\.env\.\w+/gi,
  /[A-Z]:\\[^\s"']+/gi,
  /\/[^\s"']*\/[^\s"']*/gi,
  /\b(?:192\.168|10\.|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b/g,
  /at\s+[^\s]+\s+\([^)]+\)/gi
];

/**
 * Sanitize error message to remove sensitive information
 */
export function sanitizeErrorMessage(message) {
  if (typeof message !== 'string') {
    return 'An error occurred';
  }

  let sanitized = message;

  for (const pattern of SENSITIVE_PATTERNS) {
    sanitized = sanitized.replace(pattern, '[REDACTED]');
  }

  sanitized = sanitized.replace(/(\[REDACTED\]\s*)+/g, '[REDACTED] ');
  sanitized = sanitized.replace(/\s+/g, ' ').trim();

  return sanitized || 'An error occurred';
}

/**
 * Sanitize error details object
 */
export function sanitizeDetails(details) {
  if (!details || typeof details !== 'object') {
    return {};
  }

  const sanitized = {};
  const sensitiveKeys = ['path', 'file', 'directory', 'stack', 'trace', 'pwd', 'cwd', 'home'];

  for (const [key, value] of Object.entries(details)) {
    if (sensitiveKeys.some(sk => key.toLowerCase().includes(sk))) {
      continue;
    }

    if (typeof value === 'string') {
      sanitized[key] = sanitizeErrorMessage(value);
    } else if (typeof value === 'number' || typeof value === 'boolean') {
      sanitized[key] = value;
    } else if (Array.isArray(value)) {
      sanitized[key] = value.map(v =>
        typeof v === 'string' ? sanitizeErrorMessage(v) : v
      ).slice(0, 10);
    }
  }

  return sanitized;
}

/**
 * Base error class for all CASCADE errors
 */
export class CascadeError extends Error {
  constructor(message, code = ErrorCodes.INTERNAL_ERROR, statusCode = StatusCodes.INTERNAL_ERROR, details = {}) {
    super(message);
    this.name = 'CascadeError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
    this.timestamp = Date.now();
  }

  toSafeJSON() {
    return {
      success: false,
      error: {
        code: this.code,
        message: sanitizeErrorMessage(this.message),
        statusCode: this.statusCode,
        timestamp: this.timestamp,
        ...(Object.keys(this.details).length > 0 && { details: sanitizeDetails(this.details) })
      }
    };
  }
}

/**
 * Database-specific error class
 */
export class DatabaseError extends CascadeError {
  constructor(message, operation = 'unknown', details = {}) {
    super(message, ErrorCodes.DATABASE_ERROR, StatusCodes.INTERNAL_ERROR, details);
    this.name = 'DatabaseError';
    this.operation = operation;
  }

  toSafeJSON() {
    const base = super.toSafeJSON();
    base.error.operation = this.operation;
    return base;
  }
}

/**
 * Configuration error class
 */
export class ConfigurationError extends CascadeError {
  constructor(message, details = {}) {
    super(message, ErrorCodes.CONFIGURATION_ERROR, StatusCodes.SERVICE_UNAVAILABLE, details);
    this.name = 'ConfigurationError';
  }
}

// ============================================
// DATABASE CONNECTION POOL
// ============================================

/**
 * Database connection pool with DUAL-WRITE support
 * Architecture: READ from RAM (instant), WRITE to DISK first (truth) then RAM (cache)
 */
export class CascadeDatabase {
  constructor(readPath, writePaths, logger = null) {
    this.readPath = readPath;
    this.writePaths = writePaths;
    this.readConnections = new Map();
    this.writeConnections = new Map();
    this.logger = logger;
  }

  /**
   * Log helper
   */
  log(level, message, context = {}) {
    if (this.logger) {
      this.logger[level](message, context);
    } else {
      console.error(`[${level.toUpperCase()}] ${message}`, context);
    }
  }

  /**
   * Create a promisified database connection
   */
  async createDbConnection(dbFile) {
    const db = new sqlite3.Database(dbFile);
    db.runAsync = promisify(db.run.bind(db));
    db.getAsync = promisify(db.get.bind(db));
    db.allAsync = promisify(db.all.bind(db));
    return db;
  }

  /**
   * Get database connection for reading (from RAM if available)
   */
  async getConnection(layer) {
    const validatedLayer = validateLayer(layer, true);
    if (!MEMORY_LAYERS[validatedLayer]) {
      throw new ValidationError('layer', `Invalid memory layer: ${layer}`);
    }

    if (this.readConnections.has(layer)) {
      return this.readConnections.get(layer);
    }

    const dbFile = path.join(this.readPath, MEMORY_LAYERS[layer]);

    try {
      if (!fs.existsSync(dbFile)) {
        this.log('info', `Creating new database for layer: ${layer}`);
        const diskFile = path.join(DISK_DB_PATH, MEMORY_LAYERS[layer]);
        if (fs.existsSync(diskFile) && this.readPath !== DISK_DB_PATH) {
          fs.copyFileSync(diskFile, dbFile);
          this.log('info', `Copied ${layer} from disk to RAM`);
        }
      }

      const db = await this.createDbConnection(dbFile);
      await this.ensureSchema(db, layer);
      this.readConnections.set(layer, db);
      this.log('info', `Connected to ${layer} memory layer`);

      await this.initWriteConnections(layer);

      return db;
    } catch (error) {
      if (error instanceof CascadeError || error instanceof ValidationError) {
        throw error;
      }

      throw new DatabaseError(
        `Failed to connect to memory layer: ${layer}`,
        'connection',
        { layer }
      );
    }
  }

  /**
   * Initialize write connections for a layer (dual-write pattern)
   */
  async initWriteConnections(layer) {
    if (this.writeConnections.has(layer)) {
      return this.writeConnections.get(layer);
    }

    try {
      const connections = [];
      for (let i = 0; i < this.writePaths.length; i++) {
        const writePath = this.writePaths[i];
        if (!fs.existsSync(writePath)) {
          fs.mkdirSync(writePath, { recursive: true });
          this.log('info', `Created write directory for ${i === 0 ? 'primary' : 'secondary'} storage`);
        }

        const dbFile = path.join(writePath, MEMORY_LAYERS[layer]);
        const db = await this.createDbConnection(dbFile);
        await this.ensureSchema(db, layer);
        connections.push({ path: writePath, db });
        this.log('info', `Write connection established for ${layer} (${i === 0 ? 'primary' : 'secondary'})`);
      }

      this.writeConnections.set(layer, connections);
      return connections;
    } catch (error) {
      if (error instanceof CascadeError || error instanceof ValidationError) {
        throw error;
      }

      throw new DatabaseError(
        `Failed to initialize write connections for layer: ${layer}`,
        'init_write_connections',
        { layer }
      );
    }
  }

  /**
   * Ensure database schema exists
   */
  async ensureSchema(db, layer) {
    try {
      await db.runAsync(`
        CREATE TABLE IF NOT EXISTS memories (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp REAL NOT NULL,
          content TEXT,
          event TEXT,
          context TEXT,
          emotional_intensity REAL DEFAULT 0.5,
          importance REAL DEFAULT 0.5,
          metadata TEXT
        )
      `);
      await db.runAsync(`CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp)`);
      await db.runAsync(`CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance)`);
    } catch (error) {
      this.log('error', `Schema error for ${layer}:`, { error: error.message });
      throw new DatabaseError(
        `Failed to initialize schema for layer: ${layer}`,
        'schema_creation',
        { layer }
      );
    }
  }

  /**
   * Execute write operation on all write paths (DISK first, then RAM)
   * Returns result from first (disk) write
   */
  async dualWrite(layer, operation, params = []) {
    const writeConns = await this.initWriteConnections(layer);
    let primaryResult = null;

    for (let i = 0; i < writeConns.length; i++) {
      const { path: writePath, db } = writeConns[i];
      try {
        const result = await db.runAsync(operation, params);
        if (i === 0) {
          primaryResult = result;
        }
        this.log('info', `Dual-write to storage ${i === 0 ? 'primary' : 'secondary'} succeeded`);
      } catch (error) {
        this.log('error', `Dual-write to storage ${i === 0 ? 'primary' : 'secondary'} failed:`, { error: error.message });
        if (i === 0) {
          throw new DatabaseError(
            'Failed to write to primary storage',
            'dual_write',
            { layer, isPrimary: true }
          );
        }
      }
    }

    return primaryResult;
  }

  /**
   * Get last insert ID from primary write connection
   */
  async getLastInsertId(layer) {
    const writeConns = await this.initWriteConnections(layer);
    if (writeConns.length > 0) {
      const result = await writeConns[0].db.getAsync('SELECT last_insert_rowid() as id');
      return result.id;
    }
    return null;
  }

  /**
   * Close all connections
   */
  async closeAll() {
    for (const [layer, db] of this.readConnections) {
      await promisify(db.close.bind(db))();
      this.log('info', `Closed ${layer} read database`);
    }

    for (const [layer, conns] of this.writeConnections) {
      for (const { path: writePath, db } of conns) {
        await promisify(db.close.bind(db))();
        this.log('info', `Closed ${layer} write database at ${writePath}`);
      }
    }

    this.readConnections.clear();
    this.writeConnections.clear();
  }
}

// ============================================
// HELPER FUNCTIONS
// ============================================

/**
 * Determine appropriate memory layer based on content
 */
export function determineLayer(content, metadata = {}) {
  const contentLower = content.toLowerCase();

  if (metadata.layer && MEMORY_LAYERS[metadata.layer]) {
    return metadata.layer;
  }

  if (contentLower.includes('session') || contentLower.includes('conversation') ||
      contentLower.includes('today') || contentLower.includes('happened') ||
      contentLower.includes('event') || contentLower.includes('experience')) {
    return 'episodic';
  }

  if (contentLower.includes('definition') || contentLower.includes('concept') ||
      contentLower.includes('theory') || contentLower.includes('fact') ||
      contentLower.includes('knowledge') || contentLower.includes('meaning')) {
    return 'semantic';
  }

  if (contentLower.includes('how to') || contentLower.includes('process') ||
      contentLower.includes('step') || contentLower.includes('procedure') ||
      contentLower.includes('technique') || contentLower.includes('workflow')) {
    return 'procedural';
  }

  if (contentLower.includes('thinking') || contentLower.includes('awareness') ||
      contentLower.includes('pattern') || contentLower.includes('reflection') ||
      contentLower.includes('learning') || contentLower.includes('insight')) {
    return 'meta';
  }

  if (contentLower.includes('identity') || contentLower.includes('core values') ||
      contentLower.includes('strategic focus') || contentLower.includes('purpose') ||
      contentLower.includes('principle') || contentLower.includes('belief')) {
    return 'identity';
  }

  return 'working';
}

/**
 * Escape LIKE pattern special characters
 */
export function escapeLikePattern(str) {
  return str.replace(/[%_\\]/g, '\\$&');
}

/**
 * Allowed columns for filtering and ordering (whitelist)
 */
export const ALLOWED_COLUMNS = ['id', 'timestamp', 'content', 'event', 'context', 'emotional_intensity', 'importance'];
export const ALLOWED_ORDER_DIRECTIONS = ['ASC', 'DESC'];

/**
 * Validate and sanitize order_by clause
 */
export function sanitizeOrderBy(orderBy) {
  if (!orderBy) return 'timestamp DESC';

  const parts = orderBy.trim().split(/\s+/);
  const column = parts[0]?.toLowerCase();
  const direction = parts[1]?.toUpperCase() || 'DESC';

  if (!ALLOWED_COLUMNS.includes(column)) {
    return 'timestamp DESC';
  }

  if (!ALLOWED_ORDER_DIRECTIONS.includes(direction)) {
    return `${column} DESC`;
  }

  return `${column} ${direction}`;
}

/**
 * Build safe WHERE clause from structured filter options
 */
export function buildWhereClause(filters) {
  const conditions = [];
  const params = [];

  if (!filters || typeof filters !== 'object') {
    return { whereClause: '', params: [] };
  }

  if (filters.importance_min !== undefined) {
    conditions.push('importance >= ?');
    params.push(Number(filters.importance_min));
  }

  if (filters.importance_max !== undefined) {
    conditions.push('importance <= ?');
    params.push(Number(filters.importance_max));
  }

  if (filters.emotional_intensity_min !== undefined) {
    conditions.push('emotional_intensity >= ?');
    params.push(Number(filters.emotional_intensity_min));
  }

  if (filters.emotional_intensity_max !== undefined) {
    conditions.push('emotional_intensity <= ?');
    params.push(Number(filters.emotional_intensity_max));
  }

  if (filters.timestamp_after !== undefined) {
    conditions.push('timestamp >= ?');
    params.push(Number(filters.timestamp_after));
  }

  if (filters.timestamp_before !== undefined) {
    conditions.push('timestamp <= ?');
    params.push(Number(filters.timestamp_before));
  }

  if (filters.content_contains !== undefined) {
    const escaped = escapeLikePattern(String(filters.content_contains));
    conditions.push("(event LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')");
    params.push(`%${escaped}%`, `%${escaped}%`);
  }

  if (filters.context_contains !== undefined) {
    const escaped = escapeLikePattern(String(filters.context_contains));
    conditions.push("context LIKE ? ESCAPE '\\'");
    params.push(`%${escaped}%`);
  }

  if (filters.id !== undefined) {
    conditions.push('id = ?');
    params.push(Number(filters.id));
  }

  const whereClause = conditions.length > 0 ? conditions.join(' AND ') : '';
  return { whereClause, params };
}

// ============================================
// EXPORT DEFAULT
// ============================================

export default {
  // Configuration
  RAM_DB_PATH,
  DISK_DB_PATH,
  USE_RAM,
  READ_PATH,
  WRITE_PATHS,
  CASCADE_DB_PATH,
  DEBUG,
  MEMORY_LAYERS,

  // Error classes
  ErrorCodes,
  StatusCodes,
  CascadeError,
  DatabaseError,
  ConfigurationError,

  // Database class
  CascadeDatabase,

  // Helper functions
  determineLayer,
  escapeLikePattern,
  sanitizeOrderBy,
  buildWhereClause,
  sanitizeErrorMessage,
  sanitizeDetails,

  // Constants
  ALLOWED_COLUMNS,
  ALLOWED_ORDER_DIRECTIONS
};
