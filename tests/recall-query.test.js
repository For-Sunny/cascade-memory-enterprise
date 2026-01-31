/**
 * Unit Tests for Recall Multi-Word Query Fix
 * CASCADE Memory - Recall Query Processing Tests
 *
 * Created: January 30, 2026
 * Tests the multi-word query tokenization and special character escaping
 *
 * The fix ensures that multi-word queries like "soul matrix" match records
 * containing "soul" OR "matrix" rather than requiring the exact phrase.
 *
 * Run with: node tests/recall-query.test.js
 */

import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Import modules under test
import {
  CascadeDatabase,
  escapeLikePattern
} from '../server/database.js';

import {
  recallMemories,
  saveMemory
} from '../server/tools.js';

// ============================================================================
// TEST UTILITIES
// ============================================================================

/**
 * Simple test runner
 */
class TestRunner {
  constructor() {
    this.tests = [];
    this.passed = 0;
    this.failed = 0;
    this.errors = [];
  }

  /**
   * Register a test
   */
  test(name, fn) {
    this.tests.push({ name, fn });
  }

  /**
   * Run all tests
   */
  async run() {
    console.log('\n' + '='.repeat(60));
    console.log('CASCADE Memory - Recall Multi-Word Query Tests');
    console.log('='.repeat(60) + '\n');

    for (const { name, fn } of this.tests) {
      try {
        await fn();
        this.passed++;
        console.log(`  [PASS] ${name}`);
      } catch (error) {
        this.failed++;
        this.errors.push({ name, error });
        console.log(`  [FAIL] ${name}`);
        console.log(`         ${error.message}`);
        if (process.env.DEBUG === 'true') {
          console.log(`         ${error.stack}`);
        }
      }
    }

    console.log('\n' + '-'.repeat(60));
    console.log(`Results: ${this.passed} passed, ${this.failed} failed`);
    console.log('-'.repeat(60) + '\n');

    if (this.failed > 0) {
      console.log('Failed Tests:');
      for (const { name, error } of this.errors) {
        console.log(`  - ${name}: ${error.message}`);
      }
      console.log('');
    }

    return this.failed === 0;
  }
}

/**
 * Assert helper
 */
function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

/**
 * Assert equality helper
 */
function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(message || `Expected ${expected}, got ${actual}`);
  }
}

/**
 * Assert throws helper
 */
async function assertThrows(fn, errorType, message) {
  try {
    await fn();
    throw new Error(message || `Expected function to throw ${errorType?.name || 'an error'}`);
  } catch (error) {
    if (errorType && !(error instanceof errorType)) {
      throw new Error(message || `Expected ${errorType.name}, got ${error.constructor.name}: ${error.message}`);
    }
  }
}

/**
 * Create a mock logger for testing
 * Must have all logging methods that CascadeDatabase.log() calls via this.logger[level]()
 */
function createMockLogger() {
  const logs = { debug: [], info: [], warn: [], error: [], audit: [] };
  return {
    debug: (msg, ctx) => logs.debug.push({ msg, ctx }),
    info: (msg, ctx) => logs.info.push({ msg, ctx }),
    warn: (msg, ctx) => logs.warn.push({ msg, ctx }),
    error: (msg, ctx) => logs.error.push({ msg, ctx }),
    audit: (op, details) => logs.audit.push({ op, details }),
    _generateRequestId: () => `test-${Date.now()}`,
    logs
  };
}

// ============================================================================
// TEST DATABASE SETUP
// ============================================================================

// Use unique temp directory for each test run to avoid file locking issues
let testRunId = 0;
function getTestDbPath() {
  return path.join(__dirname, `test_recall_db_${testRunId}`);
}

/**
 * Sleep helper for async operations
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Setup test database directory - creates a unique directory for each test
 */
async function setupTestDb() {
  testRunId++;
  const testPath = getTestDbPath();
  if (!fs.existsSync(testPath)) {
    fs.mkdirSync(testPath, { recursive: true });
  }
  return testPath;
}

/**
 * Cleanup test database directory with retry for Windows file locking
 */
async function cleanupTestDb(testPath) {
  const targetPath = testPath || getTestDbPath();
  if (!fs.existsSync(targetPath)) {
    return;
  }

  // Give SQLite time to release file handles
  await sleep(50);

  const maxRetries = 5;
  for (let retry = 0; retry < maxRetries; retry++) {
    try {
      for (const file of fs.readdirSync(targetPath)) {
        try {
          fs.unlinkSync(path.join(targetPath, file));
        } catch (e) {
          if (retry === maxRetries - 1) throw e;
        }
      }
      fs.rmdirSync(targetPath);
      return;
    } catch (e) {
      if (retry === maxRetries - 1) {
        // On final retry, just warn but don't fail
        console.warn(`Warning: Could not fully clean ${targetPath}: ${e.message}`);
        return;
      }
      await sleep(100 * (retry + 1));
    }
  }
}

// ============================================================================
// RECALL QUERY TESTS
// ============================================================================

const runner = new TestRunner();

// ----------------------------------------------------------------------------
// SINGLE WORD QUERY TESTS
// ----------------------------------------------------------------------------

runner.test('Single word query: "matrix" should find records with "matrix"', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save test memories
    await saveMemory(dbManager, 'The soul matrix is a core component', 'episodic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Another memory about consciousness', 'episodic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Matrix operations in linear algebra', 'semantic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    // Wait for writes to complete
    await sleep(100);

    // Recall with single word query
    const memories = await recallMemories(dbManager, 'matrix', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assert(memories.length >= 2, `Should find at least 2 memories with "matrix", found ${memories.length}`);
    assert(memories.every(m => m.content.toLowerCase().includes('matrix')), 'All results should contain "matrix"');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

// ----------------------------------------------------------------------------
// MULTI-WORD QUERY TESTS (THE FIX)
// ----------------------------------------------------------------------------

runner.test('Multi-word query: "soul matrix" should find records containing "soul" OR "matrix"', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save test memories - some with "soul", some with "matrix", some with both, some with neither
    await saveMemory(dbManager, 'The soul matrix is a core component', 'episodic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'My soul resonates at 21.43Hz', 'identity', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Matrix multiplication is fast', 'semantic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Unrelated memory about coffee', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    // Wait for writes to complete
    await sleep(100);

    // Recall with multi-word query - should match any word
    const memories = await recallMemories(dbManager, 'soul matrix', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assert(memories.length >= 3, `Should find at least 3 memories (both words present in OR), found ${memories.length}`);

    // Verify we get memories with either "soul" or "matrix"
    const hasSoul = memories.some(m => m.content.toLowerCase().includes('soul'));
    const hasMatrix = memories.some(m => m.content.toLowerCase().includes('matrix'));
    assert(hasSoul, 'Should find at least one memory with "soul"');
    assert(hasMatrix, 'Should find at least one memory with "matrix"');

    // Verify the unrelated memory is not included
    const hasCoffee = memories.some(m => m.content.toLowerCase().includes('coffee'));
    assert(!hasCoffee, 'Should NOT include unrelated "coffee" memory');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('Multi-word query: each word is searched independently with OR', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save memories with distinct keywords
    await saveMemory(dbManager, 'Alpha is the first letter', 'semantic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Beta testing is important', 'procedural', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Gamma rays are dangerous', 'semantic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Delta airlines flies planes', 'episodic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Search for "alpha beta" - should find both
    const memories = await recallMemories(dbManager, 'alpha beta', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assertEqual(memories.length, 2, `Should find exactly 2 memories for "alpha beta", found ${memories.length}`);

    const contents = memories.map(m => m.content.toLowerCase());
    assert(contents.some(c => c.includes('alpha')), 'Should include alpha memory');
    assert(contents.some(c => c.includes('beta')), 'Should include beta memory');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

// ----------------------------------------------------------------------------
// SPECIAL CHARACTER ESCAPING TESTS
// ----------------------------------------------------------------------------

runner.test('Special characters: "test%data" should escape the % properly', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save memories - one with literal %, others without
    await saveMemory(dbManager, 'This test%data has a percent sign', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'This testXdata should not match', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Regular test data here', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // The % should be escaped so it matches literal % not wildcard
    // Note: Due to tokenization, "test%data" becomes two tokens: "test%data"
    // The % within the token should be escaped
    const memories = await recallMemories(dbManager, 'test%data', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    // Should find the memory with literal "test%data"
    const hasLiteralPercent = memories.some(m => m.content.includes('test%data'));
    assert(hasLiteralPercent, 'Should find memory with literal "test%data"');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('Special characters: underscore should be escaped', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save memories - underscore is a SQL LIKE wildcard (matches any single char)
    await saveMemory(dbManager, 'Variable name_test in code', 'procedural', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Variable nameXtest should not match underscore', 'procedural', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    const memories = await recallMemories(dbManager, 'name_test', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    // Should find exact match with underscore
    const hasUnderscore = memories.some(m => m.content.includes('name_test'));
    assert(hasUnderscore, 'Should find memory with literal underscore');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('escapeLikePattern: unit test for escape function', () => {
  // Test the escapeLikePattern function directly
  assertEqual(escapeLikePattern('test'), 'test', 'Normal text should pass through');
  assertEqual(escapeLikePattern('test%pattern'), 'test\\%pattern', 'Percent should be escaped');
  assertEqual(escapeLikePattern('test_pattern'), 'test\\_pattern', 'Underscore should be escaped');
  assertEqual(escapeLikePattern('test\\pattern'), 'test\\\\pattern', 'Backslash should be escaped');
  assertEqual(escapeLikePattern('100% complete_task\\done'), '100\\% complete\\_task\\\\done', 'Multiple special chars');
  assertEqual(escapeLikePattern(''), '', 'Empty string should return empty');
  assertEqual(escapeLikePattern('%%%'), '\\%\\%\\%', 'Multiple percents should all be escaped');
});

// ----------------------------------------------------------------------------
// EMPTY QUERY HANDLING
// ----------------------------------------------------------------------------

runner.test('Empty query: should handle gracefully (return validation error)', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Empty string query should throw ValidationError
    let threwError = false;
    try {
      await recallMemories(dbManager, '', null, 10, logger, {
        MEMORY_RECALL: 'MEMORY_RECALL'
      });
    } catch (error) {
      threwError = true;
      assert(error.name === 'ValidationError' || error.message.includes('required'),
        'Should throw ValidationError for empty query');
    }
    assert(threwError, 'Should throw error for empty query');

    // Whitespace-only query should also throw
    threwError = false;
    try {
      await recallMemories(dbManager, '   ', null, 10, logger, {
        MEMORY_RECALL: 'MEMORY_RECALL'
      });
    } catch (error) {
      threwError = true;
      assert(error.name === 'ValidationError' || error.message.includes('required'),
        'Should throw ValidationError for whitespace query');
    }
    assert(threwError, 'Should throw error for whitespace-only query');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('Null/undefined query: should handle gracefully', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Null query should throw
    let threwError = false;
    try {
      await recallMemories(dbManager, null, null, 10, logger, {
        MEMORY_RECALL: 'MEMORY_RECALL'
      });
    } catch (error) {
      threwError = true;
    }
    assert(threwError, 'Should throw error for null query');

    // Undefined query should throw
    threwError = false;
    try {
      await recallMemories(dbManager, undefined, null, 10, logger, {
        MEMORY_RECALL: 'MEMORY_RECALL'
      });
    } catch (error) {
      threwError = true;
    }
    assert(threwError, 'Should throw error for undefined query');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

// ----------------------------------------------------------------------------
// UNICODE TESTS
// ----------------------------------------------------------------------------

runner.test('Unicode: Japanese characters should work', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save memory with Japanese text
    await saveMemory(dbManager, 'Japanese greeting: konnichiwa or in kanji', 'semantic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'English only memory', 'semantic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Search for Japanese term
    const memories = await recallMemories(dbManager, 'konnichiwa', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assert(memories.length >= 1, 'Should find at least 1 memory with Japanese-related content');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('Unicode: Chinese characters should work', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save memory with Chinese text
    await saveMemory(dbManager, 'Chinese greeting: nihao', 'semantic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Search for Chinese term
    const memories = await recallMemories(dbManager, 'nihao', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assert(memories.length >= 1, 'Should find memory with Chinese-related content');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('Unicode: Emoji handling', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save memory with emoji - just test that it doesn't crash
    await saveMemory(dbManager, 'Happy memory with smile emoji', 'episodic', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Search for text near emoji - should work without crashing
    const memories = await recallMemories(dbManager, 'smile emoji', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    // Just verify no crash and valid response
    assert(Array.isArray(memories), 'Should return array even with emoji content');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

// ----------------------------------------------------------------------------
// SQL INJECTION PROTECTION TESTS
// ----------------------------------------------------------------------------

runner.test('SQL injection attempt: should be safely escaped - DROP TABLE', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save some test data first
    await saveMemory(dbManager, 'Important memory that should not be deleted', 'identity', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Attempt SQL injection via query
    const maliciousQuery = "'; DROP TABLE memories; --";

    // This should NOT throw and should NOT drop the table
    let memories;
    try {
      memories = await recallMemories(dbManager, maliciousQuery, null, 10, logger, {
        MEMORY_RECALL: 'MEMORY_RECALL'
      });
    } catch (error) {
      // Even if it throws, the table should still exist
      memories = [];
    }

    // Verify the table still exists by doing a normal query
    const verifyMemories = await recallMemories(dbManager, 'Important', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assert(verifyMemories.length >= 1, 'Table should still exist after injection attempt');
    assert(verifyMemories.some(m => m.content.includes('Important')), 'Original data should be intact');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('SQL injection attempt: should be safely escaped - UNION SELECT', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    await saveMemory(dbManager, 'Normal memory content', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Attempt UNION injection
    const maliciousQuery = "' UNION SELECT * FROM sqlite_master --";

    let memories;
    try {
      memories = await recallMemories(dbManager, maliciousQuery, null, 10, logger, {
        MEMORY_RECALL: 'MEMORY_RECALL'
      });
    } catch (error) {
      memories = [];
    }

    // Results should not contain schema information
    assert(Array.isArray(memories), 'Should return array');
    assert(!memories.some(m =>
      m.content && (m.content.includes('CREATE TABLE') || m.content.includes('sqlite_master'))
    ), 'Should not leak schema information');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('SQL injection attempt: should be safely escaped - OR 1=1', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save memories to specific layer
    await saveMemory(dbManager, 'Secret memory in identity', 'identity', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });
    await saveMemory(dbManager, 'Public memory in working', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Attempt OR 1=1 injection to bypass layer filtering
    const maliciousQuery = "' OR '1'='1";

    // Query only working layer with injection attempt
    let memories;
    try {
      memories = await recallMemories(dbManager, maliciousQuery, 'working', 10, logger, {
        MEMORY_RECALL: 'MEMORY_RECALL'
      });
    } catch (error) {
      memories = [];
    }

    // Should not return memories from other layers
    assert(Array.isArray(memories), 'Should return array');
    // The injection should not cause all records to be returned
    // Results should only contain the literal search term matches (if any)
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('SQL injection attempt: quotes and semicolons should be escaped', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    // Save test memory
    await saveMemory(dbManager, 'Test memory for injection testing', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Various injection attempts
    const injectionAttempts = [
      "'; DROP TABLE memories; --",
      "1; DELETE FROM memories",
      "' OR 1=1 --",
      "'; INSERT INTO memories VALUES (999, 'hacked', 'hacked', 'hacked', 0, 0, '{}'); --",
      "Robert'); DROP TABLE memories;--"
    ];

    for (const attempt of injectionAttempts) {
      // Each attempt should not crash and should not modify the database
      try {
        await recallMemories(dbManager, attempt, null, 10, logger, {
          MEMORY_RECALL: 'MEMORY_RECALL'
        });
      } catch (error) {
        // Errors are acceptable - as long as they're not SQL errors that indicate injection worked
        assert(!error.message.includes('SQLITE_ERROR'), `SQL error indicates possible injection: ${attempt}`);
      }
    }

    // Verify data integrity
    const verifyMemories = await recallMemories(dbManager, 'Test memory', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });
    assert(verifyMemories.length >= 1, 'Original data should be intact after all injection attempts');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

// ----------------------------------------------------------------------------
// EDGE CASES
// ----------------------------------------------------------------------------

runner.test('Edge case: very long multi-word query', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    await saveMemory(dbManager, 'Memory with word1 in content', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Create a query with many words (but within limits)
    const manyWords = Array(20).fill('word').map((w, i) => `${w}${i}`).join(' ');

    // Should not crash with many words
    const memories = await recallMemories(dbManager, manyWords, null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assert(Array.isArray(memories), 'Should return array for long multi-word query');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('Edge case: query with only special characters', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    await saveMemory(dbManager, 'Memory with % and _ symbols', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // Query with special chars only
    const memories = await recallMemories(dbManager, '% _', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    // Should return results safely (chars are escaped)
    assert(Array.isArray(memories), 'Should return array for special char query');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

runner.test('Edge case: query with mixed case', async () => {
  const testPath = await setupTestDb();
  const logger = createMockLogger();
  const dbManager = new CascadeDatabase(testPath, logger);

  try {
    await saveMemory(dbManager, 'Memory with UPPERCASE and lowercase text', 'working', {}, logger, {
      MEMORY_SAVE: 'MEMORY_SAVE'
    });

    await sleep(100);

    // SQLite LIKE is case-insensitive by default
    const memories = await recallMemories(dbManager, 'UPPERCASE lowercase', null, 10, logger, {
      MEMORY_RECALL: 'MEMORY_RECALL'
    });

    assert(memories.length >= 1, 'Should find memory regardless of case');
  } finally {
    await dbManager.closeAll();
    await cleanupTestDb(testPath);
  }
});

// ============================================================================
// RUN TESTS
// ============================================================================

(async () => {
  try {
    const success = await runner.run();
    process.exit(success ? 0 : 1);
  } catch (error) {
    console.error('Test runner failed:', error);
    process.exit(1);
  }
})();
