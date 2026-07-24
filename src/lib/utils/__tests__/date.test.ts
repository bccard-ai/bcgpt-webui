/**
 * @fileoverview Tests for date and time utility functions.
 *
 * @module utils/__tests__/date
 */

import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { getTimeRange } from '../date';

// Fixed "now" — 2025-06-15 12:00 local (mid-month/mid-day avoids DST & boundary edges).
const NOW = new Date(2025, 5, 15, 12, 0, 0);
// getTimeRange expects a Unix timestamp in *seconds*.
const toTs = (d: Date) => Math.floor(d.getTime() / 1000);

describe('getTimeRange', () => {
	beforeAll(() => {
		vi.useFakeTimers();
		vi.setSystemTime(NOW);
	});
	afterAll(() => {
		vi.useRealTimers();
	});

	it('classifies the same day as Today', () => {
		expect(getTimeRange(toTs(new Date(2025, 5, 15, 9, 0, 0)))).toBe('Today');
	});

	it('classifies the prior calendar day as Yesterday', () => {
		expect(getTimeRange(toTs(new Date(2025, 5, 14, 12, 0, 0)))).toBe('Yesterday');
	});

	it('classifies within a week as Previous 7 days', () => {
		expect(getTimeRange(toTs(new Date(2025, 5, 11, 12, 0, 0)))).toBe('Previous 7 days');
	});

	it('classifies within a month as Previous 30 days', () => {
		expect(getTimeRange(toTs(new Date(2025, 4, 26, 12, 0, 0)))).toBe('Previous 30 days');
	});

	it('classifies an older month in the same year by its month name', () => {
		const d = new Date(2025, 3, 16, 12, 0, 0); // ~60 days ago, same year
		expect(getTimeRange(toTs(d))).toBe(d.toLocaleString('default', { month: 'long' }));
	});

	it('classifies a previous year by its year', () => {
		expect(getTimeRange(toTs(new Date(2024, 4, 11, 12, 0, 0)))).toBe('2024');
	});
});
