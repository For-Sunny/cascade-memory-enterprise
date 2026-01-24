/**
 * Unit Tests for validation.js
 * CASCADE Enterprise - Validation Module Tests
 *
 * Created: January 22, 2026
 * Tests all validation functions for proper input sanitization
 */

import assert from 'assert';
import {
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
} from '../server/validation.js';

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
// TESTS: TYPE CHECKERS
// ============================================================================

testGroup('Type Checkers', () => {
  // isString tests
  test('isString returns true for strings', () => {
    assert.strictEqual(isString('hello'), true);
    assert.strictEqual(isString(''), true);
  });

  test('isString returns false for non-strings', () => {
    assert.strictEqual(isString(123), false);
    assert.strictEqual(isString(null), false);
    assert.strictEqual(isString(undefined), false);
    assert.strictEqual(isString({}), false);
    assert.strictEqual(isString([]), false);
  });

  // isNumber tests
  test('isNumber returns true for finite numbers', () => {
    assert.strictEqual(isNumber(0), true);
    assert.strictEqual(isNumber(123), true);
    assert.strictEqual(isNumber(-45.67), true);
    assert.strictEqual(isNumber(0.5), true);
  });

  test('isNumber returns false for non-numbers', () => {
    assert.strictEqual(isNumber('123'), false);
    assert.strictEqual(isNumber(NaN), false);
    assert.strictEqual(isNumber(Infinity), false);
    assert.strictEqual(isNumber(-Infinity), false);
    assert.strictEqual(isNumber(null), false);
  });

  // isInteger tests
  test('isInteger returns true for integers', () => {
    assert.strictEqual(isInteger(0), true);
    assert.strictEqual(isInteger(123), true);
    assert.strictEqual(isInteger(-456), true);
  });

  test('isInteger returns false for non-integers', () => {
    assert.strictEqual(isInteger(1.5), false);
    assert.strictEqual(isInteger('123'), false);
    assert.strictEqual(isInteger(NaN), false);
  });

  // isPlainObject tests
  test('isPlainObject returns true for plain objects', () => {
    assert.strictEqual(isPlainObject({}), true);
    assert.strictEqual(isPlainObject({ a: 1 }), true);
  });

  test('isPlainObject returns false for non-plain objects', () => {
    assert.strictEqual(isPlainObject(null), false);
    assert.strictEqual(isPlainObject([]), false);
    assert.strictEqual(isPlainObject('string'), false);
    assert.strictEqual(isPlainObject(123), false);
  });

  // isArray tests
  test('isArray returns true for arrays', () => {
    assert.strictEqual(isArray([]), true);
    assert.strictEqual(isArray([1, 2, 3]), true);
  });

  test('isArray returns false for non-arrays', () => {
    assert.strictEqual(isArray({}), false);
    assert.strictEqual(isArray('string'), false);
    assert.strictEqual(isArray(null), false);
  });
});

// ============================================================================
// TESTS: CONTENT VALIDATORS
// ============================================================================

testGroup('Content Validators', () => {
  // validateContent tests
  test('validateContent accepts valid content', () => {
    const result = validateContent('Hello world');
    assert.strictEqual(result, 'Hello world');
  });

  test('validateContent trims whitespace', () => {
    const result = validateContent('  Hello world  ');
    assert.strictEqual(result, 'Hello world');
  });

  test('validateContent throws for null content', () => {
    assert.throws(() => validateContent(null), ValidationError);
  });

  test('validateContent throws for undefined content', () => {
    assert.throws(() => validateContent(undefined), ValidationError);
  });

  test('validateContent throws for empty string after trim', () => {
    assert.throws(() => validateContent('   '), ValidationError);
  });

  test('validateContent throws for non-string content', () => {
    assert.throws(() => validateContent(123), ValidationError);
    assert.throws(() => validateContent({}), ValidationError);
  });

  test('validateContent throws for content exceeding max length', () => {
    const longContent = 'x'.repeat(CONTENT_LIMITS.MAX_CONTENT_LENGTH + 1);
    assert.throws(() => validateContent(longContent), ValidationError);
  });

  test('validateContent accepts content at max length', () => {
    const maxContent = 'x'.repeat(CONTENT_LIMITS.MAX_CONTENT_LENGTH);
    const result = validateContent(maxContent);
    assert.strictEqual(result.length, CONTENT_LIMITS.MAX_CONTENT_LENGTH);
  });

  // validateQuery tests
  test('validateQuery accepts valid query', () => {
    const result = validateQuery('search term');
    assert.strictEqual(result, 'search term');
  });

  test('validateQuery throws for empty query', () => {
    assert.throws(() => validateQuery(''), ValidationError);
    assert.throws(() => validateQuery('   '), ValidationError);
  });

  test('validateQuery throws for query exceeding max length', () => {
    const longQuery = 'x'.repeat(CONTENT_LIMITS.MAX_QUERY_LENGTH + 1);
    assert.throws(() => validateQuery(longQuery), ValidationError);
  });

  // validateContext tests
  test('validateContext accepts valid context', () => {
    const result = validateContext('some context');
    assert.strictEqual(result, 'some context');
  });

  test('validateContext returns empty string for null/undefined', () => {
    assert.strictEqual(validateContext(null), '');
    assert.strictEqual(validateContext(undefined), '');
    assert.strictEqual(validateContext(''), '');
  });

  test('validateContext throws for context exceeding max length', () => {
    const longContext = 'x'.repeat(CONTENT_LIMITS.MAX_CONTEXT_LENGTH + 1);
    assert.throws(() => validateContext(longContext), ValidationError);
  });
});

// ============================================================================
// TESTS: LAYER VALIDATORS
// ============================================================================

testGroup('Layer Validators', () => {
  test('validateLayer accepts all valid layers', () => {
    for (const layer of VALID_LAYERS) {
      const result = validateLayer(layer);
      assert.strictEqual(result, layer);
    }
  });

  test('validateLayer normalizes to lowercase', () => {
    assert.strictEqual(validateLayer('EPISODIC'), 'episodic');
    assert.strictEqual(validateLayer('Semantic'), 'semantic');
  });

  test('validateLayer trims whitespace', () => {
    assert.strictEqual(validateLayer('  episodic  '), 'episodic');
  });

  test('validateLayer returns null for null/undefined when not required', () => {
    assert.strictEqual(validateLayer(null, false), null);
    assert.strictEqual(validateLayer(undefined, false), null);
    assert.strictEqual(validateLayer('', false), null);
  });

  test('validateLayer throws when required and not provided', () => {
    assert.throws(() => validateLayer(null, true), ValidationError);
    assert.throws(() => validateLayer(undefined, true), ValidationError);
  });

  test('validateLayer throws for invalid layer names', () => {
    assert.throws(() => validateLayer('invalid'), ValidationError);
    assert.throws(() => validateLayer('memory'), ValidationError);
    assert.throws(() => validateLayer('core'), ValidationError);
  });

  test('validateLayer error includes valid layer list', () => {
    try {
      validateLayer('invalid');
      assert.fail('Should have thrown');
    } catch (error) {
      assert(error.message.includes('episodic'));
      assert(error.message.includes('semantic'));
    }
  });
});

// ============================================================================
// TESTS: NUMERIC VALIDATORS
// ============================================================================

testGroup('Numeric Validators', () => {
  // validateNumericRange tests
  test('validateNumericRange accepts value in range', () => {
    assert.strictEqual(validateNumericRange(5, 'test', 0, 10), 5);
    assert.strictEqual(validateNumericRange(0, 'test', 0, 10), 0);
    assert.strictEqual(validateNumericRange(10, 'test', 0, 10), 10);
  });

  test('validateNumericRange returns default for null/undefined', () => {
    assert.strictEqual(validateNumericRange(null, 'test', 0, 10, 5), 5);
    assert.strictEqual(validateNumericRange(undefined, 'test', 0, 10, 5), 5);
  });

  test('validateNumericRange throws when required value is missing', () => {
    assert.throws(() => validateNumericRange(null, 'test', 0, 10, null), ValidationError);
  });

  test('validateNumericRange throws for out of range values', () => {
    assert.throws(() => validateNumericRange(-1, 'test', 0, 10), ValidationError);
    assert.throws(() => validateNumericRange(11, 'test', 0, 10), ValidationError);
  });

  test('validateNumericRange handles string numbers', () => {
    assert.strictEqual(validateNumericRange('5', 'test', 0, 10), 5);
    assert.strictEqual(validateNumericRange('5.5', 'test', 0, 10), 5.5);
  });

  // validateImportance tests
  test('validateImportance accepts values in 0-1 range', () => {
    assert.strictEqual(validateImportance(0), 0);
    assert.strictEqual(validateImportance(0.5), 0.5);
    assert.strictEqual(validateImportance(1), 1);
  });

  test('validateImportance returns default for null', () => {
    assert.strictEqual(validateImportance(null), 0.7); // Default
  });

  test('validateImportance throws for out of range', () => {
    assert.throws(() => validateImportance(-0.1), ValidationError);
    assert.throws(() => validateImportance(1.1), ValidationError);
  });

  // validateEmotionalIntensity tests
  test('validateEmotionalIntensity accepts values in 0-1 range', () => {
    assert.strictEqual(validateEmotionalIntensity(0), 0);
    assert.strictEqual(validateEmotionalIntensity(1), 1);
  });

  test('validateEmotionalIntensity returns default for null', () => {
    assert.strictEqual(validateEmotionalIntensity(null), 0.5); // Default
  });


  // validateLimit tests
  test('validateLimit accepts valid limits', () => {
    assert.strictEqual(validateLimit(1), 1);
    assert.strictEqual(validateLimit(100), 100);
  });

  test('validateLimit returns default for null', () => {
    assert.strictEqual(validateLimit(null), NUMERIC_LIMITS.DEFAULT_LIMIT);
  });

  test('validateLimit floors decimal values', () => {
    assert.strictEqual(validateLimit(5.7), 5);
  });

  test('validateLimit throws for out of range', () => {
    assert.throws(() => validateLimit(0), ValidationError);
    assert.throws(() => validateLimit(1001), ValidationError);
  });

  // validateTimestamp tests
  test('validateTimestamp accepts valid timestamps', () => {
    const now = Date.now() / 1000;
    assert.strictEqual(validateTimestamp(now), now);
  });

  test('validateTimestamp returns null for null/undefined', () => {
    assert.strictEqual(validateTimestamp(null), null);
    assert.strictEqual(validateTimestamp(undefined), null);
  });

  // validateId tests
  test('validateId accepts valid IDs', () => {
    assert.strictEqual(validateId(1), 1);
    assert.strictEqual(validateId(12345), 12345);
  });

  test('validateId floors decimal values', () => {
    assert.strictEqual(validateId(5.9), 5);
  });

  test('validateId returns null for null/undefined', () => {
    assert.strictEqual(validateId(null), null);
    assert.strictEqual(validateId(undefined), null);
  });
});

// ============================================================================
// TESTS: METADATA VALIDATORS
// ============================================================================

testGroup('Metadata Validators', () => {
  // validateMetadata tests
  test('validateMetadata accepts empty metadata', () => {
    const result = validateMetadata({});
    assert.deepStrictEqual(result, {});
  });

  test('validateMetadata returns empty object for null/undefined', () => {
    assert.deepStrictEqual(validateMetadata(null), {});
    assert.deepStrictEqual(validateMetadata(undefined), {});
  });

  test('validateMetadata validates known fields', () => {
    const result = validateMetadata({
      importance: 0.8,
      emotional_intensity: 0.6,
      context: 'test context'
    });
    assert.strictEqual(result.importance, 0.8);
    assert.strictEqual(result.emotional_intensity, 0.6);
    assert.strictEqual(result.context, 'test context');
  });

  test('validateMetadata moves unknown fields to custom', () => {
    const result = validateMetadata({
      unknown_field: 'value'
    });
    assert(result.custom);
    assert.strictEqual(result.custom.unknown_field, 'value');
  });

  test('validateMetadata throws for non-object metadata', () => {
    assert.throws(() => validateMetadata('string'), ValidationError);
    assert.throws(() => validateMetadata(123), ValidationError);
    assert.throws(() => validateMetadata([]), ValidationError);
  });

  test('validateMetadata throws for oversized metadata', () => {
    const hugeMetadata = { data: 'x'.repeat(CONTENT_LIMITS.MAX_METADATA_SIZE + 1) };
    assert.throws(() => validateMetadata(hugeMetadata), ValidationError);
  });

  // validateTags tests
  test('validateTags accepts valid tags array', () => {
    const result = validateTags(['tag1', 'tag2', 'tag3']);
    assert.deepStrictEqual(result, ['tag1', 'tag2', 'tag3']);
  });

  test('validateTags returns empty array for null/undefined', () => {
    assert.deepStrictEqual(validateTags(null), []);
    assert.deepStrictEqual(validateTags(undefined), []);
  });

  test('validateTags trims tag whitespace', () => {
    const result = validateTags(['  tag1  ', '  tag2  ']);
    assert.deepStrictEqual(result, ['tag1', 'tag2']);
  });

  test('validateTags filters empty tags after trim', () => {
    const result = validateTags(['tag1', '   ', 'tag2']);
    assert.deepStrictEqual(result, ['tag1', 'tag2']);
  });

  test('validateTags throws for non-array', () => {
    assert.throws(() => validateTags('tag1'), ValidationError);
    assert.throws(() => validateTags({}), ValidationError);
  });

  test('validateTags throws for too many tags', () => {
    const manyTags = Array(51).fill('tag');
    assert.throws(() => validateTags(manyTags), ValidationError);
  });

  test('validateTags throws for non-string tag', () => {
    assert.throws(() => validateTags(['tag1', 123]), ValidationError);
  });

  test('validateTags throws for overly long tag', () => {
    const longTag = 'x'.repeat(101);
    assert.throws(() => validateTags([longTag]), ValidationError);
  });

  // validateIdArray tests
  test('validateIdArray accepts valid ID array', () => {
    const result = validateIdArray([1, 2, 3]);
    assert.deepStrictEqual(result, [1, 2, 3]);
  });

  test('validateIdArray returns empty array for null/undefined', () => {
    assert.deepStrictEqual(validateIdArray(null), []);
    assert.deepStrictEqual(validateIdArray(undefined), []);
  });

  test('validateIdArray throws for non-array', () => {
    assert.throws(() => validateIdArray('1,2,3'), ValidationError);
  });

  test('validateIdArray throws for too many IDs', () => {
    const manyIds = Array(101).fill(1);
    assert.throws(() => validateIdArray(manyIds), ValidationError);
  });

  // validateStringField tests
  test('validateStringField accepts valid strings', () => {
    assert.strictEqual(validateStringField('value', 'field'), 'value');
  });

  test('validateStringField returns empty for null/undefined', () => {
    assert.strictEqual(validateStringField(null, 'field'), '');
    assert.strictEqual(validateStringField(undefined, 'field'), '');
  });

  test('validateStringField throws for non-string', () => {
    assert.throws(() => validateStringField(123, 'field'), ValidationError);
  });

  test('validateStringField throws for overly long value', () => {
    const longValue = 'x'.repeat(CONTENT_LIMITS.MAX_STRING_FIELD_LENGTH + 1);
    assert.throws(() => validateStringField(longValue, 'field'), ValidationError);
  });
});

// ============================================================================
// TESTS: FILTER VALIDATORS
// ============================================================================

testGroup('Filter Validators', () => {
  test('validateFilters accepts empty object', () => {
    assert.deepStrictEqual(validateFilters({}), {});
  });

  test('validateFilters returns empty object for null/undefined', () => {
    assert.deepStrictEqual(validateFilters(null), {});
    assert.deepStrictEqual(validateFilters(undefined), {});
  });

  test('validateFilters validates importance range filters', () => {
    const result = validateFilters({
      importance_min: 0.5,
      importance_max: 0.9
    });
    assert.strictEqual(result.importance_min, 0.5);
    assert.strictEqual(result.importance_max, 0.9);
  });

  test('validateFilters validates emotional intensity filters', () => {
    const result = validateFilters({
      emotional_intensity_min: 0.3,
      emotional_intensity_max: 0.7
    });
    assert.strictEqual(result.emotional_intensity_min, 0.3);
    assert.strictEqual(result.emotional_intensity_max, 0.7);
  });

  test('validateFilters validates timestamp filters', () => {
    const result = validateFilters({
      timestamp_after: 1000,
      timestamp_before: 2000
    });
    assert.strictEqual(result.timestamp_after, 1000);
    assert.strictEqual(result.timestamp_before, 2000);
  });

  test('validateFilters validates content search filters', () => {
    const result = validateFilters({
      content_contains: 'search term',
      context_contains: 'context term'
    });
    assert.strictEqual(result.content_contains, 'search term');
    assert.strictEqual(result.context_contains, 'context term');
  });

  test('validateFilters throws for non-object', () => {
    assert.throws(() => validateFilters('invalid'), ValidationError);
  });

  test('validateFilters throws when min > max for importance', () => {
    assert.throws(() => validateFilters({
      importance_min: 0.9,
      importance_max: 0.5
    }), ValidationError);
  });

  test('validateFilters throws when min > max for emotional_intensity', () => {
    assert.throws(() => validateFilters({
      emotional_intensity_min: 0.8,
      emotional_intensity_max: 0.2
    }), ValidationError);
  });

  test('validateFilters throws when timestamp_after > timestamp_before', () => {
    assert.throws(() => validateFilters({
      timestamp_after: 2000,
      timestamp_before: 1000
    }), ValidationError);
  });

  test('validateFilters throws for oversized content_contains', () => {
    const longSearch = 'x'.repeat(CONTENT_LIMITS.MAX_QUERY_LENGTH + 1);
    assert.throws(() => validateFilters({
      content_contains: longSearch
    }), ValidationError);
  });
});

// ============================================================================
// TESTS: QUERY OPTIONS VALIDATORS
// ============================================================================

testGroup('Query Options Validators', () => {
  test('validateQueryOptions returns defaults for null/undefined', () => {
    const result = validateQueryOptions(null);
    assert.strictEqual(result.limit, NUMERIC_LIMITS.DEFAULT_LIMIT);
  });

  test('validateQueryOptions validates limit', () => {
    const result = validateQueryOptions({ limit: 50 });
    assert.strictEqual(result.limit, 50);
  });

  test('validateQueryOptions validates order_by', () => {
    const result = validateQueryOptions({ order_by: 'timestamp DESC' });
    assert.strictEqual(result.order_by, 'timestamp DESC');
  });

  test('validateQueryOptions validates nested filters', () => {
    const result = validateQueryOptions({
      filters: { importance_min: 0.5 }
    });
    assert.strictEqual(result.filters.importance_min, 0.5);
  });

  test('validateQueryOptions throws for non-object', () => {
    assert.throws(() => validateQueryOptions('invalid'), ValidationError);
  });

  test('validateQueryOptions flags deprecated where usage', () => {
    const result = validateQueryOptions({ where: 'some condition' });
    assert.strictEqual(result._deprecated_where_used, true);
  });
});

// ============================================================================
// TESTS: COMPLETE INPUT VALIDATORS
// ============================================================================

testGroup('Complete Input Validators', () => {
  // validateRememberInput tests
  test('validateRememberInput validates complete input', () => {
    const result = validateRememberInput({
      content: 'Test memory content',
      layer: 'episodic',
      metadata: { importance: 0.8 }
    });
    assert.strictEqual(result.content, 'Test memory content');
    assert.strictEqual(result.layer, 'episodic');
    assert.strictEqual(result.metadata.importance, 0.8);
  });

  test('validateRememberInput throws for missing content', () => {
    assert.throws(() => validateRememberInput({}), ValidationError);
  });

  test('validateRememberInput throws for non-object args', () => {
    assert.throws(() => validateRememberInput('string'), ValidationError);
    assert.throws(() => validateRememberInput(null), ValidationError);
  });

  // validateRecallInput tests
  test('validateRecallInput validates complete input', () => {
    const result = validateRecallInput({
      query: 'search term',
      layer: 'semantic',
      limit: 20
    });
    assert.strictEqual(result.query, 'search term');
    assert.strictEqual(result.layer, 'semantic');
    assert.strictEqual(result.limit, 20);
  });

  test('validateRecallInput throws for missing query', () => {
    assert.throws(() => validateRecallInput({}), ValidationError);
  });

  // validateQueryLayerInput tests
  test('validateQueryLayerInput validates complete input', () => {
    const result = validateQueryLayerInput({
      layer: 'identity',
      options: { limit: 30 }
    });
    assert.strictEqual(result.layer, 'identity');
    assert.strictEqual(result.options.limit, 30);
  });

  test('validateQueryLayerInput requires layer', () => {
    assert.throws(() => validateQueryLayerInput({}), ValidationError);
  });

  // validateSaveToLayerInput tests
  test('validateSaveToLayerInput validates complete input', () => {
    const result = validateSaveToLayerInput({
      layer: 'meta',
      content: 'Test content',
      metadata: {}
    });
    assert.strictEqual(result.layer, 'meta');
    assert.strictEqual(result.content, 'Test content');
  });

  test('validateSaveToLayerInput requires both layer and content', () => {
    assert.throws(() => validateSaveToLayerInput({ layer: 'meta' }), ValidationError);
    assert.throws(() => validateSaveToLayerInput({ content: 'Test' }), ValidationError);
  });
});

// ============================================================================
// TESTS: VALIDATION ERROR CLASS
// ============================================================================

testGroup('ValidationError Class', () => {
  test('ValidationError has correct properties', () => {
    const error = new ValidationError('field', 'message', 'value');
    assert.strictEqual(error.name, 'ValidationError');
    assert.strictEqual(error.field, 'field');
    assert.strictEqual(error.validationMessage, 'message');
    assert(error.message.includes('field'));
    assert(error.message.includes('message'));
  });

  test('ValidationError toJSON returns structured object', () => {
    const error = new ValidationError('testField', 'test message');
    const json = error.toJSON();
    assert.strictEqual(json.error, 'ValidationError');
    assert.strictEqual(json.field, 'testField');
    assert.strictEqual(json.message, 'test message');
  });

  test('ValidationError hides value in production', () => {
    const originalDebug = process.env.DEBUG;
    process.env.DEBUG = 'false';
    const error = new ValidationError('field', 'message', 'sensitiveValue');
    assert.strictEqual(error.invalidValue, '[hidden]');
    process.env.DEBUG = originalDebug;
  });
});

// ============================================================================
// TESTS: CONSTANTS
// ============================================================================

testGroup('Constants', () => {
  test('VALID_LAYERS contains expected layers', () => {
    assert(VALID_LAYERS.includes('episodic'));
    assert(VALID_LAYERS.includes('semantic'));
    assert(VALID_LAYERS.includes('procedural'));
    assert(VALID_LAYERS.includes('meta'));
    assert(VALID_LAYERS.includes('identity'));
    assert(VALID_LAYERS.includes('working'));
    assert.strictEqual(VALID_LAYERS.length, 6);
  });

  test('VALID_LAYERS is frozen', () => {
    assert(Object.isFrozen(VALID_LAYERS));
  });

  test('CONTENT_LIMITS has expected values', () => {
    assert(CONTENT_LIMITS.MAX_CONTENT_LENGTH > 0);
    assert(CONTENT_LIMITS.MAX_QUERY_LENGTH > 0);
    assert(CONTENT_LIMITS.MAX_CONTEXT_LENGTH > 0);
    assert(CONTENT_LIMITS.MAX_METADATA_SIZE > 0);
  });

  test('NUMERIC_LIMITS has expected ranges', () => {
    assert.strictEqual(NUMERIC_LIMITS.MIN_IMPORTANCE, 0);
    assert.strictEqual(NUMERIC_LIMITS.MAX_IMPORTANCE, 1);
    assert.strictEqual(NUMERIC_LIMITS.MIN_LIMIT, 1);
    assert(NUMERIC_LIMITS.MAX_LIMIT > 0);
  });

  test('VALID_METADATA_FIELDS contains expected fields', () => {
    assert(VALID_METADATA_FIELDS.includes('importance'));
    assert(VALID_METADATA_FIELDS.includes('emotional_intensity'));
    assert(VALID_METADATA_FIELDS.includes('context'));
    assert(VALID_METADATA_FIELDS.includes('layer'));
    assert(VALID_METADATA_FIELDS.includes('custom'));
  });

  test('VALID_METADATA_FIELDS is frozen', () => {
    assert(Object.isFrozen(VALID_METADATA_FIELDS));
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
