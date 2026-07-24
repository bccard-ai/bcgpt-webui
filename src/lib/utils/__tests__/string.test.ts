/**
 * @fileoverview Tests for string token replacement utilities.
 *
 * @module utils/__tests__/string
 */

import { describe, it, expect } from 'vitest';
import { replaceTokens } from '../string';

describe('replaceTokens', () => {
	it('replaces {{user}} and {{char}} case-insensitively', () => {
		expect(replaceTokens('Hi {{user}}, I am {{char}}', null, 'Bot', 'Alice')).toBe(
			'Hi Alice, I am Bot'
		);
		expect(replaceTokens('{{USER}} and {{Char}}', null, 'Bot', 'Alice')).toBe('Alice and Bot');
	});

	it('does not replace tokens inside fenced code blocks', () => {
		const input = 'before {{user}}\n```\n{{user}}\n```\nafter {{user}}';
		const out = replaceTokens(input, null, 'C', 'U');
		expect(out).toContain('before U');
		expect(out).toContain('after U');
		expect(out).toContain('```\n{{user}}\n```'); // untouched inside the fence
	});

	it('does not replace tokens inside inline code spans', () => {
		const out = replaceTokens('text {{user}} `{{user}}`', null, 'C', 'U');
		expect(out).toBe('text U `{{user}}`');
	});

	it('leaves tokens untouched when char/user are not provided', () => {
		expect(replaceTokens('Hi {{user}} {{char}}', null, undefined, undefined)).toBe(
			'Hi {{user}} {{char}}'
		);
	});

	it('expands bracketed citations into source_id tags when sourceIds are given', () => {
		const out = replaceTokens('See [1] and [2]', ['srcA', 'srcB'], 'C', 'U');
		expect(out).toContain('<source_id data="1" title="srcA" />');
		expect(out).toContain('<source_id data="2" title="srcB" />');
	});

	it('returns content unchanged when there are no tokens', () => {
		expect(replaceTokens('just plain text', null, 'C', 'U')).toBe('just plain text');
	});
});
