/**
 * Unit Tests for index.js (Main Server Functions)
 * CASCADE Enterprise - Server Module Tests
 *
 * Created: January 22, 2026
 * Tests exported utilities and helper functions from the main server
 *
 * Note: These tests focus on utility functions and error handling classes.
 * Full integration tests would require mocking the database and MCP server.
 */

import assert from 'assert';

// Import utilities from index.js
// Note: Some functions are not directly exported, so we test what's available
import {
  // Error utilities
  CascadeError,
  DatabaseError,
  ConfigurationError,
  ErrorCodes,
  StatusCodes,
  sanitizeErrorMessage,
  handleError,
  createSuccessResponse,

  // Logger
  logger,
  StructuredLogger,
  LogLevel,
  AuditOperation

} from '../server/index.js';

// Import ValidationError from validation.js for comparison
import { ValidationError } from '../server/validation.js';

// ============================================================================
// TEST UTILITIES
// ============================================================================

let passCount = 0;
let failCount = 0;
const failures = [];

function test(description, fn) {
  try {
    fn();
    passCount++;
    console.log(`  PASS: ${description}`);
  } catch (error) {
    failCount++;
    failures.push({ description, error: error.message });
    console.log(`  FAIL: ${description}`);
    console.log(`        ${error.message}`);
  }
}

function testGroup(name, fn) {
  console.log(`\n=== ${name} ===`);
  fn();
}

// ============================================================================
// TESTS: ERROR CODES AND STATUS CODES
// ============================================================================

testGroup('Error Codes', () => {
  test('ErrorCodes has validation errors', () => {
    assert.strictEqual(ErrorCodes.VALIDATION_ERROR, 'VALIDATION_ERROR');
    assert.strictEqual(ErrorCodes.INVALID_INPUT, 'INVALID_INPUT');
    assert.strictEqual(ErrorCodes.INVALID_LAYER, 'INVALID_LAYER');
    assert.strictEqual(ErrorCodes.INVALID_CONTENT, 'INVALID_CONTENT');
    assert.strictEqual(ErrorCodes.INVALID_QUERY, 'INVALID_QUERY');
  });

  test('ErrorCodes has rate limiting error', () => {
    assert.strictEqual(ErrorCodes.RATE_LIMIT_EXCEEDED, 'RATE_LIMIT_EXCEEDED');
  });

  test('ErrorCodes has database errors', () => {
    assert.strictEqual(ErrorCodes.DATABASE_ERROR, 'DATABASE_ERROR');
    assert.strictEqual(ErrorCodes.CONNECTION_ERROR, 'CONNECTION_ERROR');
    assert.strictEqual(ErrorCodes.QUERY_ERROR, 'QUERY_ERROR');
    assert.strictEqual(ErrorCodes.WRITE_ERROR, 'WRITE_ERROR');
  });

  test('ErrorCodes has internal errors', () => {
    assert.strictEqual(ErrorCodes.INTERNAL_ERROR, 'INTERNAL_ERROR');
    assert.strictEqual(ErrorCodes.UNKNOWN_TOOL, 'UNKNOWN_TOOL');
    assert.strictEqual(ErrorCodes.CONFIGURATION_ERROR, 'CONFIGURATION_ERROR');
  });

  test('ErrorCodes is frozen', () => {
    assert(Object.isFrozen(ErrorCodes));
  });
});

testGroup('Status Codes', () => {
  test('StatusCodes has HTTP-like values', () => {
    assert.strictEqual(StatusCodes.OK, 200);
    assert.strictEqual(StatusCodes.BAD_REQUEST, 400);
    assert.strictEqual(StatusCodes.NOT_FOUND, 404);
    assert.strictEqual(StatusCodes.RATE_LIMITED, 429);
    assert.strictEqual(StatusCodes.INTERNAL_ERROR, 500);
    assert.strictEqual(StatusCodes.SERVICE_UNAVAILABLE, 503);
  });

  test('StatusCodes is frozen', () => {
    assert(Object.isFrozen(StatusCodes));
  });
});

// ============================================================================
// TESTS: CASCADE ERROR CLASS
// ============================================================================

testGroup('CascadeError Class', () => {
  test('CascadeError has correct default properties', () => {
    const error = new CascadeError('Test error');
    assert.strictEqual(error.name, 'CascadeError');
    assert.strictEqual(error.message, 'Test error');
    assert.strictEqual(error.code, ErrorCodes.INTERNAL_ERROR);
    assert.strictEqual(error.statusCode, StatusCodes.INTERNAL_ERROR);
    assert(error.timestamp > 0);
  });

  test('CascadeError accepts custom code and status', () => {
    const error = new CascadeError('Test', ErrorCodes.VALIDATION_ERROR, StatusCodes.BAD_REQUEST);
    assert.strictEqual(error.code, ErrorCodes.VALIDATION_ERROR);
    assert.strictEqual(error.statusCode, StatusCodes.BAD_REQUEST);
  });

  test('CascadeError stores details', () => {
    const error = new CascadeError('Test', ErrorCodes.DATABASE_ERROR, 500, { table: 'memories' });
    assert.deepStrictEqual(error.details, { table: 'memories' });
  });

  test('CascadeError toSafeJSON returns structured response', () => {
    const error = new CascadeError('Test error', ErrorCodes.DATABASE_ERROR, 500, { layer: 'identity' });
    const json = error.toSafeJSON();

    assert.strictEqual(json.success, false);
    assert.strictEqual(json.error.code, ErrorCodes.DATABASE_ERROR);
    assert.strictEqual(json.error.statusCode, 500);
    assert(json.error.timestamp > 0);
    assert(json.error.details);
  });

  test('CascadeError inherits from Error', () => {
    const error = new CascadeError('Test');
    assert(error instanceof Error);
    assert(error instanceof CascadeError);
  });
});

// ============================================================================
// TESTS: DATABASE ERROR CLASS
// ============================================================================

testGroup('DatabaseError Class', () => {
  test('DatabaseError has correct properties', () => {
    const error = new DatabaseError('Query failed', 'select');
    assert.strictEqual(error.name, 'DatabaseError');
    assert.strictEqual(error.message, 'Query failed');
    assert.strictEqual(error.operation, 'select');
    assert.strictEqual(error.code, ErrorCodes.DATABASE_ERROR);
  });

  test('DatabaseError inherits from CascadeError', () => {
    const error = new DatabaseError('Test');
    assert(error instanceof CascadeError);
    assert(error instanceof Error);
  });

  test('DatabaseError toSafeJSON includes operation', () => {
    const error = new DatabaseError('Failed', 'insert');
    const json = error.toSafeJSON();
    assert.strictEqual(json.error.operation, 'insert');
  });
});

// ============================================================================
// TESTS: CONFIGURATION ERROR CLASS
// ============================================================================

testGroup('ConfigurationError Class', () => {
  test('ConfigurationError has correct properties', () => {
    const error = new ConfigurationError('Missing config');
    assert.strictEqual(error.name, 'ConfigurationError');
    assert.strictEqual(error.code, ErrorCodes.CONFIGURATION_ERROR);
    assert.strictEqual(error.statusCode, StatusCodes.SERVICE_UNAVAILABLE);
  });

  test('ConfigurationError inherits from CascadeError', () => {
    const error = new ConfigurationError('Test');
    assert(error instanceof CascadeError);
  });
});

// ============================================================================
// TESTS: SANITIZE ERROR MESSAGE
// ============================================================================

testGroup('sanitizeErrorMessage Function', () => {
  test('sanitizeErrorMessage handles simple messages', () => {
    const result = sanitizeErrorMessage('Simple error message');
    assert.strictEqual(result, 'Simple error message');
  });

  test('sanitizeErrorMessage redacts Windows paths', () => {
    const result = sanitizeErrorMessage('Error in C:\\Users\\Pirate\\Desktop\\file.js');
    assert(result.includes('[REDACTED]'));
    assert(!result.includes('Pirate'));
  });

  test('sanitizeErrorMessage redacts Unix home paths', () => {
    const result = sanitizeErrorMessage('Error in /home/user/project/file.js');
    assert(result.includes('[REDACTED]'));
    assert(!result.includes('/home/user'));
  });

  test('sanitizeErrorMessage redacts internal IP addresses', () => {
    const result = sanitizeErrorMessage('Connection to 192.168.1.100 failed');
    assert(result.includes('[REDACTED]'));
    assert(!result.includes('192.168.1.100'));
  });

  test('sanitizeErrorMessage handles non-string input', () => {
    const result = sanitizeErrorMessage(null);
    assert.strictEqual(result, 'An error occurred');
  });

  test('sanitizeErrorMessage handles empty string', () => {
    const result = sanitizeErrorMessage('');
    assert.strictEqual(result, 'An error occurred');
  });

  test('sanitizeErrorMessage normalizes whitespace', () => {
    const result = sanitizeErrorMessage('Error   with   multiple   spaces');
    assert.strictEqual(result, 'Error with multiple spaces');
  });
});

// ============================================================================
// TESTS: HANDLE ERROR
// ============================================================================

testGroup('handleError Function', () => {
  test('handleError handles CascadeError', () => {
    const error = new CascadeError('Test cascade error', ErrorCodes.DATABASE_ERROR);
    const result = handleError(error, 'test_tool');

    assert(result.isError);
    assert(result.content[0].type === 'text');

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.success, false);
    assert.strictEqual(parsed.error.code, ErrorCodes.DATABASE_ERROR);
    assert.strictEqual(parsed.error.tool, 'test_tool');
  });

  test('handleError handles ValidationError', () => {
    const error = new ValidationError('field', 'invalid value');
    const result = handleError(error, 'remember');

    assert(result.isError);

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.success, false);
    assert.strictEqual(parsed.error.code, ErrorCodes.VALIDATION_ERROR);
    assert.strictEqual(parsed.error.statusCode, StatusCodes.BAD_REQUEST);
    assert.strictEqual(parsed.error.field, 'field');
  });

  test('handleError handles generic Error', () => {
    const error = new Error('Generic error');
    const result = handleError(error, 'recall');

    assert(result.isError);

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.success, false);
    assert.strictEqual(parsed.error.code, ErrorCodes.INTERNAL_ERROR);
  });

  test('handleError handles SQLite errors', () => {
    const error = new Error('Database locked');
    error.code = 'SQLITE_BUSY';
    const result = handleError(error, 'save_to_layer');

    assert(result.isError);

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.error.code, ErrorCodes.DATABASE_ERROR);
    assert.strictEqual(parsed.error.details.sqliteCode, 'SQLITE_BUSY');
  });

  test('handleError adds tool name to response', () => {
    const error = new Error('Test');
    const result = handleError(error, 'my_tool');

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.error.tool, 'my_tool');
  });
});

// ============================================================================
// TESTS: CREATE SUCCESS RESPONSE
// ============================================================================

testGroup('createSuccessResponse Function', () => {
  test('createSuccessResponse creates proper format', () => {
    const data = { id: 1, content: 'test' };
    const result = createSuccessResponse(data, 'remember');

    assert(!result.isError);
    assert.strictEqual(result.content[0].type, 'text');

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.success, true);
    assert.strictEqual(parsed.tool, 'remember');
    assert.deepStrictEqual(parsed.data, data);
    assert(parsed.timestamp > 0);
  });

  test('createSuccessResponse handles array data', () => {
    const data = [{ id: 1 }, { id: 2 }];
    const result = createSuccessResponse(data, 'recall');

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.success, true);
    assert(Array.isArray(parsed.data));
    assert.strictEqual(parsed.data.length, 2);
  });

  test('createSuccessResponse handles empty data', () => {
    const result = createSuccessResponse({}, 'get_status');

    const parsed = JSON.parse(result.content[0].text);
    assert.strictEqual(parsed.success, true);
    assert.deepStrictEqual(parsed.data, {});
  });
});

// ============================================================================
// TESTS: STRUCTURED LOGGER
// ============================================================================

testGroup('StructuredLogger Class', () => {
  test('StructuredLogger creates instance with defaults', () => {
    const testLogger = new StructuredLogger();
    assert(testLogger.sessionId);
    assert(testLogger.serviceName);
    assert(testLogger.version);
  });

  test('StructuredLogger accepts custom options', () => {
    const testLogger = new StructuredLogger({
      serviceName: 'test-service',
      version: '1.0.0',
      minLevel: 'warn'
    });
    assert.strictEqual(testLogger.serviceName, 'test-service');
    assert.strictEqual(testLogger.version, '1.0.0');
    assert.strictEqual(testLogger.minLevel.name, 'warn');
  });

  test('StructuredLogger generates unique session IDs', () => {
    const logger1 = new StructuredLogger();
    const logger2 = new StructuredLogger();
    assert.notStrictEqual(logger1.sessionId, logger2.sessionId);
  });

  test('StructuredLogger request counter increments', () => {
    const testLogger = new StructuredLogger();
    const id1 = testLogger._generateRequestId();
    const id2 = testLogger._generateRequestId();
    assert.notStrictEqual(id1, id2);
    assert(testLogger.requestCounter >= 2);
  });

  test('StructuredLogger getAuditStats returns proper structure', () => {
    const testLogger = new StructuredLogger();
    const stats = testLogger.getAuditStats();

    assert(stats.sessionId);
    assert(typeof stats.requestCount === 'number');
    assert(typeof stats.pendingAuditEntries === 'number');
    assert(typeof stats.auditEnabled === 'boolean');
  });

  test('StructuredLogger child logger inherits settings', () => {
    const parent = new StructuredLogger({ serviceName: 'parent' });
    const child = parent.child({ component: 'child' });

    assert.strictEqual(child.serviceName, 'parent');
    assert.strictEqual(child.sessionId, parent.sessionId);
  });
});

// ============================================================================
// TESTS: LOG LEVELS
// ============================================================================

testGroup('Log Levels', () => {
  test('LogLevel has all expected levels', () => {
    assert(LogLevel.DEBUG);
    assert(LogLevel.INFO);
    assert(LogLevel.WARN);
    assert(LogLevel.ERROR);
    assert(LogLevel.AUDIT);
  });

  test('LogLevel has proper priority ordering', () => {
    assert(LogLevel.DEBUG.priority < LogLevel.INFO.priority);
    assert(LogLevel.INFO.priority < LogLevel.WARN.priority);
    assert(LogLevel.WARN.priority < LogLevel.ERROR.priority);
    assert(LogLevel.ERROR.priority < LogLevel.AUDIT.priority);
  });

  test('LogLevel has color codes', () => {
    assert(LogLevel.DEBUG.color);
    assert(LogLevel.INFO.color);
    assert(LogLevel.WARN.color);
    assert(LogLevel.ERROR.color);
    assert(LogLevel.AUDIT.color);
  });

  test('LogLevel is frozen', () => {
    assert(Object.isFrozen(LogLevel));
  });
});

// ============================================================================
// TESTS: AUDIT OPERATIONS
// ============================================================================

testGroup('Audit Operations', () => {
  test('AuditOperation has memory operations', () => {
    assert.strictEqual(AuditOperation.MEMORY_SAVE, 'MEMORY_SAVE');
    assert.strictEqual(AuditOperation.MEMORY_RECALL, 'MEMORY_RECALL');
    assert.strictEqual(AuditOperation.MEMORY_QUERY, 'MEMORY_QUERY');
    assert.strictEqual(AuditOperation.MEMORY_DELETE, 'MEMORY_DELETE');
  });

  test('AuditOperation has connection operations', () => {
    assert.strictEqual(AuditOperation.CONNECTION_OPEN, 'CONNECTION_OPEN');
    assert.strictEqual(AuditOperation.CONNECTION_CLOSE, 'CONNECTION_CLOSE');
  });

  test('AuditOperation has server operations', () => {
    assert.strictEqual(AuditOperation.SERVER_START, 'SERVER_START');
    assert.strictEqual(AuditOperation.SERVER_STOP, 'SERVER_STOP');
  });

  test('AuditOperation has security operations', () => {
    assert.strictEqual(AuditOperation.RATE_LIMIT_HIT, 'RATE_LIMIT_HIT');
    assert.strictEqual(AuditOperation.VALIDATION_FAIL, 'VALIDATION_FAIL');
  });

  test('AuditOperation is frozen', () => {
    assert(Object.isFrozen(AuditOperation));
  });
});

// ============================================================================
// TESTS: GLOBAL LOGGER INSTANCE
// ============================================================================

testGroup('Global Logger Instance', () => {
  test('logger is a StructuredLogger instance', () => {
    assert(logger instanceof StructuredLogger);
  });

  test('logger has expected service name', () => {
    assert.strictEqual(logger.serviceName, 'cascade-memory');
  });

  test('logger has expected version', () => {
    assert(logger.version === '2.2.0');
  });

  test('logger has logging methods', () => {
    assert(typeof logger.debug === 'function');
    assert(typeof logger.info === 'function');
    assert(typeof logger.warn === 'function');
    assert(typeof logger.error === 'function');
    assert(typeof logger.audit === 'function');
  });
});

// ============================================================================
// TESTS: ERROR RESPONSE FORMAT CONSISTENCY
// ============================================================================

testGroup('Error Response Format Consistency', () => {
  test('All error types produce consistent JSON structure', () => {
    const errors = [
      new CascadeError('Cascade error'),
      new DatabaseError('Database error'),
      new ConfigurationError('Config error'),
      new ValidationError('field', 'Validation error')
    ];

    for (const error of errors) {
      const result = handleError(error, 'test');
      const parsed = JSON.parse(result.content[0].text);

      // All should have these fields
      assert.strictEqual(parsed.success, false);
      assert(parsed.error);
      assert(parsed.error.code);
      assert(parsed.error.message);
      assert(parsed.error.statusCode);
      assert(parsed.error.timestamp);
      assert(parsed.error.tool);
    }
  });

  test('Error responses are valid JSON', () => {
    const error = new Error('Test error with special chars: "quotes" and \\backslash');
    const result = handleError(error, 'test');

    // Should not throw
    assert.doesNotThrow(() => JSON.parse(result.content[0].text));
  });
});

// ============================================================================
// SUMMARY
// ============================================================================

console.log('\n' + '='.repeat(60));
console.log('TEST SUMMARY');
console.log('='.repeat(60));
console.log(`Total: ${passCount + failCount}`);
console.log(`Passed: ${passCount}`);
console.log(`Failed: ${failCount}`);

if (failures.length > 0) {
  console.log('\nFailures:');
  failures.forEach((f, i) => {
    console.log(`  ${i + 1}. ${f.description}`);
    console.log(`     Error: ${f.error}`);
  });
  process.exit(1);
} else {
  console.log('\nAll tests passed!');
  process.exit(0);
}
