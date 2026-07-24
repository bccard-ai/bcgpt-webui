import { describe, expect, it } from 'vitest';
import {
	COMPOSER_DRAFT_MAX_PER_OWNER,
	COMPOSER_DRAFT_MAX_TEXT_LENGTH,
	COMPOSER_DRAFT_TTL_MS,
	getComposerDraftKey,
	migrateLegacyComposerDraft,
	readComposerDraft,
	removeComposerDraftIfMatches,
	writeComposerDraft,
	type StorageLike
} from '../composer-draft';

class MemoryStorage implements StorageLike {
	private values = new Map<string, string>();

	get length() {
		return this.values.size;
	}

	getItem(key: string) {
		return this.values.get(key) ?? null;
	}

	setItem(key: string, value: string) {
		this.values.set(key, value);
	}

	removeItem(key: string) {
		this.values.delete(key);
	}

	key(index: number) {
		return [...this.values.keys()][index] ?? null;
	}
}

const NOW = 1_800_000_000_000;

describe('composer draft storage', () => {
	it('isolates drafts by owner and chat scope', () => {
		const storage = new MemoryStorage();
		const scopes = [
			{ ownerId: 'owner:a' },
			{ ownerId: 'owner:a', chatId: 'chat:1' },
			{ ownerId: 'owner:b', chatId: 'chat:1' }
		] as const;

		scopes.forEach((scope, index) => {
			expect(
				writeComposerDraft(scope, { prompt: `draft-${index}` }, { storage, now: NOW + index })
			).toBe(true);
		});

		expect(new Set(scopes.map(getComposerDraftKey)).size).toBe(3);
		expect(
			scopes.map((scope) => readComposerDraft(scope, { storage, now: NOW + 10 })?.prompt)
		).toEqual(['draft-0', 'draft-1', 'draft-2']);
	});

	it('round-trips bounded text, unique tools, and feature flags', () => {
		const storage = new MemoryStorage();
		const scope = { ownerId: 'owner-1', chatId: 'chat-1' };
		expect(
			writeComposerDraft(
				scope,
				{
					prompt: 'x'.repeat(COMPOSER_DRAFT_MAX_TEXT_LENGTH + 20),
					selectedToolIds: [' search ', 'search', '', 'calculator'],
					webSearchEnabled: true,
					smartQueryEnabled: true
				},
				{ storage, now: NOW }
			)
		).toBe(true);

		const draft = readComposerDraft(scope, { storage, now: NOW + 1 });
		expect(draft?.prompt).toHaveLength(COMPOSER_DRAFT_MAX_TEXT_LENGTH);
		expect(draft?.selectedToolIds).toEqual(['search', 'calculator']);
		expect(draft).toMatchObject({ webSearchEnabled: true, smartQueryEnabled: true });
	});

	it('removes corrupt and expired envelopes', () => {
		const storage = new MemoryStorage();
		const scope = { ownerId: 'owner-1' };
		const key = getComposerDraftKey(scope)!;
		storage.setItem(key, '{not-json');
		expect(readComposerDraft(scope, { storage, now: NOW })).toBeNull();
		expect(storage.getItem(key)).toBeNull();

		writeComposerDraft(scope, { prompt: 'expires' }, { storage, now: NOW });
		expect(readComposerDraft(scope, { storage, now: NOW + COMPOSER_DRAFT_TTL_MS })).toBeNull();
		expect(storage.getItem(key)).toBeNull();
	});

	it('removes an existing draft when the text becomes empty', () => {
		const storage = new MemoryStorage();
		const scope = { ownerId: 'owner-1' };
		writeComposerDraft(scope, { prompt: 'keep me' }, { storage, now: NOW });
		expect(writeComposerDraft(scope, { prompt: '  ' }, { storage, now: NOW + 1 })).toBe(true);
		expect(readComposerDraft(scope, { storage, now: NOW + 2 })).toBeNull();
	});

	it('keeps at most ten recent drafts for one owner', () => {
		const storage = new MemoryStorage();
		for (let index = 0; index < COMPOSER_DRAFT_MAX_PER_OWNER + 3; index += 1) {
			writeComposerDraft(
				{ ownerId: 'owner-1', chatId: `chat-${index}` },
				{ prompt: `draft-${index}` },
				{ storage, now: NOW + index }
			);
		}
		expect(storage.length).toBe(COMPOSER_DRAFT_MAX_PER_OWNER);
		expect(
			readComposerDraft({ ownerId: 'owner-1', chatId: 'chat-0' }, { storage, now: NOW + 20 })
		).toBeNull();
		expect(
			readComposerDraft({ ownerId: 'owner-1', chatId: 'chat-12' }, { storage, now: NOW + 20 })
				?.prompt
		).toBe('draft-12');

		writeComposerDraft(
			{ ownerId: 'owner-1', chatId: 'chat-12' },
			{ prompt: 'updated' },
			{ storage, now: NOW + 21 }
		);
		expect(storage.length).toBe(COMPOSER_DRAFT_MAX_PER_OWNER);
		expect(
			readComposerDraft({ ownerId: 'owner-1', chatId: 'chat-12' }, { storage, now: NOW + 22 })
				?.prompt
		).toBe('updated');
	});

	it('only removes an accepted revision when no newer edit replaced it', () => {
		const storage = new MemoryStorage();
		const scope = { ownerId: 'owner-1' };
		writeComposerDraft(scope, { prompt: 'submitted' }, { storage, now: NOW });
		writeComposerDraft(scope, { prompt: 'new edit' }, { storage, now: NOW + 1 });

		expect(
			removeComposerDraftIfMatches(scope, { prompt: 'submitted' }, { storage, now: NOW + 2 })
		).toBe(false);
		expect(readComposerDraft(scope, { storage, now: NOW + 2 })?.prompt).toBe('new edit');
		expect(
			removeComposerDraftIfMatches(scope, { prompt: 'new edit' }, { storage, now: NOW + 2 })
		).toBe(true);
	});

	it('migrates legacy text and settings without retaining attachment payloads', () => {
		const storage = new MemoryStorage();
		const scope = { ownerId: 'owner-1', chatId: 'chat-1' };
		storage.setItem(
			'chat-input-chat-1',
			JSON.stringify({
				prompt: 'legacy draft',
				files: [{ type: 'image', url: 'data:image/png;base64,sensitive' }],
				selectedToolIds: ['search'],
				webSearchEnabled: true
			})
		);

		const draft = migrateLegacyComposerDraft(scope, 'chat-input-chat-1', { storage, now: NOW });
		expect(draft).toMatchObject({
			prompt: 'legacy draft',
			selectedToolIds: ['search'],
			webSearchEnabled: true
		});
		expect(storage.getItem('chat-input-chat-1')).toBeNull();
		expect(JSON.stringify(draft)).not.toContain('sensitive');
	});

	it('fails softly when browser storage is unavailable', () => {
		const storage: StorageLike = {
			length: 0,
			getItem: () => {
				throw new Error('denied');
			},
			setItem: () => {
				throw new Error('denied');
			},
			removeItem: () => {
				throw new Error('denied');
			},
			key: () => null
		};
		expect(readComposerDraft({ ownerId: 'owner-1' }, { storage, now: NOW })).toBeNull();
		expect(
			writeComposerDraft({ ownerId: 'owner-1' }, { prompt: 'draft' }, { storage, now: NOW })
		).toBe(false);
	});
});
