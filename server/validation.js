/**
 * CASCADE Memory System
 * Copyright (c) 2025-2026 CIPS Corp (C.I.P.S. LLC)
 * Commercial License - See LICENSE file
 *
 * https://cipscorps.io
 * Contact: glass@cipscorps.io | opus@cipscorps.io
 *
 * Validation Module - Comprehensive validation for all MCP inputs
 */

// ============================================================================
// CONSTANTS - Validation Limits
// ============================================================================

/**
 * Content length limits
 */
export const CONTENT_LIMITS = {
  MIN_CONTENT_LENGTH: 1,
  MAX_CONTENT_LENGTH: 100000,      // 100KB max content
  MAX_CONTEXT_LENGTH: 10000,       // 10KB max context
  MAX_QUERY_LENGTH: 1000,          // 1KB max query
  MAX_METADATA_SIZE: 50000,        // 50KB max metadata JSON
  MAX_STRING_FIELD_LENGTH: 5000,   // 5KB for general string fields
};

/**
 * Numeric range limits
 */
export const NUMERIC_LIMITS = {
  // Importance and emotional intensity are 0-1 scales
  MIN_IMPORTANCE: 0,
  MAX_IMPORTANCE: 1,
  MIN_EMOTIONAL_INTENSITY: 0,
  MAX_EMOTIONAL_INTENSITY: 1,

  // Query limits
  MIN_LIMIT: 1,
  MAX_LIMIT: 1000,
  DEFAULT_LIMIT: 10,

  // Timestamp ranges (Unix epoch)
  MIN_TIMESTAMP: 0,
  MAX_TIMESTAMP: 4102444800, // Year 2100

  // ID ranges
  MIN_ID: 1,
  MAX_ID: Number.MAX_SAFE_INTEGER,
};

/**
 * Valid memory layers - strict whitelist
 */
export const VALID_LAYERS = Object.freeze([
  'episodic',
  'semantic',
  'procedural',
  'meta',
  'identity',
  'working'
]);

/**
 * Valid metadata field names - whitelist for safety
 */
export const VALID_METADATA_FIELDS = Object.freeze([
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
  'custom'  // Allow a 'custom' object for extensibility
]);

// ============================================================================
// VALIDATION ERROR CLASS
// ============================================================================

/**
 * Custom validation error with field information
 */
export class ValidationError extends Error {
  constructor(field, message, value = undefined) {
    super(`Validation failed for '${field}': ${message}`);
    this.name = 'ValidationError';
    this.field = field;
    this.validationMessage = message;
    // Don't expose the actual value in production for security
    this.invalidValue = process.env.DEBUG === 'true' ? value : '[hidden]';
  }

  toJSON() {
    return {
      error: 'ValidationError',
      field: this.field,
      message: this.validationMessage
    };
  }
}

// ============================================================================
// TYPE VALIDATORS
// ============================================================================

/**
 * Check if value is a string
 */
export function isString(value) {
  return typeof value === 'string';
}

/**
 * Check if value is a number (finite, not NaN)
 */
export function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Check if value is an integer
 */
export function isInteger(value) {
  return Number.isInteger(value);
}

/**
 * Check if value is a plain object
 */
export function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Check if value is an array
 */
export function isArray(value) {
  return Array.isArray(value);
}

// ============================================================================
// CONTENT VALIDATORS
// ============================================================================

/**
 * Validate content string
 * @param {*} content - Content to validate
 * @param {string} fieldName - Field name for error messages
 * @returns {string} - Validated and trimmed content
 * @throws {ValidationError}
 */
export function validateContent(content, fieldName = 'content') {
  if (content === null || content === undefined) {
    throw new ValidationError(fieldName, 'Content is required');
  }

  if (!isString(content)) {
    throw new ValidationError(fieldName, 'Content must be a string', typeof content);
  }

  const trimmed = content.trim();

  if (trimmed.length < CONTENT_LIMITS.MIN_CONTENT_LENGTH) {
    throw new ValidationError(fieldName, `Content must be at least ${CONTENT_LIMITS.MIN_CONTENT_LENGTH} character(s)`);
  }

  if (trimmed.length > CONTENT_LIMITS.MAX_CONTENT_LENGTH) {
    throw new ValidationError(
      fieldName,
      `Content exceeds maximum length of ${CONTENT_LIMITS.MAX_CONTENT_LENGTH} characters (got ${trimmed.length})`
    );
  }

  return trimmed;
}

/**
 * Validate query string
 * @param {*} query - Query to validate
 * @returns {string} - Validated and trimmed query
 * @throws {ValidationError}
 */
export function validateQuery(query) {
  if (query === null || query === undefined) {
    throw new ValidationError('query', 'Query is required');
  }

  if (!isString(query)) {
    throw new ValidationError('query', 'Query must be a string', typeof query);
  }

  const trimmed = query.trim();

  if (trimmed.length < 1) {
    throw new ValidationError('query', 'Query cannot be empty');
  }

  if (trimmed.length > CONTENT_LIMITS.MAX_QUERY_LENGTH) {
    throw new ValidationError(
      'query',
      `Query exceeds maximum length of ${CONTENT_LIMITS.MAX_QUERY_LENGTH} characters (got ${trimmed.length})`
    );
  }

  return trimmed;
}

/**
 * Validate context string (optional field)
 * @param {*} context - Context to validate
 * @returns {string} - Validated context or empty string
 * @throws {ValidationError}
 */
export function validateContext(context) {
  if (context === null || context === undefined || context === '') {
    return '';
  }

  if (!isString(context)) {
    throw new ValidationError('context', 'Context must be a string', typeof context);
  }

  if (context.length > CONTENT_LIMITS.MAX_CONTEXT_LENGTH) {
    throw new ValidationError(
      'context',
      `Context exceeds maximum length of ${CONTENT_LIMITS.MAX_CONTEXT_LENGTH} characters (got ${context.length})`
    );
  }

  return context;
}

// ============================================================================
// LAYER VALIDATORS
// ============================================================================

/**
 * Validate memory layer name (strict whitelist)
 * @param {*} layer - Layer name to validate
 * @param {boolean} required - Whether layer is required
 * @returns {string|null} - Validated layer or null if not required and not provided
 * @throws {ValidationError}
 */
export function validateLayer(layer, required = false) {
  if (layer === null || layer === undefined || layer === '') {
    if (required) {
      throw new ValidationError('layer', 'Layer is required');
    }
    return null;
  }

  if (!isString(layer)) {
    throw new ValidationError('layer', 'Layer must be a string', typeof layer);
  }

  const normalizedLayer = layer.toLowerCase().trim();

  if (!VALID_LAYERS.includes(normalizedLayer)) {
    throw new ValidationError(
      'layer',
      `Invalid layer '${normalizedLayer}'. Must be one of: ${VALID_LAYERS.join(', ')}`
    );
  }

  return normalizedLayer;
}

// ============================================================================
// NUMERIC VALIDATORS
// ============================================================================

/**
 * Validate a number is within a range
 * @param {*} value - Value to validate
 * @param {string} fieldName - Field name for error messages
 * @param {number} min - Minimum value (inclusive)
 * @param {number} max - Maximum value (inclusive)
 * @param {number|null} defaultValue - Default if not provided
 * @returns {number} - Validated number
 * @throws {ValidationError}
 */
export function validateNumericRange(value, fieldName, min, max, defaultValue = null) {
  if (value === null || value === undefined) {
    if (defaultValue !== null) {
      return defaultValue;
    }
    throw new ValidationError(fieldName, 'Value is required');
  }

  // Handle string numbers (e.g., from JSON parsing edge cases)
  let numValue = value;
  if (isString(value)) {
    numValue = parseFloat(value);
  }

  if (!isNumber(numValue)) {
    throw new ValidationError(fieldName, 'Value must be a number', value);
  }

  if (numValue < min || numValue > max) {
    throw new ValidationError(
      fieldName,
      `Value must be between ${min} and ${max} (got ${numValue})`
    );
  }

  return numValue;
}

/**
 * Validate importance field (0-1 scale)
 */
export function validateImportance(value) {
  return validateNumericRange(
    value,
    'importance',
    NUMERIC_LIMITS.MIN_IMPORTANCE,
    NUMERIC_LIMITS.MAX_IMPORTANCE,
    0.7  // Default importance
  );
}

/**
 * Validate emotional intensity field (0-1 scale)
 */
export function validateEmotionalIntensity(value) {
  return validateNumericRange(
    value,
    'emotional_intensity',
    NUMERIC_LIMITS.MIN_EMOTIONAL_INTENSITY,
    NUMERIC_LIMITS.MAX_EMOTIONAL_INTENSITY,
    0.5  // Default emotional intensity
  );
}

/**
 * Validate limit field (query results limit)
 */
export function validateLimit(value) {
  const limit = validateNumericRange(
    value,
    'limit',
    NUMERIC_LIMITS.MIN_LIMIT,
    NUMERIC_LIMITS.MAX_LIMIT,
    NUMERIC_LIMITS.DEFAULT_LIMIT
  );
  return Math.floor(limit);  // Ensure integer
}

/**
 * Validate timestamp field
 */
export function validateTimestamp(value, fieldName = 'timestamp') {
  if (value === null || value === undefined) {
    return null;  // Timestamps are optional in filters
  }

  return validateNumericRange(
    value,
    fieldName,
    NUMERIC_LIMITS.MIN_TIMESTAMP,
    NUMERIC_LIMITS.MAX_TIMESTAMP,
    null
  );
}

/**
 * Validate ID field
 */
export function validateId(value) {
  if (value === null || value === undefined) {
    return null;  // IDs are optional in filters
  }

  const id = validateNumericRange(
    value,
    'id',
    NUMERIC_LIMITS.MIN_ID,
    NUMERIC_LIMITS.MAX_ID,
    null
  );
  return Math.floor(id);  // Ensure integer
}

// ============================================================================
// METADATA VALIDATORS
// ============================================================================

/**
 * Validate metadata object
 * @param {*} metadata - Metadata to validate
 * @returns {object} - Validated and sanitized metadata
 * @throws {ValidationError}
 */
export function validateMetadata(metadata) {
  if (metadata === null || metadata === undefined) {
    return {};
  }

  if (!isPlainObject(metadata)) {
    throw new ValidationError('metadata', 'Metadata must be an object', typeof metadata);
  }

  // Check total size of metadata JSON
  const metadataJson = JSON.stringify(metadata);
  if (metadataJson.length > CONTENT_LIMITS.MAX_METADATA_SIZE) {
    throw new ValidationError(
      'metadata',
      `Metadata exceeds maximum size of ${CONTENT_LIMITS.MAX_METADATA_SIZE} bytes (got ${metadataJson.length})`
    );
  }

  const sanitized = {};

  for (const [key, value] of Object.entries(metadata)) {
    // Validate field name against whitelist (or allow if it's under 'custom')
    if (!VALID_METADATA_FIELDS.includes(key) && key !== 'custom') {
      // Log warning but don't reject - place unknown fields under 'custom'
      if (!sanitized.custom) {
        sanitized.custom = {};
      }
      sanitized.custom[key] = value;
      continue;
    }

    // Validate specific known fields
    switch (key) {
      case 'importance':
        sanitized.importance = validateImportance(value);
        break;

      case 'emotional_intensity':
        sanitized.emotional_intensity = validateEmotionalIntensity(value);
        break;

      case 'context':
        sanitized.context = validateContext(value);
        break;

      case 'layer':
        sanitized.layer = validateLayer(value, false);
        break;

      case 'timestamp':
        sanitized.timestamp = validateTimestamp(value);
        break;

      case 'tags':
        sanitized.tags = validateTags(value);
        break;

      case 'source':
        sanitized.source = validateStringField(value, 'source');
        break;

      case 'session_id':
        sanitized.session_id = validateStringField(value, 'session_id');
        break;

      case 'category':
        sanitized.category = validateStringField(value, 'category');
        break;

      case 'priority':
        sanitized.priority = validateNumericRange(value, 'priority', 0, 100, 50);
        break;

      case 'expires_at':
        sanitized.expires_at = validateTimestamp(value, 'expires_at');
        break;

      case 'related_ids':
        sanitized.related_ids = validateIdArray(value);
        break;

      case 'custom':
        // Allow custom object but validate its size
        if (isPlainObject(value)) {
          const customJson = JSON.stringify(value);
          if (customJson.length <= CONTENT_LIMITS.MAX_METADATA_SIZE / 2) {
            sanitized.custom = { ...sanitized.custom, ...value };
          } else {
            throw new ValidationError('custom', 'Custom metadata object is too large');
          }
        }
        break;

      default:
        // Should not reach here due to whitelist check above
        sanitized[key] = value;
    }
  }

  return sanitized;
}

/**
 * Validate tags array
 * @param {*} tags - Tags to validate
 * @returns {string[]} - Validated tags array
 * @throws {ValidationError}
 */
export function validateTags(tags) {
  if (tags === null || tags === undefined) {
    return [];
  }

  if (!isArray(tags)) {
    throw new ValidationError('tags', 'Tags must be an array', typeof tags);
  }

  if (tags.length > 50) {
    throw new ValidationError('tags', 'Too many tags (max 50)');
  }

  const validatedTags = [];
  for (let i = 0; i < tags.length; i++) {
    const tag = tags[i];
    if (!isString(tag)) {
      throw new ValidationError(`tags[${i}]`, 'Each tag must be a string', typeof tag);
    }
    const trimmed = tag.trim();
    if (trimmed.length > 100) {
      throw new ValidationError(`tags[${i}]`, 'Tag exceeds maximum length of 100 characters');
    }
    if (trimmed.length > 0) {
      validatedTags.push(trimmed);
    }
  }

  return validatedTags;
}

/**
 * Validate ID array
 * @param {*} ids - IDs to validate
 * @returns {number[]} - Validated IDs array
 * @throws {ValidationError}
 */
export function validateIdArray(ids) {
  if (ids === null || ids === undefined) {
    return [];
  }

  if (!isArray(ids)) {
    throw new ValidationError('related_ids', 'Related IDs must be an array', typeof ids);
  }

  if (ids.length > 100) {
    throw new ValidationError('related_ids', 'Too many related IDs (max 100)');
  }

  const validatedIds = [];
  for (let i = 0; i < ids.length; i++) {
    const id = validateNumericRange(
      ids[i],
      `related_ids[${i}]`,
      NUMERIC_LIMITS.MIN_ID,
      NUMERIC_LIMITS.MAX_ID,
      null
    );
    if (id !== null) {
      validatedIds.push(Math.floor(id));
    }
  }

  return validatedIds;
}

/**
 * Validate generic string field
 * @param {*} value - Value to validate
 * @param {string} fieldName - Field name for error messages
 * @returns {string} - Validated string
 * @throws {ValidationError}
 */
export function validateStringField(value, fieldName) {
  if (value === null || value === undefined) {
    return '';
  }

  if (!isString(value)) {
    throw new ValidationError(fieldName, 'Value must be a string', typeof value);
  }

  if (value.length > CONTENT_LIMITS.MAX_STRING_FIELD_LENGTH) {
    throw new ValidationError(
      fieldName,
      `Value exceeds maximum length of ${CONTENT_LIMITS.MAX_STRING_FIELD_LENGTH} characters`
    );
  }

  return value;
}

// ============================================================================
// FILTER VALIDATORS
// ============================================================================

/**
 * Validate query filters object
 * @param {*} filters - Filters to validate
 * @returns {object} - Validated filters
 * @throws {ValidationError}
 */
export function validateFilters(filters) {
  if (filters === null || filters === undefined) {
    return {};
  }

  if (!isPlainObject(filters)) {
    throw new ValidationError('filters', 'Filters must be an object', typeof filters);
  }

  const validated = {};

  // Importance filters
  if ('importance_min' in filters) {
    validated.importance_min = validateNumericRange(
      filters.importance_min,
      'filters.importance_min',
      NUMERIC_LIMITS.MIN_IMPORTANCE,
      NUMERIC_LIMITS.MAX_IMPORTANCE,
      null
    );
  }

  if ('importance_max' in filters) {
    validated.importance_max = validateNumericRange(
      filters.importance_max,
      'filters.importance_max',
      NUMERIC_LIMITS.MIN_IMPORTANCE,
      NUMERIC_LIMITS.MAX_IMPORTANCE,
      null
    );
  }

  // Emotional intensity filters
  if ('emotional_intensity_min' in filters) {
    validated.emotional_intensity_min = validateNumericRange(
      filters.emotional_intensity_min,
      'filters.emotional_intensity_min',
      NUMERIC_LIMITS.MIN_EMOTIONAL_INTENSITY,
      NUMERIC_LIMITS.MAX_EMOTIONAL_INTENSITY,
      null
    );
  }

  if ('emotional_intensity_max' in filters) {
    validated.emotional_intensity_max = validateNumericRange(
      filters.emotional_intensity_max,
      'filters.emotional_intensity_max',
      NUMERIC_LIMITS.MIN_EMOTIONAL_INTENSITY,
      NUMERIC_LIMITS.MAX_EMOTIONAL_INTENSITY,
      null
    );
  }

  // Timestamp filters
  if ('timestamp_after' in filters) {
    validated.timestamp_after = validateTimestamp(filters.timestamp_after, 'filters.timestamp_after');
  }

  if ('timestamp_before' in filters) {
    validated.timestamp_before = validateTimestamp(filters.timestamp_before, 'filters.timestamp_before');
  }

  // Content search filters
  if ('content_contains' in filters) {
    validated.content_contains = validateStringField(filters.content_contains, 'filters.content_contains');
    if (validated.content_contains.length > CONTENT_LIMITS.MAX_QUERY_LENGTH) {
      throw new ValidationError(
        'filters.content_contains',
        `Search term exceeds maximum length of ${CONTENT_LIMITS.MAX_QUERY_LENGTH}`
      );
    }
  }

  if ('context_contains' in filters) {
    validated.context_contains = validateStringField(filters.context_contains, 'filters.context_contains');
    if (validated.context_contains.length > CONTENT_LIMITS.MAX_QUERY_LENGTH) {
      throw new ValidationError(
        'filters.context_contains',
        `Search term exceeds maximum length of ${CONTENT_LIMITS.MAX_QUERY_LENGTH}`
      );
    }
  }

  // ID filter
  if ('id' in filters) {
    validated.id = validateId(filters.id);
  }

  // Cross-validation: min should not exceed max
  if (validated.importance_min !== undefined && validated.importance_max !== undefined) {
    if (validated.importance_min > validated.importance_max) {
      throw new ValidationError(
        'filters',
        'importance_min cannot be greater than importance_max'
      );
    }
  }

  if (validated.emotional_intensity_min !== undefined && validated.emotional_intensity_max !== undefined) {
    if (validated.emotional_intensity_min > validated.emotional_intensity_max) {
      throw new ValidationError(
        'filters',
        'emotional_intensity_min cannot be greater than emotional_intensity_max'
      );
    }
  }

  if (validated.timestamp_after !== undefined && validated.timestamp_before !== undefined) {
    if (validated.timestamp_after > validated.timestamp_before) {
      throw new ValidationError(
        'filters',
        'timestamp_after cannot be greater than timestamp_before'
      );
    }
  }

  return validated;
}

// ============================================================================
// OPTIONS VALIDATORS
// ============================================================================

/**
 * Validate query_layer options
 * @param {*} options - Options to validate
 * @returns {object} - Validated options
 * @throws {ValidationError}
 */
export function validateQueryOptions(options) {
  if (options === null || options === undefined) {
    return { limit: NUMERIC_LIMITS.DEFAULT_LIMIT };
  }

  if (!isPlainObject(options)) {
    throw new ValidationError('options', 'Options must be an object', typeof options);
  }

  const validated = {};

  // Validate limit
  if ('limit' in options) {
    validated.limit = validateLimit(options.limit);
  } else {
    validated.limit = NUMERIC_LIMITS.DEFAULT_LIMIT;
  }

  // Validate order_by (already sanitized in main code, but validate format here)
  if ('order_by' in options) {
    if (!isString(options.order_by)) {
      throw new ValidationError('options.order_by', 'order_by must be a string');
    }
    validated.order_by = options.order_by.trim();
  }

  // Validate filters
  if ('filters' in options) {
    validated.filters = validateFilters(options.filters);
  }

  // Legacy params support (deprecated but validated)
  if ('params' in options) {
    if (isArray(options.params)) {
      validated.params = options.params.slice(0, 10);  // Limit params count
    }
  }

  // Ignore deprecated 'where' field - log warning handled in main code
  if ('where' in options) {
    validated._deprecated_where_used = true;
  }

  return validated;
}

// ============================================================================
// COMPLETE INPUT VALIDATORS (for tool handlers)
// ============================================================================

/**
 * Validate 'remember' tool input
 */
export function validateRememberInput(args) {
  if (!isPlainObject(args)) {
    throw new ValidationError('args', 'Arguments must be an object');
  }

  return {
    content: validateContent(args.content),
    layer: validateLayer(args.layer, false),
    metadata: validateMetadata(args.metadata)
  };
}

/**
 * Validate 'recall' tool input
 */
export function validateRecallInput(args) {
  if (!isPlainObject(args)) {
    throw new ValidationError('args', 'Arguments must be an object');
  }

  return {
    query: validateQuery(args.query),
    layer: validateLayer(args.layer, false),
    limit: validateLimit(args.limit)
  };
}

/**
 * Validate 'query_layer' tool input
 */
export function validateQueryLayerInput(args) {
  if (!isPlainObject(args)) {
    throw new ValidationError('args', 'Arguments must be an object');
  }

  return {
    layer: validateLayer(args.layer, true),  // Layer is required for query_layer
    options: validateQueryOptions(args.options)
  };
}

/**
 * Validate 'save_to_layer' tool input
 */
export function validateSaveToLayerInput(args) {
  if (!isPlainObject(args)) {
    throw new ValidationError('args', 'Arguments must be an object');
  }

  return {
    layer: validateLayer(args.layer, true),  // Layer is required
    content: validateContent(args.content),
    metadata: validateMetadata(args.metadata)
  };
}

// ============================================================================
// EXPORT DEFAULT VALIDATOR OBJECT
// ============================================================================

export default {
  // Constants
  CONTENT_LIMITS,
  NUMERIC_LIMITS,
  VALID_LAYERS,
  VALID_METADATA_FIELDS,

  // Error class
  ValidationError,

  // Type checkers
  isString,
  isNumber,
  isInteger,
  isPlainObject,
  isArray,

  // Content validators
  validateContent,
  validateQuery,
  validateContext,

  // Layer validators
  validateLayer,

  // Numeric validators
  validateNumericRange,
  validateImportance,
  validateEmotionalIntensity,
  validateLimit,
  validateTimestamp,
  validateId,

  // Metadata validators
  validateMetadata,
  validateTags,
  validateIdArray,
  validateStringField,

  // Filter/Options validators
  validateFilters,
  validateQueryOptions,

  // Complete input validators
  validateRememberInput,
  validateRecallInput,
  validateQueryLayerInput,
  validateSaveToLayerInput
};
