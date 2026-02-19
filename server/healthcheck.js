#!/usr/bin/env node

/**
 * CASCADE Enterprise - Docker Health Check
 * Copyright (c) 2025-2026 CIPS Corp (C.I.P.S. LLC)
 *
 * Verifies:
 * 1. Node process is running (implicit - this script runs)
 * 2. At least one SQLite database is accessible and responds to queries
 * 3. Database schema has the expected tables
 *
 * Exit 0 = healthy, Exit 1 = unhealthy
 */

import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const DB_PATH = process.env.CASCADE_DB_PATH || '/data/cascade';
const RAM_PATH = process.env.CASCADE_RAM_PATH || '/ram_disk';

// Check at least one layer database exists and responds
const LAYERS = ['episodic', 'semantic', 'procedural', 'meta', 'identity', 'working'];

let healthy = false;
let checkedCount = 0;
let errorMessages = [];

for (const layer of LAYERS) {
  const dbFile = `${layer}_memory.db`;

  // Try RAM path first (fast), then disk path (truth)
  const candidates = [
    path.join(RAM_PATH, dbFile),
    path.join(DB_PATH, dbFile)
  ];

  for (const dbPath of candidates) {
    if (!fs.existsSync(dbPath)) {
      continue;
    }

    let db;
    try {
      db = new Database(dbPath, { readonly: true, timeout: 5000 });
      // Verify the database responds to a simple query
      const result = db.prepare('SELECT COUNT(*) AS count FROM memories').get();
      if (typeof result.count === 'number') {
        checkedCount++;
        healthy = true;
      }
    } catch (err) {
      errorMessages.push(`${layer}: ${err.message}`);
    } finally {
      if (db) {
        try { db.close(); } catch (_) { /* ignore close errors */ }
      }
    }

    // One successful check per layer is enough
    if (healthy) break;
  }
}

if (healthy) {
  process.exit(0);
} else {
  if (errorMessages.length > 0) {
    process.stderr.write(`CASCADE healthcheck failed: ${errorMessages.join('; ')}\n`);
  } else {
    process.stderr.write('CASCADE healthcheck failed: no database files found\n');
  }
  process.exit(1);
}
