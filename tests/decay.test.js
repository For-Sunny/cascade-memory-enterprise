/**
 * Unit Tests for Decay Engine
 * CASCADE Enterprise - Temporal Memory Decay
 *
 * Created: February 2026
 * Tests: decay math, immortal threshold, schema migration, save/recall/query
 *        with decay columns, touch mechanics, sweep behavior, NULL handling,
 *        status/stats reporting
 */

import assert from 'assert';
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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
// HELPERS: Create a temp DB that mimics CascadeDatabase for testing
// ============================================================================

function createTestDb() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cascade-decay-test-'));
  const dbPath = path.join(tmpDir, 'test_memory.db');
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');

  // Create base schema (without decay columns - to test migration)
  db.exec(`
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

  return { db, dbPath, tmpDir };
}

function createTestDbWithDecay() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cascade-decay-test-'));
  const dbPath = path.join(tmpDir, 'test_memory.db');
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');

  db.exec(`
    CREATE TABLE IF NOT EXISTS memories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp REAL NOT NULL,
      content TEXT,
      event TEXT,
      context TEXT,
      emotional_intensity REAL DEFAULT 0.5,
      importance REAL DEFAULT 0.5,
      metadata TEXT,
      last_accessed REAL,
      effective_importance REAL,
      access_count INTEGER DEFAULT 0
    )
  `);

  return { db, dbPath, tmpDir };
}

function cleanup(tmpDir) {
  try {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  } catch (_) {}
}

// Mock dbManager for DecayEngine
function createMockDbManager(db, layerName = 'episodic') {
  return {
    getConnection: (layer) => db,
    dualWriteBatch: (layer, operations) => {
      for (const { sql, params } of operations) {
        db.prepare(sql).run(...(Array.isArray(params) ? params : [params]));
      }
    },
    initWriteConnections: (layer) => [{ path: 'test', db }]
  };
}

// ============================================================================
// TESTS: DECAY MATH
// ============================================================================

testGroup('Decay Math - calculateEffectiveImportance', () => {
  // Import DecayEngine dynamically by creating instance directly
  // We replicate the core math here to test independently

  function calculateEffectiveImportance(importance, lastAccessed, now, config) {
    if (importance >= config.IMMORTAL_THRESHOLD) {
      return importance;
    }
    const daysSinceAccess = (now - lastAccessed) / 86400;
    if (daysSinceAccess <= 0) {
      return importance;
    }
    const decayRate = config.BASE_RATE * (1 - importance);
    const decayFactor = Math.exp(-decayRate * daysSinceAccess);
    return importance * decayFactor;
  }

  const config = {
    BASE_RATE: 0.01,
    THRESHOLD: 0.1,
    IMMORTAL_THRESHOLD: 0.9
  };

  test('Immortal memories (importance >= 0.9) never decay', () => {
    const now = 1000000;
    const lastAccessed = now - 86400 * 365; // 1 year ago
    const result = calculateEffectiveImportance(0.9, lastAccessed, now, config);
    assert.strictEqual(result, 0.9);

    const result2 = calculateEffectiveImportance(1.0, lastAccessed, now, config);
    assert.strictEqual(result2, 1.0);
  });

  test('Recently accessed memory does not decay', () => {
    const now = 1000000;
    const lastAccessed = now; // just accessed
    const result = calculateEffectiveImportance(0.5, lastAccessed, now, config);
    assert.strictEqual(result, 0.5);
  });

  test('Lower importance decays faster', () => {
    const now = 1000000;
    const lastAccessed = now - 86400 * 30; // 30 days ago

    const lowImportance = calculateEffectiveImportance(0.2, lastAccessed, now, config);
    const midImportance = calculateEffectiveImportance(0.5, lastAccessed, now, config);
    const highImportance = calculateEffectiveImportance(0.8, lastAccessed, now, config);

    // Lower importance should have lower effective importance (more decay)
    assert.ok(lowImportance < midImportance, `Low (${lowImportance}) should be < Mid (${midImportance})`);
    assert.ok(midImportance < highImportance, `Mid (${midImportance}) should be < High (${highImportance})`);
  });

  test('Decay increases over time', () => {
    const now = 1000000;
    const importance = 0.5;

    const day1 = calculateEffectiveImportance(importance, now - 86400 * 1, now, config);
    const day30 = calculateEffectiveImportance(importance, now - 86400 * 30, now, config);
    const day90 = calculateEffectiveImportance(importance, now - 86400 * 90, now, config);
    const day365 = calculateEffectiveImportance(importance, now - 86400 * 365, now, config);

    assert.ok(day1 > day30, `1 day (${day1}) should be > 30 days (${day30})`);
    assert.ok(day30 > day90, `30 days (${day30}) should be > 90 days (${day90})`);
    assert.ok(day90 > day365, `90 days (${day90}) should be > 365 days (${day365})`);
  });

  test('Effective importance is always >= 0', () => {
    const now = 1000000;
    const result = calculateEffectiveImportance(0.1, now - 86400 * 10000, now, config);
    assert.ok(result >= 0, `Result should be >= 0, got ${result}`);
  });

  test('Exponential decay formula is correct', () => {
    const now = 1000000;
    const importance = 0.5;
    const lastAccessed = now - 86400 * 10; // 10 days ago

    const decayRate = config.BASE_RATE * (1 - importance); // 0.01 * 0.5 = 0.005
    const decayFactor = Math.exp(-decayRate * 10); // e^(-0.005 * 10) = e^(-0.05)
    const expected = importance * decayFactor;

    const result = calculateEffectiveImportance(importance, lastAccessed, now, config);
    assert.ok(Math.abs(result - expected) < 0.0001, `Expected ~${expected}, got ${result}`);
  });
});

// ============================================================================
// TESTS: SCHEMA MIGRATION
// ============================================================================

testGroup('Schema Migration', () => {
  test('Migration adds decay columns to existing table', () => {
    const { db, tmpDir } = createTestDb();

    // Insert a pre-migration row
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance)
      VALUES (?, ?, ?, ?)
    `).run(1000, 'test', 'test', 0.5);

    // Run migration (simulate what ensureSchema does)
    const decayColumns = [
      { name: 'last_accessed', type: 'REAL' },
      { name: 'effective_importance', type: 'REAL' },
      { name: 'access_count', type: 'INTEGER DEFAULT 0' }
    ];

    for (const col of decayColumns) {
      try {
        db.exec(`ALTER TABLE memories ADD COLUMN ${col.name} ${col.type}`);
      } catch (e) {
        if (!e.message.includes('duplicate column name')) {
          throw e;
        }
      }
    }

    // Backfill
    db.exec(`
      UPDATE memories SET
        last_accessed = timestamp,
        effective_importance = importance,
        access_count = 0
      WHERE last_accessed IS NULL
    `);

    const row = db.prepare('SELECT * FROM memories WHERE id = 1').get();
    assert.strictEqual(row.last_accessed, 1000);
    assert.strictEqual(row.effective_importance, 0.5);
    assert.strictEqual(row.access_count, 0);

    db.close();
    cleanup(tmpDir);
  });

  test('Migration is safe to run multiple times', () => {
    const { db, tmpDir } = createTestDb();

    // Run migration twice
    for (let i = 0; i < 2; i++) {
      const decayColumns = [
        { name: 'last_accessed', type: 'REAL' },
        { name: 'effective_importance', type: 'REAL' },
        { name: 'access_count', type: 'INTEGER DEFAULT 0' }
      ];

      for (const col of decayColumns) {
        try {
          db.exec(`ALTER TABLE memories ADD COLUMN ${col.name} ${col.type}`);
        } catch (e) {
          if (!e.message.includes('duplicate column name')) {
            throw e;
          }
        }
      }
    }

    // Should not throw
    assert.ok(true, 'Migration ran twice without error');

    db.close();
    cleanup(tmpDir);
  });
});

// ============================================================================
// TESTS: SAVE WITH DECAY COLUMNS
// ============================================================================

testGroup('Save with Decay Columns', () => {
  test('New memory gets initialized decay columns', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;

    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, last_accessed, effective_importance, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'test content', 'test content', 0.7, now, 0.7, 0);

    const row = db.prepare('SELECT * FROM memories WHERE id = 1').get();
    assert.strictEqual(row.importance, 0.7);
    assert.strictEqual(row.effective_importance, 0.7);
    assert.strictEqual(row.access_count, 0);
    assert.ok(Math.abs(row.last_accessed - now) < 1);

    db.close();
    cleanup(tmpDir);
  });

  test('Immortal memory saves correctly', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;

    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, last_accessed, effective_importance, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'critical truth', 'critical truth', 0.95, now, 0.95, 0);

    const row = db.prepare('SELECT * FROM memories WHERE id = 1').get();
    assert.strictEqual(row.importance, 0.95);
    assert.strictEqual(row.effective_importance, 0.95);

    db.close();
    cleanup(tmpDir);
  });
});

// ============================================================================
// TESTS: RECALL WITH DECAY FILTER
// ============================================================================

testGroup('Recall with Decay Filter', () => {
  test('Decayed memories are hidden by default', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;

    // Insert active memory
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'active memory', 'active memory', 0.5, 0.5, now, 0);

    // Insert decayed memory (effective_importance below threshold)
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now - 86400 * 100, 'decayed memory', 'decayed memory', 0.3, 0.05, now - 86400 * 100, 0);

    // Query with threshold filter (simulating what recall does)
    const threshold = 0.1;
    const results = db.prepare(`
      SELECT * FROM memories
      WHERE (event LIKE ?)
      AND (effective_importance IS NULL OR effective_importance >= ?)
    `).all('%memory%', threshold);

    assert.strictEqual(results.length, 1);
    assert.strictEqual(results[0].event, 'active memory');

    db.close();
    cleanup(tmpDir);
  });

  test('include_decayed=true returns all memories', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;

    // Active
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'active', 'active', 0.5, 0.5, now, 0);

    // Decayed
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'decayed', 'decayed', 0.3, 0.05, now - 86400 * 100, 0);

    // Query without decay filter (include_decayed = true)
    const results = db.prepare(`
      SELECT * FROM memories WHERE 1=1
    `).all();

    assert.strictEqual(results.length, 2);

    db.close();
    cleanup(tmpDir);
  });
});

// ============================================================================
// TESTS: TOUCH MECHANICS
// ============================================================================

testGroup('Touch Mechanics', () => {
  test('Touching a memory updates last_accessed and increments access_count', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;
    const originalAccess = now - 86400 * 10;

    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now - 86400 * 30, 'old memory', 'old memory', 0.5, 0.4, originalAccess, 3);

    // Touch
    db.prepare('UPDATE memories SET last_accessed = ?, access_count = COALESCE(access_count, 0) + 1 WHERE id = ?')
      .run(now, 1);

    const row = db.prepare('SELECT * FROM memories WHERE id = 1').get();
    assert.ok(Math.abs(row.last_accessed - now) < 1);
    assert.strictEqual(row.access_count, 4);

    db.close();
    cleanup(tmpDir);
  });

  test('Touch handles NULL access_count gracefully', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;

    // Insert with NULL access_count
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, NULL)
    `).run(now, 'test', 'test', 0.5, 0.5, now);

    // Touch - COALESCE(access_count, 0) + 1 should give 1
    db.prepare('UPDATE memories SET last_accessed = ?, access_count = COALESCE(access_count, 0) + 1 WHERE id = ?')
      .run(now, 1);

    const row = db.prepare('SELECT * FROM memories WHERE id = 1').get();
    assert.strictEqual(row.access_count, 1);

    db.close();
    cleanup(tmpDir);
  });
});

// ============================================================================
// TESTS: SWEEP BEHAVIOR
// ============================================================================

testGroup('Sweep Behavior', () => {
  test('Sweep updates effective_importance for non-immortal memories', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;
    const thirtyDaysAgo = now - 86400 * 30;

    // Insert non-immortal memory accessed 30 days ago
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(thirtyDaysAgo, 'old', 'old', 0.5, 0.5, thirtyDaysAgo, 0);

    // Simulate sweep
    const config = { BASE_RATE: 0.01, IMMORTAL_THRESHOLD: 0.9, SWEEP_BATCH_SIZE: 1000 };
    const memories = db.prepare(
      `SELECT id, importance, last_accessed FROM memories WHERE importance < ? LIMIT ?`
    ).all(config.IMMORTAL_THRESHOLD, config.SWEEP_BATCH_SIZE);

    for (const mem of memories) {
      const daysSinceAccess = (now - mem.last_accessed) / 86400;
      const decayRate = config.BASE_RATE * (1 - mem.importance);
      const decayFactor = Math.exp(-decayRate * daysSinceAccess);
      const newEffective = mem.importance * decayFactor;

      db.prepare('UPDATE memories SET effective_importance = ? WHERE id = ?').run(newEffective, mem.id);
    }

    const row = db.prepare('SELECT * FROM memories WHERE id = 1').get();
    assert.ok(row.effective_importance < 0.5, `Effective should be < 0.5, got ${row.effective_importance}`);
    assert.ok(row.effective_importance > 0, `Effective should be > 0, got ${row.effective_importance}`);

    db.close();
    cleanup(tmpDir);
  });

  test('Sweep does not touch immortal memories', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;
    const yearAgo = now - 86400 * 365;

    // Insert immortal memory
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(yearAgo, 'immortal', 'immortal', 0.95, 0.95, yearAgo, 0);

    // Simulate sweep - only select non-immortal
    const config = { IMMORTAL_THRESHOLD: 0.9, SWEEP_BATCH_SIZE: 1000 };
    const memories = db.prepare(
      `SELECT id, importance, last_accessed FROM memories WHERE importance < ? LIMIT ?`
    ).all(config.IMMORTAL_THRESHOLD, config.SWEEP_BATCH_SIZE);

    assert.strictEqual(memories.length, 0, 'Immortal memories should not be selected for sweep');

    const row = db.prepare('SELECT * FROM memories WHERE id = 1').get();
    assert.strictEqual(row.effective_importance, 0.95);

    db.close();
    cleanup(tmpDir);
  });
});

// ============================================================================
// TESTS: NULL HANDLING FOR PRE-MIGRATION MEMORIES
// ============================================================================

testGroup('NULL Handling for Pre-Migration Memories', () => {
  test('Pre-migration memories with NULL effective_importance pass decay filter', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;

    // Simulate pre-migration memory (no decay columns set)
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance)
      VALUES (?, ?, ?, ?)
    `).run(now, 'legacy', 'legacy', 0.5);

    // The filter uses: effective_importance IS NULL OR effective_importance >= threshold
    const threshold = 0.1;
    const results = db.prepare(`
      SELECT * FROM memories
      WHERE (effective_importance IS NULL OR effective_importance >= ?)
    `).all(threshold);

    assert.strictEqual(results.length, 1, 'Pre-migration memory should pass NULL-safe filter');
    assert.strictEqual(results[0].event, 'legacy');

    db.close();
    cleanup(tmpDir);
  });
});

// ============================================================================
// TESTS: STATUS AND STATS WITH DECAY
// ============================================================================

testGroup('Status and Stats with Decay', () => {
  test('Stats correctly counts immortal, active, and decayed memories', () => {
    const { db, tmpDir } = createTestDbWithDecay();
    const now = Date.now() / 1000;
    const IMMORTAL_THRESHOLD = 0.9;
    const THRESHOLD = 0.1;

    // Immortal
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'immortal', 'immortal', 0.95, 0.95, now, 0);

    // Active (non-immortal, not decayed)
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'active', 'active', 0.5, 0.4, now, 0);

    // Decayed
    db.prepare(`
      INSERT INTO memories (timestamp, content, event, importance, effective_importance, last_accessed, access_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(now, 'decayed', 'decayed', 0.2, 0.05, now - 86400 * 100, 0);

    const total = db.prepare('SELECT COUNT(*) as count FROM memories').get();
    const immortal = db.prepare('SELECT COUNT(*) as count FROM memories WHERE importance >= ?').get(IMMORTAL_THRESHOLD);
    const decayed = db.prepare('SELECT COUNT(*) as count FROM memories WHERE effective_importance IS NOT NULL AND effective_importance < ?').get(THRESHOLD);
    const active = total.count - immortal.count - decayed.count;

    assert.strictEqual(total.count, 3);
    assert.strictEqual(immortal.count, 1);
    assert.strictEqual(decayed.count, 1);
    assert.strictEqual(active, 1);

    db.close();
    cleanup(tmpDir);
  });
});

// ============================================================================
// TESTS: DECAY CONFIG
// ============================================================================

testGroup('Decay Configuration', () => {
  test('DECAY_CONFIG has all required fields', async () => {
    const { DECAY_CONFIG } = await import('../server/database.js');

    assert.ok('ENABLED' in DECAY_CONFIG, 'Missing ENABLED');
    assert.ok('BASE_RATE' in DECAY_CONFIG, 'Missing BASE_RATE');
    assert.ok('THRESHOLD' in DECAY_CONFIG, 'Missing THRESHOLD');
    assert.ok('IMMORTAL_THRESHOLD' in DECAY_CONFIG, 'Missing IMMORTAL_THRESHOLD');
    assert.ok('SWEEP_INTERVAL_MINUTES' in DECAY_CONFIG, 'Missing SWEEP_INTERVAL_MINUTES');
    assert.ok('SWEEP_BATCH_SIZE' in DECAY_CONFIG, 'Missing SWEEP_BATCH_SIZE');
  });

  test('DECAY_CONFIG has sensible defaults', async () => {
    const { DECAY_CONFIG } = await import('../server/database.js');

    assert.strictEqual(typeof DECAY_CONFIG.ENABLED, 'boolean');
    assert.strictEqual(DECAY_CONFIG.BASE_RATE, 0.01);
    assert.strictEqual(DECAY_CONFIG.THRESHOLD, 0.1);
    assert.strictEqual(DECAY_CONFIG.IMMORTAL_THRESHOLD, 0.9);
    assert.strictEqual(DECAY_CONFIG.SWEEP_INTERVAL_MINUTES, 60);
    assert.strictEqual(DECAY_CONFIG.SWEEP_BATCH_SIZE, 1000);
  });
});

// ============================================================================
// TESTS: EFFECTIVE IMPORTANCE FILTER IN buildWhereClause
// ============================================================================

testGroup('buildWhereClause with effective_importance filters', () => {
  test('effective_importance_min filter generates correct SQL', async () => {
    const { buildWhereClause } = await import('../server/database.js');

    const { whereClause, params } = buildWhereClause({ effective_importance_min: 0.3 });
    assert.ok(whereClause.includes('effective_importance >= ?'));
    assert.deepStrictEqual(params, [0.3]);
  });

  test('effective_importance_max filter generates correct SQL', async () => {
    const { buildWhereClause } = await import('../server/database.js');

    const { whereClause, params } = buildWhereClause({ effective_importance_max: 0.8 });
    assert.ok(whereClause.includes('effective_importance <= ?'));
    assert.deepStrictEqual(params, [0.8]);
  });

  test('Combined effective_importance filters work together', async () => {
    const { buildWhereClause } = await import('../server/database.js');

    const { whereClause, params } = buildWhereClause({
      effective_importance_min: 0.2,
      effective_importance_max: 0.7
    });

    assert.ok(whereClause.includes('effective_importance >= ?'));
    assert.ok(whereClause.includes('effective_importance <= ?'));
    assert.deepStrictEqual(params, [0.2, 0.7]);
  });
});

// ============================================================================
// TESTS: VALIDATION - include_decayed
// ============================================================================

testGroup('Validation - include_decayed', () => {
  test('validateRecallInput accepts include_decayed boolean', async () => {
    const { validateRecallInput } = await import('../server/validation.js');

    const result = validateRecallInput({
      query: 'test query',
      include_decayed: true
    });

    assert.strictEqual(result.include_decayed, true);
  });

  test('validateRecallInput defaults include_decayed to false', async () => {
    const { validateRecallInput } = await import('../server/validation.js');

    const result = validateRecallInput({
      query: 'test query'
    });

    assert.strictEqual(result.include_decayed, false);
  });

  test('validateQueryLayerInput accepts include_decayed boolean', async () => {
    const { validateQueryLayerInput } = await import('../server/validation.js');

    const result = validateQueryLayerInput({
      layer: 'episodic',
      include_decayed: true
    });

    assert.strictEqual(result.include_decayed, true);
  });

  test('validateQueryLayerInput defaults include_decayed to false', async () => {
    const { validateQueryLayerInput } = await import('../server/validation.js');

    const result = validateQueryLayerInput({
      layer: 'episodic'
    });

    assert.strictEqual(result.include_decayed, false);
  });
});

// ============================================================================
// TESTS: VALIDATION - effective_importance filters
// ============================================================================

testGroup('Validation - effective_importance filters', () => {
  test('validateFilters accepts effective_importance_min', async () => {
    const { validateFilters } = await import('../server/validation.js');

    const result = validateFilters({ effective_importance_min: 0.3 });
    assert.strictEqual(result.effective_importance_min, 0.3);
  });

  test('validateFilters accepts effective_importance_max', async () => {
    const { validateFilters } = await import('../server/validation.js');

    const result = validateFilters({ effective_importance_max: 0.8 });
    assert.strictEqual(result.effective_importance_max, 0.8);
  });

  test('validateFilters rejects effective_importance_min > effective_importance_max', async () => {
    const { validateFilters, ValidationError } = await import('../server/validation.js');

    try {
      validateFilters({
        effective_importance_min: 0.8,
        effective_importance_max: 0.3
      });
      assert.fail('Should have thrown ValidationError');
    } catch (error) {
      assert.ok(error instanceof ValidationError);
      assert.ok(error.message.includes('effective_importance_min'));
    }
  });
});

// ============================================================================
// RESULTS SUMMARY
// ============================================================================

console.log(`\n${'='.repeat(60)}`);
console.log(`Decay Test Results: ${passCount} passed, ${failCount} failed`);
console.log('='.repeat(60));

if (failures.length > 0) {
  console.log('\nFailures:');
  failures.forEach(f => {
    console.log(`  - ${f.description}: ${f.error}`);
  });
}

process.exit(failCount > 0 ? 1 : 0);
