/**
 * @fileoverview Tests for model provider detection and icon resolution.
 *
 * @module utils/__tests__/providers
 */

import { describe, it, expect } from 'vitest';
import { getModelProvider, getProviderIconPath, getModelIconUrl } from '../providers';

describe('getModelProvider', () => {
	it('prefers owned_by over the id pattern', () => {
		// id looks like OpenAI, but owned_by wins.
		expect(getModelProvider({ id: 'gpt-4', owned_by: 'ollama' })).toBe('ollama');
	});

	it('matches owned_by case-insensitively', () => {
		expect(getModelProvider({ id: 'whatever', owned_by: 'OpenAI' })).toBe('openai');
	});

	it('falls back to id patterns when owned_by is unknown/absent', () => {
		expect(getModelProvider({ id: 'claude-3-opus', owned_by: 'litellm' })).toBe('claude');
		expect(getModelProvider({ id: 'gemini-1.5-pro' })).toBe('gemini');
		expect(getModelProvider({ id: 'o1-preview' })).toBe('openai');
		expect(getModelProvider({ id: 'sonar-medium' })).toBe('perplexity');
		expect(getModelProvider({ id: 'deepseek-chat' })).toBe('deepseek');
	});

	it('returns unknown for unrecognized models', () => {
		expect(getModelProvider({ id: 'some-random-model' })).toBe('unknown');
	});
});

describe('getProviderIconPath', () => {
	it('maps providers to icon paths', () => {
		expect(getProviderIconPath('openai')).toBe('/static/providers/openai.svg');
		expect(getProviderIconPath('claude')).toBe('/static/providers/claude.svg');
	});

	it('uses the favicon for unknown', () => {
		expect(getProviderIconPath('unknown')).toBe('/static/favicon.png');
	});
});

describe('getModelIconUrl', () => {
	it('returns a custom profile image when set and not the default favicon', () => {
		expect(getModelIconUrl({ id: 'gpt-4', profileImageUrl: '/custom/icon.png' })).toBe(
			'/custom/icon.png'
		);
	});

	it('falls through to the provider icon when the image is the default favicon', () => {
		expect(getModelIconUrl({ id: 'gpt-4', profileImageUrl: '/static/favicon.png' })).toBe(
			'/static/providers/openai.svg'
		);
	});

	it('uses the provider icon when no profile image is set', () => {
		expect(getModelIconUrl({ id: 'claude-3', owned_by: 'anthropic' })).toBe(
			'/static/providers/claude.svg'
		);
	});
});
