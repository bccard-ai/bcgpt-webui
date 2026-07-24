import { describe, it, expect } from 'vitest';
import { severityBadge, humanize, piiLabel, piiBadge, NEUTRAL_BADGE } from '../utils';

describe('severityBadge', () => {
	it('maps known severities to distinct styles and others to neutral', () => {
		expect(severityBadge('CRITICAL')).toContain('red');
		expect(severityBadge('WARNING')).toContain('amber');
		expect(severityBadge('INFO')).toBe(NEUTRAL_BADGE);
		expect(severityBadge('whatever')).toBe(NEUTRAL_BADGE);
	});
});

describe('humanize', () => {
	it('replaces underscores with spaces', () => {
		expect(humanize('user_login_failed')).toBe('user login failed');
		expect(humanize('plain')).toBe('plain');
	});
});

describe('piiLabel / piiBadge', () => {
	it('returns known PII labels (incl. localized)', () => {
		expect(piiLabel('email')).toBe('Email');
		expect(piiLabel('korean_rrn')).toBe('주민등록번호');
	});

	it('falls back to a humanized type for unknown PII', () => {
		expect(piiLabel('custom_secret_type')).toBe('custom secret type');
	});

	it('piiBadge falls back to NEUTRAL_BADGE for unknown types', () => {
		expect(piiBadge('totally_unknown')).toBe(NEUTRAL_BADGE);
	});
});
