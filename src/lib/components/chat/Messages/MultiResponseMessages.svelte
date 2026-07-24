<script lang="ts">
	import dayjs from 'dayjs';
	import { onMount, tick, getContext } from 'svelte';

	import ResponseMessage from './ResponseMessage.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Merge from '$lib/components/icons/Merge.svelte';

	import Markdown from './Markdown.svelte';
	import Name from './Name.svelte';
	import Skeleton from './Skeleton.svelte';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	import { mobile } from '$lib/stores';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');
	dayjs.extend(localizedFormat);

	/** Grouped message IDs indexed by model position */
	interface GroupedMessages {
		[key: string]: { messageIds: string[] };
	}

	/** Current index within each model group */
	interface GroupedIndex {
		[key: string]: number;
	}

	/** Props for the MultiResponseMessages component */
	interface Props {
		chatId: string;
		history: Record<string, unknown>;
		messageId: string;
		isLastMessage: boolean;
		readOnly?: boolean;
		updateChat: () => Promise<void>;
		editMessage: (...args: unknown[]) => void;
		saveMessage: (...args: unknown[]) => void;
		rateMessage: (...args: unknown[]) => void;
		actionMessage: (...args: unknown[]) => void;
		submitMessage: (...args: unknown[]) => void;
		deleteMessage: (...args: unknown[]) => void;
		continueResponse: (...args: unknown[]) => void;
		regenerateResponse: (...args: unknown[]) => void;
		mergeResponses: (...args: unknown[]) => void;
		addMessages: (...args: unknown[]) => void;
		triggerScroll: () => void;
	}

	let {
		chatId,
		history = $bindable(),
		messageId,
		isLastMessage,
		readOnly = false,
		updateChat,
		editMessage,
		saveMessage,
		rateMessage,
		actionMessage,
		submitMessage,
		deleteMessage,
		continueResponse,
		regenerateResponse,
		mergeResponses,
		addMessages,
		triggerScroll
	}: Props = $props();

	let parentMessage = $state<Record<string, unknown> | null>(null);
	let groupedMessageIds = $state<GroupedMessages>({});
	let groupedMessageIdsIdx = $state<GroupedIndex>({});

	// $state.snapshot unwraps the Svelte 5 deep-$state proxy into a plain deep copy.
	// structuredClone() throws DataCloneError on $state proxies (regression from 5d78a03).
	let message = $derived($state.snapshot(history.messages?.[messageId]));

	/**
	 * Navigates to a specific message within a model group,
	 * then traverses to the deepest child to update history.currentId.
	 */
	async function gotoMessage(modelIdx: string, messageIdx: number): Promise<void> {
		groupedMessageIdsIdx[modelIdx] = Math.max(
			0,
			Math.min(messageIdx, groupedMessageIds[modelIdx].messageIds.length - 1)
		);

		let targetId: string = groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]];

		let messageChildrenIds = (history.messages as Record<string, Record<string, unknown>>)[targetId]
			?.childrenIds as string[];
		while (messageChildrenIds?.length !== 0) {
			targetId = messageChildrenIds.at(-1)!;
			messageChildrenIds = (history.messages as Record<string, Record<string, unknown>>)[targetId]
				?.childrenIds as string[];
		}

		history.currentId = targetId;

		await tick();
		await updateChat();
		triggerScroll();
	}

	/** Shows the previous message in a model group */
	async function showPreviousMessage(modelIdx: string): Promise<void> {
		groupedMessageIdsIdx[modelIdx] = Math.max(0, groupedMessageIdsIdx[modelIdx] - 1);

		let targetId: string = groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]];

		let messageChildrenIds = (history.messages as Record<string, Record<string, unknown>>)[targetId]
			?.childrenIds as string[];
		while (messageChildrenIds?.length !== 0) {
			targetId = messageChildrenIds.at(-1)!;
			messageChildrenIds = (history.messages as Record<string, Record<string, unknown>>)[targetId]
				?.childrenIds as string[];
		}

		history.currentId = targetId;

		await tick();
		await updateChat();
		triggerScroll();
	}

	/** Shows the next message in a model group */
	async function showNextMessage(modelIdx: string): Promise<void> {
		groupedMessageIdsIdx[modelIdx] = Math.min(
			groupedMessageIds[modelIdx].messageIds.length - 1,
			groupedMessageIdsIdx[modelIdx] + 1
		);

		let targetId: string = groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]];

		let messageChildrenIds = (history.messages as Record<string, Record<string, unknown>>)[targetId]
			?.childrenIds as string[];
		while (messageChildrenIds?.length !== 0) {
			targetId = messageChildrenIds.at(-1)!;
			messageChildrenIds = (history.messages as Record<string, Record<string, unknown>>)[targetId]
				?.childrenIds as string[];
		}

		history.currentId = targetId;

		await tick();
		await updateChat();
		triggerScroll();
	}

	/**
	 * Traverses the message children tree to find the deepest leaf node.
	 * Used for updating history.currentId when selecting a response.
	 */
	function findDeepestChild(startId: string): string {
		let currentId = startId;
		const messages = history.messages as Record<string, Record<string, unknown>>;
		let childrenIds = messages[currentId]?.childrenIds as string[];
		while (childrenIds?.length !== 0) {
			currentId = childrenIds.at(-1)!;
			childrenIds = messages[currentId]?.childrenIds as string[];
		}
		return currentId;
	}

	/** Initialises the grouped message structure from the parent's models and children */
	async function initHandler(): Promise<void> {
		await tick();

		const messages = history.messages as Record<string, Record<string, unknown>>;
		const currentMsg = messages[messageId] as Record<string, unknown>;
		const parentId = currentMsg?.parentId as string;

		parentMessage = parentId ? (messages[parentId] as Record<string, unknown>) : null;

		const parentModels = parentMessage?.models as unknown[];
		const parentChildrenIds = parentMessage?.childrenIds as string[];

		groupedMessageIds = (parentModels ?? []).reduce(
			(acc: GroupedMessages, model: unknown, modelIdx: number) => {
				let modelMessageIds = parentChildrenIds
					.map((id) => messages[id] as Record<string, unknown>)
					.filter((m) => m?.modelIdx === modelIdx)
					.map((m) => m.id as string);

				// Legacy support for messages without modelIdx
				if (modelMessageIds.length === 0) {
					const modelMessages = parentChildrenIds
						.map((id) => messages[id] as Record<string, unknown>)
						.filter((m) => m?.model === model);

					modelMessages.forEach((m) => {
						m.modelIdx = modelIdx;
					});

					modelMessageIds = modelMessages.map((m) => m.id as string);
				}

				return {
					...acc,
					[modelIdx]: { messageIds: modelMessageIds }
				};
			},
			{}
		);

		groupedMessageIdsIdx = (parentModels ?? []).reduce(
			(acc: GroupedIndex, _model: unknown, modelIdx: number) => {
				const idx = groupedMessageIds[modelIdx].messageIds.findIndex((id) => id === messageId);
				return {
					...acc,
					[modelIdx]: idx !== -1 ? idx : groupedMessageIds[modelIdx].messageIds.length - 1
				};
			},
			{}
		);

		await tick();
	}

	/** Merges all model responses into a single combined response */
	async function mergeResponsesHandler(): Promise<void> {
		const responses = Object.keys(groupedMessageIds).map((modelIdx) => {
			const { messageIds } = groupedMessageIds[modelIdx];
			const targetId = messageIds[groupedMessageIdsIdx[modelIdx]];
			const messages = history.messages as Record<string, Record<string, unknown>>;
			return (messages[targetId] as Record<string, unknown>).content;
		});
		mergeResponses(messageId, responses, chatId);
	}

	onMount(async () => {
		await initHandler();
		await tick();

		const messageElement = document.getElementById(`message-${messageId}`);
		if (messageElement) {
			messageElement.scrollIntoView({ block: 'start' });
		}
	});
</script>

{#if parentMessage}
	<div>
		<div
			class="flex snap-x snap-mandatory overflow-x-auto scrollbar-hidden"
			id="responses-container-{chatId}-{(parentMessage as Record<string, unknown>).id}"
		>
			{#each Object.keys(groupedMessageIds) as modelIdx (modelIdx)}
				{#if groupedMessageIdsIdx[modelIdx] !== undefined && groupedMessageIds[modelIdx].messageIds.length > 0}
					{@const _messageId =
						groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]]}
					{@const selectResponse = async () => {
						if (messageId != _messageId) {
							const deepestId = findDeepestChild(_messageId);
							history.currentId = deepestId;

							await tick();
							await updateChat();
							triggerScroll();
						}
					}}

					<div
						class="snap-center w-full max-w-full m-1 border {(
							history.messages as Record<string, Record<string, unknown>>
						)[messageId]?.modelIdx == modelIdx
							? `border-gray-100 dark:border-gray-850 border-[1.5px] ${$mobile ? 'min-w-full' : 'min-w-80'}`
							: `border-gray-100 dark:border-gray-850 border-dashed ${$mobile ? 'min-w-full' : 'min-w-80'}`} transition-all p-5 rounded-2xl"
						role="button"
						tabindex="0"
						onclick={selectResponse}
						onkeydown={(e) => {
							if (e.key === 'Enter' || e.key === ' ') {
								e.preventDefault();
								selectResponse();
							}
						}}
					>
						{#key history.currentId}
							{#if message}
								<ResponseMessage
									{chatId}
									{history}
									messageId={_messageId}
									isLastMessage={true}
									siblings={groupedMessageIds[modelIdx].messageIds}
									gotoMessage={(_msg: unknown, messageIdx: number) =>
										gotoMessage(modelIdx, messageIdx)}
									showPreviousMessage={() => showPreviousMessage(modelIdx)}
									showNextMessage={() => showNextMessage(modelIdx)}
									{updateChat}
									{editMessage}
									{saveMessage}
									{rateMessage}
									{deleteMessage}
									{actionMessage}
									{submitMessage}
									{continueResponse}
									regenerateResponse={async (msg: unknown) => {
										regenerateResponse(msg);
										await tick();
										groupedMessageIdsIdx[modelIdx] =
											groupedMessageIds[modelIdx].messageIds.length - 1;
									}}
									{addMessages}
									{readOnly}
								/>
							{/if}
						{/key}
					</div>
				{/if}
			{/each}
		</div>

		{#if !readOnly}
			{#if !Object.keys(groupedMessageIds).find((modelIdx) => {
				const { messageIds } = groupedMessageIds[modelIdx];
				const targetId = messageIds[groupedMessageIdsIdx[modelIdx]];
				const messages = history.messages as Record<string, Record<string, unknown>>;
				return !(messages[targetId] as Record<string, unknown>)?.done;
			})}
				<div class="flex justify-end">
					<div class="w-full">
						{#if (history.messages as Record<string, Record<string, unknown>>)[messageId]?.merged?.status}
							{@const mergedMessage = (
								(history.messages as Record<string, Record<string, unknown>>)[messageId] as Record<
									string,
									unknown
								>
							).merged as Record<string, unknown>}

							<div class="w-full rounded-xl pl-5 pr-2 py-2">
								<Name>
									{$i18n.t('Merged Response')}

									{#if mergedMessage.timestamp}
										<span
											class="self-center invisible group-hover:visible text-gray-400 text-xs font-medium uppercase ml-0.5 -mt-0.5"
										>
											{dayjs((mergedMessage.timestamp as number) * 1000).format('LT')}
										</span>
									{/if}
								</Name>

								<div class="mt-1 markdown-prose w-full min-w-full">
									{#if ((mergedMessage?.content as string) ?? '') === ''}
										<Skeleton />
									{:else}
										<Markdown id="merged" content={(mergedMessage.content ?? '') as string} />
									{/if}
								</div>
							</div>
						{/if}
					</div>

					{#if isLastMessage}
						<div class="shrink-0 text-gray-600 dark:text-gray-500 mt-1">
							<Tooltip content={$i18n.t('Merge Responses')} placement="bottom">
								<button
									type="button"
									id="merge-response-button"
									class="visible p-1 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition regenerate-response-button"
									onclick={mergeResponsesHandler}
								>
									<Merge className="size-5" />
								</button>
							</Tooltip>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
{/if}
