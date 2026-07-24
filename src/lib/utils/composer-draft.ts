const COMPOSER_DRAFT_STORAGE_PREFIX = 'bcgpt:chat-composer-draft:v1:';

export const COMPOSER_DRAFT_SCHEMA_VERSION = 1 as const;
export const COMPOSER_DRAFT_TTL_MS = 7 * 24 * 60 * 60 * 1000;
export const COMPOSER_DRAFT_MAX_PER_OWNER = 10;
export const COMPOSER_DRAFT_MAX_TEXT_LENGTH = 100_000;
export const COMPOSER_DRAFT_MAX_TOOL_IDS = 64;

const MAX_ID_LENGTH = 256;

export interface StorageLike {
	readonly length: number;
	getItem(key: string): string | null;
	setItem(key: string, value: string): void;
	removeItem(key: string): void;
	key(index: number): string | null;
}

export interface ComposerDraftScope {
	ownerId: string;
	chatId?: string | null;
}

export interface ComposerDraftValue {
	prompt: string;
	selectedToolIds?: readonly string[];
	imageGenerationEnabled?: boolean;
	webSearchEnabled?: boolean;
	contextCompressionEnabled?: boolean;
	smartQueryEnabled?: boolean;
}

export interface ComposerDraft extends Required<ComposerDraftValue> {
	updatedAt: number;
	expiresAt: number;
}

interface StoredComposerDraft extends ComposerDraft {
	version: typeof COMPOSER_DRAFT_SCHEMA_VERSION;
	ownerId: string;
	chatId: string | null;
}

interface DraftOptions {
	storage?: StorageLike;
	now?: number;
}

interface NormalizedScope {
	ownerId: string;
	chatId: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasControlCharacter(value: string): boolean {
	return Array.from(value).some((character) => {
		const codePoint = character.codePointAt(0) ?? 0;
		return codePoint <= 0x1f || codePoint === 0x7f;
	});
}

function normalizeId(value: unknown): string | null {
	if (typeof value !== 'string') return null;
	const normalized = value.trim();
	if (!normalized || normalized.length > MAX_ID_LENGTH || hasControlCharacter(normalized)) {
		return null;
	}
	return normalized;
}

function normalizeScope(scope: ComposerDraftScope): NormalizedScope | null {
	if (!isRecord(scope)) return null;
	const ownerId = normalizeId(scope.ownerId);
	if (!ownerId) return null;

	if (scope.chatId === undefined || scope.chatId === null || scope.chatId === '') {
		return { ownerId, chatId: null };
	}

	const chatId = normalizeId(scope.chatId);
	return chatId ? { ownerId, chatId } : null;
}

function normalizeValue(value: ComposerDraftValue): Required<ComposerDraftValue> {
	const prompt =
		typeof value?.prompt === 'string' ? value.prompt.slice(0, COMPOSER_DRAFT_MAX_TEXT_LENGTH) : '';
	const selectedToolIds: string[] = [];
	const seen = new Set<string>();

	for (const candidate of Array.isArray(value?.selectedToolIds) ? value.selectedToolIds : []) {
		const id = normalizeId(candidate);
		if (!id || seen.has(id)) continue;
		seen.add(id);
		selectedToolIds.push(id);
		if (selectedToolIds.length >= COMPOSER_DRAFT_MAX_TOOL_IDS) break;
	}

	return {
		prompt,
		selectedToolIds,
		imageGenerationEnabled: value?.imageGenerationEnabled === true,
		webSearchEnabled: value?.webSearchEnabled === true,
		contextCompressionEnabled: value?.contextCompressionEnabled === true,
		smartQueryEnabled: value?.smartQueryEnabled === true
	};
}

function valuesEqual(left: ComposerDraftValue, right: ComposerDraftValue): boolean {
	const a = normalizeValue(left);
	const b = normalizeValue(right);
	return (
		a.prompt === b.prompt &&
		a.imageGenerationEnabled === b.imageGenerationEnabled &&
		a.webSearchEnabled === b.webSearchEnabled &&
		a.contextCompressionEnabled === b.contextCompressionEnabled &&
		a.smartQueryEnabled === b.smartQueryEnabled &&
		a.selectedToolIds.length === b.selectedToolIds.length &&
		a.selectedToolIds.every((id, index) => id === b.selectedToolIds[index])
	);
}

function resolveStorage(storage?: StorageLike): StorageLike | null {
	if (storage) return storage;
	try {
		return globalThis.localStorage ?? null;
	} catch {
		return null;
	}
}

function normalizeNow(now?: number): number {
	return typeof now === 'number' && Number.isSafeInteger(now) && now >= 0 ? now : Date.now();
}

function ownerPrefix(ownerId: string): string {
	return `${COMPOSER_DRAFT_STORAGE_PREFIX}${encodeURIComponent(ownerId)}:`;
}

export function getComposerDraftKey(scope: ComposerDraftScope): string | null {
	const normalized = normalizeScope(scope);
	if (!normalized) return null;
	const suffix =
		normalized.chatId === null ? 'new' : `chat:${encodeURIComponent(normalized.chatId)}`;
	return `${ownerPrefix(normalized.ownerId)}${suffix}`;
}

function storageKeys(storage: StorageLike): string[] | null {
	try {
		const keys: string[] = [];
		for (let index = 0; index < storage.length; index += 1) {
			const key = storage.key(index);
			if (key !== null) keys.push(key);
		}
		return keys;
	} catch {
		return null;
	}
}

function safeRemove(storage: StorageLike, key: string): boolean {
	try {
		storage.removeItem(key);
		return true;
	} catch {
		return false;
	}
}

function parseStoredDraft(
	raw: string,
	expectedScope: NormalizedScope,
	now: number
): StoredComposerDraft | null {
	let value: unknown;
	try {
		value = JSON.parse(raw);
	} catch {
		return null;
	}

	if (!isRecord(value) || value.version !== COMPOSER_DRAFT_SCHEMA_VERSION) return null;
	const storedScope = normalizeScope({
		ownerId: value.ownerId as string,
		chatId: value.chatId as string | null
	});
	if (
		!storedScope ||
		storedScope.ownerId !== expectedScope.ownerId ||
		storedScope.chatId !== expectedScope.chatId ||
		value.ownerId !== storedScope.ownerId ||
		value.chatId !== storedScope.chatId
	) {
		return null;
	}

	if (
		typeof value.prompt !== 'string' ||
		value.prompt.length > COMPOSER_DRAFT_MAX_TEXT_LENGTH ||
		!Array.isArray(value.selectedToolIds) ||
		value.selectedToolIds.length > COMPOSER_DRAFT_MAX_TOOL_IDS ||
		typeof value.updatedAt !== 'number' ||
		!Number.isSafeInteger(value.updatedAt) ||
		value.updatedAt < 0 ||
		typeof value.expiresAt !== 'number' ||
		!Number.isSafeInteger(value.expiresAt) ||
		value.expiresAt !== value.updatedAt + COMPOSER_DRAFT_TTL_MS ||
		value.expiresAt <= now
	) {
		return null;
	}

	const normalizedValue = normalizeValue({
		prompt: value.prompt,
		selectedToolIds: value.selectedToolIds as string[],
		imageGenerationEnabled: value.imageGenerationEnabled === true,
		webSearchEnabled: value.webSearchEnabled === true,
		contextCompressionEnabled: value.contextCompressionEnabled === true,
		smartQueryEnabled: value.smartQueryEnabled === true
	});

	if (
		!valuesEqual(normalizedValue, value as unknown as ComposerDraftValue) ||
		value.imageGenerationEnabled !== normalizedValue.imageGenerationEnabled ||
		value.webSearchEnabled !== normalizedValue.webSearchEnabled ||
		value.contextCompressionEnabled !== normalizedValue.contextCompressionEnabled ||
		value.smartQueryEnabled !== normalizedValue.smartQueryEnabled
	) {
		return null;
	}

	return {
		version: COMPOSER_DRAFT_SCHEMA_VERSION,
		ownerId: storedScope.ownerId,
		chatId: storedScope.chatId,
		...normalizedValue,
		updatedAt: value.updatedAt,
		expiresAt: value.expiresAt
	};
}

export function readComposerDraft(
	scope: ComposerDraftScope,
	options: DraftOptions = {}
): ComposerDraft | null {
	const normalizedScope = normalizeScope(scope);
	const key = getComposerDraftKey(scope);
	const storage = resolveStorage(options.storage);
	if (!normalizedScope || !key || !storage) return null;

	let raw: string | null;
	try {
		raw = storage.getItem(key);
	} catch {
		return null;
	}
	if (raw === null) return null;

	const draft = parseStoredDraft(raw, normalizedScope, normalizeNow(options.now));
	if (!draft) {
		safeRemove(storage, key);
		return null;
	}

	const { version: _version, ownerId: _ownerId, chatId: _chatId, ...publicDraft } = draft;
	return publicDraft;
}

function ownerEntries(storage: StorageLike, ownerId: string, now: number) {
	const prefix = ownerPrefix(ownerId);
	const keys = storageKeys(storage);
	if (!keys) return null;

	const entries: Array<{ key: string; updatedAt: number }> = [];
	for (const key of keys.filter((candidate) => candidate.startsWith(prefix))) {
		let raw: string | null;
		try {
			raw = storage.getItem(key);
		} catch {
			return null;
		}
		if (raw === null) continue;

		let parsed: Record<string, unknown> | null = null;
		try {
			const candidate = JSON.parse(raw);
			parsed = isRecord(candidate) ? candidate : null;
		} catch {
			// Removed below.
		}

		if (
			!parsed ||
			parsed.version !== COMPOSER_DRAFT_SCHEMA_VERSION ||
			typeof parsed.updatedAt !== 'number' ||
			!Number.isSafeInteger(parsed.updatedAt) ||
			typeof parsed.expiresAt !== 'number' ||
			parsed.expiresAt <= now
		) {
			safeRemove(storage, key);
			continue;
		}
		entries.push({ key, updatedAt: parsed.updatedAt });
	}
	return entries;
}

function pruneOwnerDrafts(
	storage: StorageLike,
	ownerId: string,
	now: number,
	keep: number
): boolean {
	const entries = ownerEntries(storage, ownerId, now);
	if (!entries) return false;
	entries.sort(
		(left, right) => right.updatedAt - left.updatedAt || right.key.localeCompare(left.key)
	);
	return entries.slice(keep).every(({ key }) => safeRemove(storage, key));
}

export function removeComposerDraft(
	scope: ComposerDraftScope,
	options: DraftOptions = {}
): boolean {
	const key = getComposerDraftKey(scope);
	const storage = resolveStorage(options.storage);
	return Boolean(key && storage && safeRemove(storage, key));
}

export function writeComposerDraft(
	scope: ComposerDraftScope,
	value: ComposerDraftValue,
	options: DraftOptions = {}
): boolean {
	const normalizedScope = normalizeScope(scope);
	const key = getComposerDraftKey(scope);
	const storage = resolveStorage(options.storage);
	if (!normalizedScope || !key || !storage) return false;

	const normalizedValue = normalizeValue(value);
	if (!normalizedValue.prompt.trim()) return safeRemove(storage, key);

	const now = normalizeNow(options.now);
	// Collect expired/corrupt owner entries before writing. The cap is enforced
	// after the write so updating an existing scope never evicts another draft.
	ownerEntries(storage, normalizedScope.ownerId, now);

	const envelope: StoredComposerDraft = {
		version: COMPOSER_DRAFT_SCHEMA_VERSION,
		ownerId: normalizedScope.ownerId,
		chatId: normalizedScope.chatId,
		...normalizedValue,
		updatedAt: now,
		expiresAt: now + COMPOSER_DRAFT_TTL_MS
	};

	try {
		storage.setItem(key, JSON.stringify(envelope));
		pruneOwnerDrafts(storage, normalizedScope.ownerId, now, COMPOSER_DRAFT_MAX_PER_OWNER);
		return true;
	} catch {
		// One bounded retry after freeing the oldest owner-scoped entry.
		pruneOwnerDrafts(
			storage,
			normalizedScope.ownerId,
			now,
			Math.max(0, COMPOSER_DRAFT_MAX_PER_OWNER - 2)
		);
		try {
			storage.setItem(key, JSON.stringify(envelope));
			pruneOwnerDrafts(storage, normalizedScope.ownerId, now, COMPOSER_DRAFT_MAX_PER_OWNER);
			return true;
		} catch {
			return false;
		}
	}
}

export function removeComposerDraftIfMatches(
	scope: ComposerDraftScope,
	value: ComposerDraftValue,
	options: DraftOptions = {}
): boolean {
	const current = readComposerDraft(scope, options);
	if (!current) return true;
	return valuesEqual(current, value) ? removeComposerDraft(scope, options) : false;
}

/**
 * Migrates the old, unscoped `chat-input-*` payload without carrying file
 * objects or image data URLs into the safer draft envelope.
 */
export function migrateLegacyComposerDraft(
	scope: ComposerDraftScope,
	legacyKey: string,
	options: DraftOptions = {}
): ComposerDraft | null {
	const storage = resolveStorage(options.storage);
	if (!storage) return null;
	if (readComposerDraft(scope, options)) {
		safeRemove(storage, legacyKey);
		return readComposerDraft(scope, options);
	}

	let raw: string | null;
	try {
		raw = storage.getItem(legacyKey);
	} catch {
		return null;
	}
	if (raw === null) return null;

	let legacy: unknown;
	try {
		legacy = JSON.parse(raw);
	} catch {
		safeRemove(storage, legacyKey);
		return null;
	}

	if (isRecord(legacy)) {
		writeComposerDraft(
			scope,
			{
				prompt: typeof legacy.prompt === 'string' ? legacy.prompt : '',
				selectedToolIds: Array.isArray(legacy.selectedToolIds)
					? (legacy.selectedToolIds as string[])
					: [],
				imageGenerationEnabled: legacy.imageGenerationEnabled === true,
				webSearchEnabled: legacy.webSearchEnabled === true,
				contextCompressionEnabled: legacy.contextCompressionEnabled === true,
				smartQueryEnabled: legacy.smartQueryEnabled === true
			},
			options
		);
	}
	safeRemove(storage, legacyKey);
	return readComposerDraft(scope, options);
}
