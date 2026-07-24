import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function source(path: string): string {
	return readFileSync(resolve(process.cwd(), path), 'utf8');
}

describe('open-moai chat adoption wiring', () => {
	it('persists drafts from both composer surfaces with the exact Svelte callback contract', () => {
		const chat = source('src/lib/components/chat/Chat.svelte');
		const placeholder = source('src/lib/components/chat/Placeholder.svelte');

		expect(chat.match(/onchange=\{handleComposerInputChange\}/gu)).toHaveLength(2);
		expect(chat).toContain(
			'removeComposerDraftIfMatches(submittedDraftScope, submittedDraftValue)'
		);
		expect(chat).toContain("window.addEventListener('pagehide', flushComposerDraft)");
		expect(chat).not.toContain('onChange={(input)');
		expect(placeholder).toContain('{onchange}');
	});

	it('exposes citation list and modal as keyboard-operable labelled disclosures', () => {
		const citations = source('src/lib/components/chat/Messages/Citations.svelte');
		const citationModal = source('src/lib/components/chat/Messages/CitationsModal.svelte');
		const modal = source('src/lib/components/common/Modal.svelte');

		expect(citations).toContain('aria-expanded={isCollapsibleOpen}');
		expect(citations).toContain('aria-controls={citationListId}');
		expect(citations).toContain('aria-haspopup="dialog"');
		expect(citations).toContain('role="region"');
		expect(citations).toContain('trigger.focus()');
		expect(citationModal).toContain('ariaLabelledby={titleId}');
		expect(citationModal).toContain('closeButton?.focus()');
		expect(modal).toContain("role={ariaLabelledby || ariaLabel ? 'dialog' : undefined}");
		expect(modal).toContain("aria-modal={ariaLabelledby || ariaLabel ? 'true' : undefined}");
	});

	it('keeps successful search pages and exposes an explicit retry for the failed page', () => {
		const sidebar = source('src/lib/components/layout/Sidebar.svelte');
		const chatItem = source('src/lib/components/layout/Sidebar/ChatItem.svelte');
		const chat = source('src/lib/components/chat/Chat.svelte');

		expect(sidebar).toContain('failedChatPage = requestedPage');
		expect(sidebar).toContain('currentChatPage.set(requestedPage)');
		expect(sidebar).toContain('await loadMoreChats(failedChatPage)');
		expect(sidebar).toContain('role="alert"');
		expect(sidebar).toContain("$i18n.t('Retry')");
		expect(sidebar).toContain('matchMessageId={search ? chat.match_message_id : null}');
		expect(chatItem).toContain('encodeURIComponent(matchMessageId)');
		expect(chatItem).toContain('{matchSnippet}');
		expect(chat).toContain("$page.url.searchParams.get('message')");
		expect(chat).toContain('selectMessageBranch(messageId)');
	});

	it('binds every active generation to its owner-scoped task, chat, and assistant message', () => {
		const chat = source('src/lib/components/chat/Chat.svelte');
		const api = source('src/lib/apis/index.ts');
		const middleware = source('backend/bcgpt/utils/middleware.py');
		const socket = source('backend/bcgpt/socket/main.py');
		const tasks = source('backend/bcgpt/tasks.py');

		expect(chat).toContain('activeGenerations');
		expect(chat).toContain('sameChatGenerationAuthority(authority');
		expect(chat).toContain('generation_id: generationAuthority.generationId');
		expect(chat).toContain("deliveryStatus: 'unknown'");
		expect(chat).toContain("await stopChatGeneration('', authority.generationId, binding)");
		expect(chat).toContain('observeDurableGeneration(authority)');
		expect(chat).toContain('generation.replay.cursor > replayCursor');
		expect(chat).toContain('message_id: authority.messageId');
		expect(chat.match(/generating=\{hasActiveGeneration\}/gu)).toHaveLength(2);
		expect(chat).not.toContain('let taskId: string | null');
		expect(api).toContain('binding?: TaskStopBinding');
		expect(api).toContain('/api/chat/generations/${encodeURIComponent(generationId)}/stop');
		expect(middleware).toContain('owner_id=metadata["user_id"]');
		expect(middleware).toContain('message_id=metadata["message_id"]');
		expect(middleware).toContain('generation_id=generation_id');
		expect(middleware).toContain('ChatGenerations.append_replay_snapshot');
		expect(socket).toContain('payload["generation_id"] = generation_id');
		expect(tasks).toContain('record.owner_id != str(owner_id)');
		expect(tasks).toContain('status="different_generation"');
	});

	it('does not request tags or durable generations before a persisted chat ID exists', () => {
		const chat = source('src/lib/components/chat/Chat.svelte');
		const chatsApi = source('src/lib/apis/chats/index.ts');
		const api = source('src/lib/apis/index.ts');

		expect(chat).toContain('const scopedChatId = chatIdProp.trim();');
		expect(chat).toContain('if (!scopedChatId) return null;');
		expect(chat).toContain('if (!scopedChatId) return false;');
		expect(chatsApi).toContain('if (!chatId) return [];');
		expect(api).toContain('if (!normalizedChatId) return { generations: [] };');
	});

	it('does not let a stale regeneration save to the collection endpoint', () => {
		const chat = source('src/lib/components/chat/Chat.svelte');
		const auth = source('src/lib/apis/auths/index.ts');

		expect(chat).toContain('Blocked regeneration without a persisted chat ID');
		expect(chat).toContain('Skipped chat save without a persisted chat ID');
		expect(auth).toContain('verifySessionAfterUnauthorizedResponse');
		expect(auth).toContain('Session validation returned 401 - terminating session');
	});
});
