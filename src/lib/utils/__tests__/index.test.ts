/**
 * @fileoverview Integration tests for the utils barrel export.
 *
 * Validates that all re-exported functions are accessible from `$lib/utils`
 * and behave as expected.
 *
 * @module utils/__tests__/index
 */

import { describe, it, expect } from 'vitest';
import {
	sanitizeResponseContent,
	isValidHttpUrl,
	compareVersion,
	transformFileName,
	removeEmojis,
	removeFormattings,
	cleanText,
	capitalizeFirstLetter,
	formatFileSize,
	approximateToHumanReadable,
	extractFrontmatter,
	findWordIndices,
	removeFirstHashWord
} from '../index';

describe('sanitizeResponseContent', () => {
	it('escapes < characters to &lt;', () => {
		const result = sanitizeResponseContent('hello < world');
		expect(result).toBe('hello &lt; world');
	});

	it('escapes > characters to &gt;', () => {
		const result = sanitizeResponseContent('hello > world');
		expect(result).toBe('hello &gt; world');
	});

	it('escapes both < and > in the same string', () => {
		const result = sanitizeResponseContent('<div>content</div>');
		expect(result).toBe('&lt;div&gt;content&lt;/div&gt;');
	});

	it('removes trailing incomplete special tokens', () => {
		const result = sanitizeResponseContent('hello<|im');
		expect(result).toBe('hello');
	});

	it('trims whitespace from output', () => {
		const result = sanitizeResponseContent('  hello  ');
		expect(result).toBe('hello');
	});

	it('replaces full special tokens with space', () => {
		const result = sanitizeResponseContent('before<|end|>after');
		expect(result).toBe('before after');
	});
});

describe('isValidHttpUrl', () => {
	it('returns true for valid http URL', () => {
		expect(isValidHttpUrl('http://example.com')).toBe(true);
	});

	it('returns true for valid https URL', () => {
		expect(isValidHttpUrl('https://example.com/path?query=1')).toBe(true);
	});

	it('returns false for non-URL strings', () => {
		expect(isValidHttpUrl('not-a-url')).toBe(false);
	});

	it('returns false for ftp URLs', () => {
		expect(isValidHttpUrl('ftp://example.com')).toBe(false);
	});
});

describe('compareVersion', () => {
	it('returns false when current is 0.0.0', () => {
		expect(compareVersion('2.0.0', '0.0.0')).toBe(false);
	});

	it('returns true when latest > current', () => {
		expect(compareVersion('2.0.0', '1.0.0')).toBe(true);
	});

	it('returns false when latest === current', () => {
		expect(compareVersion('1.0.0', '1.0.0')).toBe(false);
	});

	it('returns false when latest < current', () => {
		expect(compareVersion('1.0.0', '2.0.0')).toBe(false);
	});
});

describe('transformFileName', () => {
	it('converts to lowercase', () => {
		expect(transformFileName('MyFile.TXT')).toBe('myfiletxt');
	});

	it('replaces spaces with dashes', () => {
		expect(transformFileName('my file name')).toBe('my-file-name');
	});

	it('removes special characters', () => {
		expect(transformFileName('file@#name!.doc')).toBe('filenamedoc');
	});
});

describe('removeEmojis', () => {
	it('removes emojis from string', () => {
		expect(removeEmojis('Hello 😀 World')).toBe('Hello  World');
	});

	it('returns unchanged string when no emojis', () => {
		expect(removeEmojis('Hello World')).toBe('Hello World');
	});
});

describe('removeFormattings', () => {
	it('removes bold markdown formatting', () => {
		expect(removeFormattings('This is **bold** text')).toBe('This is bold text');
	});

	it('removes italic markdown formatting', () => {
		expect(removeFormattings('This is *italic* text')).toBe('This is italic text');
	});

	it('removes code blocks', () => {
		expect(removeFormattings('Before ```code``` after')).toBe('Before  after');
	});

	it('removes headers', () => {
		expect(removeFormattings('## Header')).toBe('Header');
	});
});

describe('cleanText', () => {
	it('removes emojis and formatting', () => {
		expect(cleanText('  **Hello** 😀  ').trim()).toBe('Hello');
	});
});

describe('capitalizeFirstLetter', () => {
	it('capitalizes the first letter', () => {
		expect(capitalizeFirstLetter('hello')).toBe('Hello');
	});

	it('handles single character', () => {
		expect(capitalizeFirstLetter('a')).toBe('A');
	});

	it('does not change already capitalized strings', () => {
		expect(capitalizeFirstLetter('Hello')).toBe('Hello');
	});
});

describe('formatFileSize', () => {
	it('formats bytes', () => {
		expect(formatFileSize(500)).toBe('500.0 B');
	});

	it('formats kilobytes', () => {
		expect(formatFileSize(1024)).toBe('1.0 KB');
	});

	it('formats megabytes', () => {
		expect(formatFileSize(1048576)).toBe('1.0 MB');
	});

	it('formats zero bytes', () => {
		expect(formatFileSize(0)).toBe('0 B');
	});

	it('returns "Unknown size" for null', () => {
		expect(formatFileSize(null)).toBe('Unknown size');
	});

	it('returns "Invalid size" for negative', () => {
		expect(formatFileSize(-1)).toBe('Invalid size');
	});
});

describe('approximateToHumanReadable', () => {
	it('formats seconds only', () => {
		expect(approximateToHumanReadable(5e9)).toBe('5s');
	});

	it('formats minutes and seconds', () => {
		expect(approximateToHumanReadable(125e9)).toBe('2m 5s');
	});

	it('formats hours, minutes, seconds', () => {
		expect(approximateToHumanReadable(3665e9)).toBe('1h 1m 5s');
	});
});

describe('extractFrontmatter', () => {
	it('extracts frontmatter from valid content', () => {
		const content = '"""\ntitle: Test\nauthor: Me\n"""\nBody text';
		const result = extractFrontmatter(content);
		expect(result).toEqual({ title: 'Test', author: 'Me' });
	});

	it('returns empty object when no frontmatter', () => {
		const content = 'No frontmatter here';
		const result = extractFrontmatter(content);
		expect(result).toEqual({});
	});
});

describe('findWordIndices', () => {
	it('finds bracketed words', () => {
		const result = findWordIndices('Hello [world] and [test]');
		expect(result).toHaveLength(2);
		expect(result[0]).toEqual({ word: 'world', startIndex: 6, endIndex: 12 });
		expect(result[1]).toEqual({ word: 'test', startIndex: 18, endIndex: 23 });
	});

	it('returns empty array when no brackets', () => {
		expect(findWordIndices('No brackets here')).toEqual([]);
	});
});

describe('removeFirstHashWord', () => {
	it('removes first word starting with #', () => {
		expect(removeFirstHashWord('hello #world foo')).toBe('hello foo');
	});

	it('returns unchanged string when no # word', () => {
		expect(removeFirstHashWord('hello world')).toBe('hello world');
	});
});
