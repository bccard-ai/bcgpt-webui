/**
 * @fileoverview Tests for text extraction and formatting utilities.
 *
 * @module utils/__tests__/text
 */

import { describe, it, expect } from 'vitest';
import {
	extractSentences,
	extractSentencesForAudio,
	extractParagraphsForAudio,
	getMessageContentParts,
	removeDetails
} from '../text';
import { TTS_RESPONSE_SPLIT } from '$lib/types';

describe('extractSentences', () => {
	it('splits text on sentence boundaries', () => {
		expect(extractSentences('Hello world. How are you? I am fine!')).toEqual([
			'Hello world.',
			'How are you?',
			'I am fine!'
		]);
	});

	it('does not fragment on punctuation inside code blocks', () => {
		// The code block is protected from splitting (and stripped from audio output),
		// so this yields the two surrounding sentences — not one per internal dot.
		expect(extractSentences('Intro. ```x.y.z``` End.')).toHaveLength(2);
	});

	it('drops empty/whitespace-only fragments', () => {
		expect(extractSentences('   ')).toEqual([]);
	});
});

describe('extractSentencesForAudio', () => {
	it('merges a short leading fragment into the following sentence', () => {
		const out = extractSentencesForAudio(
			'No. This is a sufficiently long sentence with plenty of words to exceed the fifty character limit here.'
		);
		expect(out).toHaveLength(1);
		expect(out[0].startsWith('No.')).toBe(true);
	});

	it('keeps two already-long sentences separate', () => {
		const out = extractSentencesForAudio(
			'This first sentence is quite long and has more than enough words here. This second sentence is also long enough to remain on its own clearly.'
		);
		expect(out).toHaveLength(2);
	});
});

describe('extractParagraphsForAudio', () => {
	it('splits on blank lines', () => {
		expect(extractParagraphsForAudio('First paragraph here.\n\nSecond paragraph here.')).toEqual([
			'First paragraph here.',
			'Second paragraph here.'
		]);
	});
});

describe('removeDetails', () => {
	it('removes matching <details type="..."> blocks', () => {
		expect(removeDetails('a<details type="reasoning">hidden</details>b', ['reasoning'])).toBe('ab');
		expect(
			removeDetails('x<details type="tool_calls">y</details>z', ['reasoning', 'tool_calls'])
		).toBe('xz');
	});

	it('leaves non-matching detail blocks intact', () => {
		const input = 'a<details type="citations">keep</details>b';
		expect(removeDetails(input, ['reasoning'])).toBe(input);
	});
});

describe('getMessageContentParts', () => {
	it('strips reasoning/tool_calls details then sentence-chunks by default', () => {
		const out = getMessageContentParts(
			'<details type="reasoning">secret thinking</details>The weather is nice today and the sky is clear blue.'
		);
		const joined = out.join(' ');
		expect(joined).not.toContain('secret thinking'); // reasoning stripped
		expect(joined).toContain('weather');
	});

	it('NONE split returns a single cleaned part (details still stripped)', () => {
		const out = getMessageContentParts(
			'<details type="tool_calls">call</details>Just some text here.',
			TTS_RESPONSE_SPLIT.NONE
		);
		expect(out).toHaveLength(1);
		expect(out[0]).not.toContain('call');
		expect(out[0]).toContain('Just some text here');
	});

	it('PARAGRAPHS split breaks on blank lines', () => {
		const out = getMessageContentParts(
			'First para here.\n\nSecond para here.',
			TTS_RESPONSE_SPLIT.PARAGRAPHS
		);
		expect(out).toEqual(['First para here.', 'Second para here.']);
	});
});
