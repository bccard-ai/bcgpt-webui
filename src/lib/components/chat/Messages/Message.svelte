<script lang="ts">
	import { settings } from '$lib/stores';

	import MultiResponseMessages from './MultiResponseMessages.svelte';
	import ResponseMessage from './ResponseMessage.svelte';
	import UserMessage from './UserMessage.svelte';

	/** A single message in the chat history */
	interface HistoryMessage {
		id: string;
		role: string;
		parentId: string | null;
		childrenIds: string[];
		models?: unknown[];
		[key: string]: unknown;
	}

	/** The chat history tree structure */
	interface HistoryType {
		messages: Record<string, HistoryMessage>;
		currentId: string | null;
		[key: string]: unknown;
	}

	/** Props for the Message component - routes to the correct message type renderer */
	interface Props {
		chatId: string;
		idx?: number;
		history: HistoryType;
		messageId: string;
		user: Record<string, unknown>;
		gotoMessage: (...args: unknown[]) => void;
		showPreviousMessage: (...args: unknown[]) => void;
		showNextMessage: (...args: unknown[]) => void;
		updateChat: (...args: unknown[]) => void;
		editMessage: (...args: unknown[]) => void;
		saveMessage: (...args: unknown[]) => void;
		deleteMessage: (...args: unknown[]) => void;
		rateMessage: (...args: unknown[]) => void;
		actionMessage: (...args: unknown[]) => void;
		submitMessage: (...args: unknown[]) => void;
		regenerateResponse: (...args: unknown[]) => void;
		continueResponse: (...args: unknown[]) => void;
		mergeResponses: (...args: unknown[]) => void;
		addMessages: (...args: unknown[]) => void;
		triggerScroll: (...args: unknown[]) => void;
		readOnly?: boolean;
	}

	let {
		chatId,
		idx = 0,
		history = $bindable(),
		messageId,
		user,
		gotoMessage,
		showPreviousMessage,
		showNextMessage,
		updateChat,
		editMessage,
		saveMessage,
		deleteMessage,
		rateMessage,
		actionMessage,
		submitMessage,
		regenerateResponse,
		continueResponse,
		mergeResponses,
		addMessages,
		triggerScroll,
		readOnly = false
	}: Props = $props();

	/** Computes sibling message IDs for navigation */
	function computeSiblings(): string[] {
		const parentMessage = history.messages[messageId];
		const parentId = parentMessage?.parentId;

		if (parentId != null) {
			return history.messages[parentId]?.childrenIds ?? [];
		}
		return (
			Object.values(history.messages)
				.filter((message) => message.parentId === null)
				.map((message) => message.id) ?? []
		);
	}

	/** Checks if the parent message has multiple models for multi-response display */
	function isMultiModel(): boolean {
		const parentMessage = history.messages[messageId];
		const parentId = parentMessage?.parentId;
		const parent = history.messages[parentId ?? ''];
		return (parent?.models?.length ?? 1) > 1;
	}
</script>

<div
	class="flex flex-col justify-between px-5 mb-3 w-full {($settings?.widescreenMode ?? null)
		? 'max-w-full'
		: 'max-w-5xl'} mx-auto rounded-lg group"
>
	{#if history.messages[messageId]}
		{#if history.messages[messageId].role === 'user'}
			<UserMessage
				{user}
				{history}
				{messageId}
				isFirstMessage={idx === 0}
				siblings={computeSiblings()}
				{gotoMessage}
				{showPreviousMessage}
				{showNextMessage}
				{editMessage}
				{deleteMessage}
				{readOnly}
			/>
		{:else if !isMultiModel()}
			<ResponseMessage
				{chatId}
				bind:history
				{messageId}
				isLastMessage={messageId === history.currentId}
				siblings={history.messages[history.messages[messageId].parentId ?? '']?.childrenIds ?? []}
				{gotoMessage}
				{showPreviousMessage}
				{showNextMessage}
				{updateChat}
				{editMessage}
				{saveMessage}
				{rateMessage}
				{actionMessage}
				{submitMessage}
				{deleteMessage}
				{continueResponse}
				{regenerateResponse}
				{addMessages}
				{readOnly}
			/>
		{:else}
			<MultiResponseMessages
				bind:history
				{chatId}
				{messageId}
				isLastMessage={messageId === history?.currentId}
				{updateChat}
				{editMessage}
				{saveMessage}
				{rateMessage}
				{actionMessage}
				{submitMessage}
				{deleteMessage}
				{continueResponse}
				{regenerateResponse}
				{mergeResponses}
				{triggerScroll}
				{addMessages}
				{readOnly}
			/>
		{/if}
	{/if}
</div>
