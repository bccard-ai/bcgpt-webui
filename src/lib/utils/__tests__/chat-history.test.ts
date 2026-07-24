/**
 * @fileoverview Tests for chat history conversion utilities.
 *
 * @module utils/__tests__/chat-history
 */

import { describe, it, expect } from 'vitest';
import { convertMessagesToHistory, createMessagesList } from '../chat-history';

describe('convertMessagesToHistory', () => {
	it('returns an empty history for no messages', () => {
		expect(convertMessagesToHistory([])).toEqual({ messages: {}, currentId: null });
	});

	it('builds a linear parent/child chain and preserves message fields', () => {
		const history = convertMessagesToHistory([
			{ role: 'user', content: 'one' },
			{ role: 'assistant', content: 'two' },
			{ role: 'user', content: 'three' }
		]);

		// String (uuid) keys preserve insertion order in JS objects.
		const [first, second, third] = Object.keys(history.messages).map((id) => history.messages[id]);

		expect(Object.keys(history.messages)).toHaveLength(3);
		expect(history.currentId).toBe(third.id);

		expect(first.parentId).toBeNull();
		expect(first.content).toBe('one');
		expect(first.childrenIds).toEqual([second.id]);

		expect(second.parentId).toBe(first.id);
		expect(second.childrenIds).toEqual([third.id]);

		expect(third.parentId).toBe(second.id);
		expect(third.childrenIds).toEqual([]);
	});
});

describe('createMessagesList', () => {
	it('returns an empty list for a null message id', () => {
		expect(createMessagesList({ messages: {}, currentId: null }, null)).toEqual([]);
	});

	it('round-trips: convert then flatten yields the original order', () => {
		const history = convertMessagesToHistory([
			{ role: 'user', content: 'a' },
			{ role: 'assistant', content: 'b' },
			{ role: 'user', content: 'c' }
		]);
		const list = createMessagesList(history, history.currentId);
		expect(list.map((m) => m.content)).toEqual(['a', 'b', 'c']);
	});

	it('walks the correct branch when the tree forks', () => {
		const history = {
			messages: {
				r: { id: 'r', parentId: null, childrenIds: ['a', 'b'], content: 'root' },
				a: { id: 'a', parentId: 'r', childrenIds: [], content: 'A' },
				b: { id: 'b', parentId: 'r', childrenIds: [], content: 'B' }
			},
			currentId: 'a'
		};
		expect(createMessagesList(history, 'a').map((m) => m.content)).toEqual(['root', 'A']);
		expect(createMessagesList(history, 'b').map((m) => m.content)).toEqual(['root', 'B']);
	});
});
