/**
 * @fileoverview Tests for prompt template utilities.
 *
 * @module utils/__tests__/prompt
 */

// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { promptTemplate, titleGenerationTemplate } from '../prompt';

describe('promptTemplate', () => {
	it('substitutes user name and location', () => {
		expect(promptTemplate('Hi {{USER_NAME}} from {{USER_LOCATION}}', 'Alice', 'NYC')).toBe(
			'Hi Alice from NYC'
		);
	});

	it('uses LOCATION_UNKNOWN when no location is provided', () => {
		expect(promptTemplate('loc: {{USER_LOCATION}}', 'Bob')).toBe('loc: LOCATION_UNKNOWN');
	});

	it('leaves a template without known placeholders unchanged', () => {
		expect(promptTemplate('nothing to replace here')).toBe('nothing to replace here');
	});
});

describe('titleGenerationTemplate', () => {
	it('replaces {{prompt}} with the full prompt', () => {
		expect(titleGenerationTemplate('Title: {{prompt}}', 'hello world')).toBe('Title: hello world');
	});

	it('supports start and end slicing', () => {
		expect(titleGenerationTemplate('{{prompt:start:5}}', 'hello world')).toBe('hello');
		expect(titleGenerationTemplate('{{prompt:end:4}}', 'hello world')).toBe('orld');
	});

	it('middletruncate keeps head and tail around an ellipsis', () => {
		const out = titleGenerationTemplate('{{prompt:middletruncate:10}}', '0123456789ABCDEFGHIJ');
		expect(out.startsWith('01234')).toBe(true);
		expect(out.endsWith('FGHIJ')).toBe(true);
		expect(out).toContain('...');
	});

	it('middletruncate returns the prompt unchanged when short enough', () => {
		expect(titleGenerationTemplate('{{prompt:middletruncate:50}}', 'short')).toBe('short');
	});
});
