#!/usr/bin/env node

/**
 * Test Runner for cascade-enterprise-ram
 * Runs all test files and reports combined results
 *
 * Created: January 22, 2026
 */

import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const testFiles = [
  'validation.test.js',
  'index.test.js',
  'content_analyzer.test.js',
  'decay.test.js',
  'integration.test.js'
];

let totalPass = 0;
let totalFail = 0;
let failedTests = [];

async function runTest(testFile) {
  return new Promise((resolve) => {
    const testPath = path.join(__dirname, testFile);
    console.log(`\n${'='.repeat(70)}`);
    console.log(`Running: ${testFile}`);
    console.log('='.repeat(70));

    const proc = spawn('node', [testPath], {
      cwd: __dirname,
      stdio: 'inherit'
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        failedTests.push(testFile);
      }
      resolve(code);
    });

    proc.on('error', (err) => {
      console.error(`Failed to run ${testFile}:`, err.message);
      failedTests.push(testFile);
      resolve(1);
    });
  });
}

async function main() {
  console.log('='.repeat(70));
  console.log('CASCADE ENTERPRISE RAM - TEST SUITE');
  console.log('='.repeat(70));
  console.log(`\nRunning ${testFiles.length} test files...\n`);

  const startTime = Date.now();

  for (const testFile of testFiles) {
    await runTest(testFile);
  }

  const duration = ((Date.now() - startTime) / 1000).toFixed(2);

  console.log('\n' + '='.repeat(70));
  console.log('OVERALL TEST RESULTS');
  console.log('='.repeat(70));
  console.log(`\nTest files run: ${testFiles.length}`);
  console.log(`Test files passed: ${testFiles.length - failedTests.length}`);
  console.log(`Test files failed: ${failedTests.length}`);
  console.log(`Total time: ${duration}s`);

  if (failedTests.length > 0) {
    console.log('\nFailed test files:');
    failedTests.forEach(f => console.log(`  - ${f}`));
    process.exit(1);
  } else {
    console.log('\nAll test files passed!');
    process.exit(0);
  }
}

main().catch(err => {
  console.error('Test runner failed:', err);
  process.exit(1);
});
