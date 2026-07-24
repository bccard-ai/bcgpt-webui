/**
 * @fileoverview Tests for miscellaneous utility helpers.
 *
 * @module utils/__tests__/misc
 */

import { describe, it, expect } from 'vitest';
import { bestMatchingLanguage } from '../misc';
import { getLineCount } from '../text';

const SUPPORTED = [{ code: 'en-US' }, { code: 'ko-KR' }, { code: 'ja-JP' }];

describe('bestMatchingLanguage', () => {
	it('matches a preferred language prefix to a supported locale', () => {
		expect(bestMatchingLanguage(SUPPORTED, ['ko'], 'en-US')).toBe('ko-KR');
	});

	it('honors preference order (first matching preferred wins)', () => {
		expect(bestMatchingLanguage(SUPPORTED, ['fr', 'ja', 'ko'], 'en-US')).toBe('ja-JP');
	});

	it('matches an exact locale code', () => {
		expect(bestMatchingLanguage(SUPPORTED, ['en-US'], 'ko-KR')).toBe('en-US');
	});

	it('falls back to the default locale when nothing matches', () => {
		expect(bestMatchingLanguage(SUPPORTED, ['de', 'es'], 'en-US')).toBe('en-US');
	});
});

describe('getLineCount', () => {
	it('counts newline-separated lines', () => {
		expect(getLineCount('a\nb\nc')).toBe(3);
		expect(getLineCount('single line')).toBe(1);
	});

	it('returns 0 for empty/nullish input', () => {
		expect(getLineCount('')).toBe(0);
		expect(getLineCount(null)).toBe(0);
		expect(getLineCount(undefined)).toBe(0);
	});
});
