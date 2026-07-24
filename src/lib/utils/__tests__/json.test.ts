/**
 * @fileoverview Tests for safe JSON parsing utility.
 *
 * @module utils/__tests__/json
 */

import { describe, it, expect } from 'vitest';
import { safeJsonParse } from '../json';

describe('safeJsonParse', () => {
	it('parses valid JSON objects and arrays', () => {
		expect(safeJsonParse('{"a":1,"b":[2,3]}', {})).toEqual({ a: 1, b: [2, 3] });
		expect(safeJsonParse('[1,2,3]', [])).toEqual([1, 2, 3]);
	});

	it('parses JSON primitives, including a literal null', () => {
		expect(safeJsonParse('42', 0)).toBe(42);
		expect(safeJsonParse('true', false)).toBe(true);
		expect(safeJsonParse('"hi"', '')).toBe('hi');
		// JSON.parse('null') === null — the parsed value wins over the fallback.
		expect(safeJsonParse('null', 'fallback')).toBe(null);
	});

	it('returns the fallback for malformed JSON instead of throwing', () => {
		expect(safeJsonParse('{not json}', { ok: true })).toEqual({ ok: true });
		expect(safeJsonParse('{"a":}', [])).toEqual([]);
		expect(safeJsonParse('undefined', 'fb')).toBe('fb');
	});

	it('returns the fallback for null/undefined/empty input', () => {
		expect(safeJsonParse(null, 'fb')).toBe('fb');
		expect(safeJsonParse(undefined, 42)).toBe(42);
		expect(safeJsonParse('', { empty: true })).toEqual({ empty: true });
	});

	it('preserves the fallback reference on failure (no clone)', () => {
		const fallback = { shared: true };
		expect(safeJsonParse('not-json', fallback)).toBe(fallback);
	});
});
