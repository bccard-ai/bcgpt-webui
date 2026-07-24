/**
 * @fileoverview Tests for chat import detection and conversion.
 *
 * @module utils/__tests__/chat-import
 */

import { describe, it, expect } from 'vitest';
import { getImportOrigin, convertOpenAIChats } from '../chat-import';

describe('getImportOrigin', () => {
	it('detects an OpenAI export by the `mapping` key', () => {
		expect(getImportOrigin([{ mapping: {} }])).toBe('openai');
	});

	it('defaults to webui otherwise', () => {
		expect(getImportOrigin([{ title: 'x', history: {} }])).toBe('bcgpt');
	});
});

describe('convertOpenAIChats', () => {
	const conversation = {
		id: 'c1',
		title: 'Imported',
		create_time: 123,
		mapping: {
			// Root node with no message — must be skipped.
			root: { id: 'root', message: null, parent: null, children: ['u1'] },
			u1: {
				id: 'u1',
				message: { author: { role: 'user' }, content: { parts: ['Hi'] } },
				parent: 'root',
				children: ['a1']
			},
			a1: {
				id: 'a1',
				message: { author: { role: 'assistant' }, content: { parts: ['Hello!'] } },
				parent: 'u1',
				children: []
			}
		}
	};

	it('converts a valid OpenAI conversation, skipping the empty root node', () => {
		const out = convertOpenAIChats([conversation]);
		expect(out).toHaveLength(1);
		expect(out[0].id).toBe('c1');
		expect(out[0].title).toBe('Imported');

		const msgs = out[0].chat.messages;
		expect(msgs).toHaveLength(2); // root skipped
		expect(msgs[0]).toMatchObject({ role: 'user', content: 'Hi', parentId: null });
		expect(msgs[1]).toMatchObject({ role: 'assistant', content: 'Hello!', parentId: 'u1' });
		expect(out[0].chat.history.currentId).toBe('a1');
	});

	it('drops conversations that validate to empty', () => {
		const empty = {
			id: 'e',
			title: 'Empty',
			create_time: 1,
			mapping: { r: { id: 'r', message: null, parent: null, children: [] } }
		};
		expect(convertOpenAIChats([empty])).toHaveLength(0);
	});
});
