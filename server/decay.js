/**
 * CASCADE Memory System
 * Copyright (c) 2025-2026 CIPS Corp (C.I.P.S. LLC)
 * MIT License - See LICENSE file
 *
 * https://cipscorps.io
 * Contact: glass@cipscorps.io
 *
 * Decay Engine - Temporal memory decay with immortal threshold
 *
 * Formula:
 *   If importance >= IMMORTAL_THRESHOLD: effective_importance = importance (never decays)
 *   Else:
 *     days_since_access = (now - last_accessed) / 86400
 *     decay_rate = BASE_RATE * (1 - importance)
 *     decay_factor = e^(-decay_rate * days_since_access)
 *     effective_importance = importance * decay_factor
 *
 * Memories with effective_importance < THRESHOLD are considered "decayed"
 * and hidden from default queries (retrievable with include_decayed flag).
 */

import { DECAY_CONFIG, MEMORY_LAYERS } from './database.js';

export class DecayEngine {
  constructor(dbManager, logger = null) {
    this.dbManager = dbManager;
    this.logger = logger;
    this.config = { ...DECAY_CONFIG };
    this.sweepInterval = null;
    this.sweepRunning = false;
    this.stats = {
      lastSweepTime: null,
      lastSweepDurationMs: null,
      totalSweeps: 0,
      totalUpdated: 0
    };
  }

  /**
   * Calculate effective importance for a memory
   */
  calculateEffectiveImportance(importance, lastAccessed, now = Date.now() / 1000) {
    // Immortal memories never decay
    if (importance >= this.config.IMMORTAL_THRESHOLD) {
      return importance;
    }

    // Default to now if lastAccessed is null/undefined (prevents NaN)
    const safeLastAccessed = lastAccessed || now;
    const daysSinceAccess = (now - safeLastAccessed) / 86400;
    if (daysSinceAccess <= 0) {
      return importance;
    }

    const decayRate = this.config.BASE_RATE * (1 - importance);
    const decayFactor = Math.exp(-decayRate * daysSinceAccess);
    return importance * decayFactor;
  }

  /**
   * Run a sweep across all layers
   */
  runSweep() {
    if (!this.config.ENABLED) return;
    if (this.sweepRunning) {
      this.logger?.warn('Decay sweep already running, skipping');
      return;
    }

    this.sweepRunning = true;
    const startTime = Date.now();
    let totalUpdated = 0;

    try {
      const now = Date.now() / 1000;

      for (const layer of Object.keys(MEMORY_LAYERS)) {
        try {
          const updated = this.sweepLayer(layer, now);
          totalUpdated += updated;
        } catch (error) {
          this.logger?.error(`Decay sweep failed for layer ${layer}`, { error });
        }
      }

      const durationMs = Date.now() - startTime;
      this.stats.lastSweepTime = Date.now();
      this.stats.lastSweepDurationMs = durationMs;
      this.stats.totalSweeps++;
      this.stats.totalUpdated += totalUpdated;

      this.logger?.info('Decay sweep completed', {
        totalUpdated,
        durationMs,
        sweepNumber: this.stats.totalSweeps
      });
    } finally {
      this.sweepRunning = false;
    }
  }

  /**
   * Sweep a single layer: recalculate effective_importance for non-immortal memories
   */
  sweepLayer(layer, now) {
    const db = this.dbManager.getConnection(layer);

    // Select non-immortal memories in batches
    const memories = db.prepare(
      `SELECT id, importance, last_accessed FROM memories
       WHERE importance < ? AND last_accessed IS NOT NULL
       LIMIT ?`
    ).all(this.config.IMMORTAL_THRESHOLD, this.config.SWEEP_BATCH_SIZE);

    if (memories.length === 0) return 0;

    const operations = [];
    let updated = 0;

    for (const mem of memories) {
      const newEffective = this.calculateEffectiveImportance(
        mem.importance,
        mem.last_accessed,
        now
      );

      operations.push({
        sql: 'UPDATE memories SET effective_importance = ? WHERE id = ?',
        params: [newEffective, mem.id]
      });
      updated++;
    }

    if (operations.length > 0) {
      this.dbManager.dualWriteBatch(layer, operations);
    }

    return updated;
  }

  /**
   * Touch memories: update last_accessed and access_count when recalled
   * Fire-and-forget - errors are logged but don't affect the caller
   */
  touchMemories(layer, memoryIds) {
    if (!memoryIds || memoryIds.length === 0) return;

    const now = Date.now() / 1000;
    const operations = memoryIds.map(id => ({
      sql: 'UPDATE memories SET last_accessed = ?, access_count = COALESCE(access_count, 0) + 1 WHERE id = ?',
      params: [now, id]
    }));

    try {
      this.dbManager.dualWriteBatch(layer, operations);
    } catch (error) {
      this.logger?.error('Failed to touch memories', { layer, memoryIds, error });
    }
  }

  /**
   * Start the decay engine: run initial sweep and schedule periodic sweeps
   */
  start() {
    if (!this.config.ENABLED) {
      this.logger?.info('Decay engine disabled via configuration');
      return;
    }

    this.logger?.info('Starting decay engine', {
      baseRate: this.config.BASE_RATE,
      threshold: this.config.THRESHOLD,
      immortalThreshold: this.config.IMMORTAL_THRESHOLD,
      sweepIntervalMinutes: this.config.SWEEP_INTERVAL_MINUTES
    });

    // Run initial sweep (synchronous, catches its own errors)
    try {
      this.runSweep();
    } catch (err) {
      this.logger?.error('Initial decay sweep failed', { error: err });
    }

    // Schedule periodic sweeps
    this.sweepInterval = setInterval(() => {
      try {
        this.runSweep();
      } catch (err) {
        this.logger?.error('Periodic decay sweep failed', { error: err });
      }
    }, this.config.SWEEP_INTERVAL_MINUTES * 60 * 1000);

    if (this.sweepInterval.unref) {
      this.sweepInterval.unref();
    }
  }

  /**
   * Stop the decay engine
   */
  stop() {
    if (this.sweepInterval) {
      clearInterval(this.sweepInterval);
      this.sweepInterval = null;
    }
    this.logger?.info('Decay engine stopped');
  }

  /**
   * Get decay engine status
   */
  getStatus() {
    return {
      enabled: this.config.ENABLED,
      config: {
        base_rate: this.config.BASE_RATE,
        threshold: this.config.THRESHOLD,
        immortal_threshold: this.config.IMMORTAL_THRESHOLD,
        sweep_interval_minutes: this.config.SWEEP_INTERVAL_MINUTES,
        sweep_batch_size: this.config.SWEEP_BATCH_SIZE
      },
      stats: { ...this.stats },
      sweep_running: this.sweepRunning
    };
  }
}

export default DecayEngine;
