<script lang="ts">
	import { get } from 'svelte/store';
	import { logger } from '$lib/utils/logger';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';

	import { onMount, tick, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	const i18n = getContext<Writable<i18nType>>('i18n');

	import { createNewFeedback, updateFeedbackById } from '$lib/apis/evaluations';
	import { getChatById } from '$lib/apis/chats';
	import { generateTags } from '$lib/apis';

	import { config, models, settings, temporaryChatEnabled, user } from '$lib/stores';
	import { getModelIconUrl } from '$lib/utils/providers';
	import { imageGenerations } from '$lib/apis/images';
	import {
		copyToClipboard as _copyToClipboard,
		sanitizeResponseContent,
		createMessagesList,
		formatDate
	} from '$lib/utils';

	import { createMessageTTS } from './message-tts.svelte';

	import Name from './Name.svelte';
	import ProfileImage from './ProfileImage.svelte';
	import Skeleton from './Skeleton.svelte';
	import Image from '$lib/components/common/Image.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import RateComment from './RateComment.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import WebSearchResults from './ResponseMessage/WebSearchResults.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';

	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	import Error from './Error.svelte';
	import Citations from './Citations.svelte';
	import ContentRenderer from './ContentRenderer.svelte';

	// ---------------------------------------------------------------------------
	// Type definitions
	// ---------------------------------------------------------------------------

	/** Metadata attached to a citation document */
	interface MessageSourceMetadata {
		source?: string;
		name?: string;
		[key: string]: unknown;
	}

	/** A retrieval source with documents and distance scores */
	interface MessageSource {
		document: string[];
		metadata?: Array<MessageSourceMetadata | undefined>;
		distances?: number[];
		source?: { id?: string; name?: string; url?: string; [key: string]: unknown };
		[key: string]: unknown;
	}

	/** A status entry for background actions (web search, knowledge search, etc.) */
	interface StatusEntry {
		done: boolean;
		action: string;
		description: string;
		urls?: string[];
		query?: string;
		hidden?: boolean;
	}

	/** Token usage information from the model */
	interface MessageInfo {
		openai?: boolean;
		prompt_tokens?: number;
		completion_tokens?: number;
		total_tokens?: number;
		eval_count?: number;
		eval_duration?: number;
		prompt_eval_count?: number;
		prompt_eval_duration?: number;
		total_duration?: number;
		load_duration?: number;
		usage?: unknown;
	}

	/** Full message object from the chat history */
	interface MessageType {
		id: string;
		model: string;
		content: string;
		files?: { type: string; url: string }[];
		timestamp: number;
		role: string;
		statusHistory?: StatusEntry[];
		status?: StatusEntry;
		done: boolean;
		error?: boolean | { content: string };
		sources?: MessageSource[];
		info?: MessageInfo;
		annotation?: { type: string; rating: number; [key: string]: unknown };
		usage?: unknown;
		citations?: MessageSource[];
		parentId?: string | null;
		feedbackId?: string | null;
		selectedModelId?: string;
		arena?: boolean;
	}

	// ---------------------------------------------------------------------------
	// Props
	// ---------------------------------------------------------------------------

	/** Props for the ResponseMessage component - renders an LLM response with rich content */
	interface Props {
		chatId?: string;
		history: Record<string, unknown>;
		messageId: string;
		siblings: unknown[];
		gotoMessage?: (modelIdx: number, messageIdx: number) => void;
		showPreviousMessage: () => void;
		showNextMessage: () => void;
		updateChat: () => void;
		editMessage: (messageId: string, content: string, submit?: boolean) => void;
		saveMessage: (messageId: string, message: Record<string, unknown>) => void;
		actionMessage: (actionId: string, message: Record<string, unknown>) => void;
		deleteMessage: (messageId: string) => void;
		submitMessage: (parentId: string, content: string) => void;
		continueResponse: () => void;
		regenerateResponse: () => void;
		addMessages: (data: Record<string, unknown>) => void;
		isLastMessage?: boolean;
		readOnly?: boolean;
		onAction?: (payload: { id: string; event: unknown }) => void;
	}

	let {
		chatId = '',
		history = $bindable(),
		messageId,
		siblings,
		gotoMessage = () => {},
		showPreviousMessage,
		showNextMessage,
		updateChat,
		editMessage,
		saveMessage,
		actionMessage,
		deleteMessage,
		submitMessage: _submitMessage,
		continueResponse,
		regenerateResponse,
		addMessages,
		isLastMessage = true,
		readOnly = false,
		onAction
	}: Props = $props();

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------

	// $state.snapshot unwraps the Svelte 5 deep-$state proxy into a plain deep copy.
	// structuredClone() throws DataCloneError on $state proxies (regression from 5d78a03).
	let message: MessageType = $derived($state.snapshot(history.messages?.[messageId]));

	let buttonsContainerElement: HTMLDivElement = $state();
	let showDeleteConfirm = $state(false);

	let model = $derived(get(models).find((m) => m.id === message.model) ?? null);

	let edit = $state(false);
	let editedContent = $state('');
	let editTextAreaElement: HTMLTextAreaElement = $state();

	let messageIndexEdit = $state(false);

	const tts = createMessageTTS({
		getMessageContent: () => message?.content ?? '',
		toastInfo: (msg) => toast.info($i18n.t(msg)),
		toastError: (msg) => toast.error(msg)
	});

	let generatingImage = $state(false);

	let showRateComment = $state(false);

	let feedbackLoading = $state(false);

	// ---------------------------------------------------------------------------
	// Clipboard
	// ---------------------------------------------------------------------------

	/** Copies text to the system clipboard and shows a success toast */
	async function copyToClipboard(text: string): Promise<void> {
		const res = await _copyToClipboard(text);
		if (res) {
			toast.success($i18n.t('Copying to clipboard was successful!'));
		}
	}

	// ---------------------------------------------------------------------------
	// Edit message
	// ---------------------------------------------------------------------------

	/** Enters edit mode for the response message */
	async function editMessageHandler(): Promise<void> {
		edit = true;
		editedContent = message.content;

		await tick();

		editTextAreaElement.style.height = '';
		editTextAreaElement.style.height = `${editTextAreaElement.scrollHeight}px`;
	}

	/** Confirms the edit and saves the changes */
	async function editMessageConfirmHandler(): Promise<void> {
		editMessage(message.id, editedContent ? editedContent : '', false);
		edit = false;
		editedContent = '';
		await tick();
	}

	/** Saves the edited content as a new copy */
	async function saveAsCopyHandler(): Promise<void> {
		editMessage(message.id, editedContent ? editedContent : '');
		edit = false;
		editedContent = '';
		await tick();
	}

	/** Cancels the edit and restores original content */
	async function cancelEditMessage(): Promise<void> {
		edit = false;
		editedContent = '';
		await tick();
	}

	/** Handles keyboard shortcuts in the edit textarea */
	function handleEditKeydown(e: KeyboardEvent): void {
		if (e.key === 'Escape') {
			document.getElementById('close-edit-message-button')?.click();
		}

		const isCmdOrCtrlPressed = e.metaKey || e.ctrlKey;
		const isEnterPressed = e.key === 'Enter';

		if (isCmdOrCtrlPressed && isEnterPressed) {
			document.getElementById('confirm-edit-message-button')?.click();
		}
	}

	/** Auto-resizes the edit textarea to fit content */
	function handleEditInput(e: Event): void {
		if (e.target) {
			(e.target as HTMLTextAreaElement).style.height = '';
		}
		if (e.target) {
			(e.target as HTMLTextAreaElement).style.height =
				`${(e.target as HTMLTextAreaElement).scrollHeight}px`;
		}
	}

	// ---------------------------------------------------------------------------
	// Image generation
	// ---------------------------------------------------------------------------

	/** Generates an image from the message content */
	async function generateImage(msg: MessageType): Promise<void> {
		generatingImage = true;
		const res = await imageGenerations('', msg.content).catch((error: unknown) => {
			if (error?.name === 'AbortError') {
				toast.error('Image generation timed out. Please try again.');
			} else {
				toast.error(
					(error as Record<string, unknown>)?.detail ??
						(error as Record<string, unknown>)?.message ??
						`${error}`
				);
			}
		});

		if (res) {
			const files = res.map((image: { url: string }) => ({
				type: 'image',
				url: `${image.url}`
			}));

			saveMessage(msg.id, {
				...msg,
				files: files
			});
		}

		generatingImage = false;
	}

	// ---------------------------------------------------------------------------
	// Feedback / rating
	// ---------------------------------------------------------------------------

	/**
	 * Handles message rating feedback.
	 * Creates or updates feedback records, optionally generates tags,
	 * and shows the detailed rating comment form.
	 */
	async function feedbackHandler(
		rating: number | null = null,
		details: Record<string, unknown> | null = null
	): Promise<void> {
		feedbackLoading = true;

		const updatedMessage = {
			...message,
			annotation: {
				...(message?.annotation ?? {}),
				...(rating !== null ? { rating: rating } : {}),
				...(details ? details : {})
			}
		};

		const chat = await getChatById('', chatId).catch((error: unknown) => {
			toast.error(`${error}`);
		});
		if (!chat) return;

		const messages = createMessagesList(history, message.id);

		const feedbackItem = buildFeedbackItem(updatedMessage, messages, chat);

		if (message?.feedbackId) {
			await updateFeedbackById('', message.feedbackId, feedbackItem).catch((error: unknown) => {
				toast.error(`${error}`);
			});
		} else {
			const feedback = await createNewFeedback('', feedbackItem).catch((error: unknown) => {
				toast.error(`${error}`);
			});

			if (feedback) {
				updatedMessage.feedbackId = feedback.id;
			}
		}

		saveMessage(message.id, updatedMessage);
		await tick();

		if (!details) {
			showRateComment = true;

			if (!(updatedMessage.annotation as Record<string, unknown>)?.tags) {
				const tags = await generateTags('', message.model, messages, chatId).catch(
					(error: unknown) => {
						logger.error('chat', 'ResponseMessage error', undefined, error);
						return [];
					}
				);

				if (tags) {
					(updatedMessage.annotation as Record<string, unknown>).tags = tags;
					(feedbackItem.data as Record<string, unknown>).tags = tags;

					saveMessage(message.id, updatedMessage);
					await updateFeedbackById('', updatedMessage.feedbackId, feedbackItem).catch(
						(error: unknown) => {
							toast.error(`${error}`);
						}
					);
				}
			}
		}

		feedbackLoading = false;
	}

	/** Builds the feedback payload for the API */
	function buildFeedbackItem(
		updatedMessage: Record<string, unknown>,
		messages: unknown[],
		chat: unknown
	): Record<string, unknown> {
		const historyMessages = history.messages as Record<string, Record<string, unknown>>;
		const parentMsg = historyMessages[message.parentId ?? ''];

		const siblingModelIds =
			(parentMsg?.childrenIds as string[])?.length > 1
				? (parentMsg.childrenIds as string[])
						.filter((id: string) => id !== message.id)
						.map((id: string) => historyMessages[id]?.selectedModelId ?? historyMessages[id].model)
				: [];

		const baseModels = [
			(updatedMessage as Record<string, unknown>).selectedModelId ?? message.model,
			...siblingModelIds
		].reduce((acc: Record<string, unknown>, modelId: string) => {
			const found = get(models).find((m) => m.id === modelId);
			if (found) {
				acc[found.id] = found?.info?.base_model_id ?? null;
			}
			return acc;
		}, {});

		return {
			type: 'rating',
			data: {
				...(updatedMessage.annotation ? updatedMessage.annotation : {}),
				model_id: message?.selectedModelId ?? message.model,
				...(siblingModelIds.length > 0 ? { sibling_model_ids: siblingModelIds } : {})
			},
			meta: {
				arena: message ? message.arena : false,
				model_id: message.model,
				message_id: message.id,
				message_index: messages.length,
				chat_id: chatId,
				base_models: baseModels
			},
			snapshot: {
				chat: chat
			}
		};
	}

	// ---------------------------------------------------------------------------
	// Delete
	// ---------------------------------------------------------------------------

	/** Deletes the current message */
	function deleteMessageHandler(): void {
		deleteMessage(message.id);
	}

	// ---------------------------------------------------------------------------
	// Status helpers
	// ---------------------------------------------------------------------------

	/** Resolves the latest status entry from the message */
	function getLatestStatus(): StatusEntry | undefined {
		const statusEntries = message?.statusHistory ?? [...(message?.status ? [message.status] : [])];
		return statusEntries.at(-1);
	}

	/** Formats a status description with i18n support */
	function formatStatusDescription(status: StatusEntry): string {
		if (status?.description.includes('{{count}}')) {
			return $i18n.t(status.description, { count: status.urls?.length });
		}
		if (status?.description === 'No search query generated') {
			return $i18n.t('No search query generated');
		}
		if (status?.description === 'Generating search query') {
			return $i18n.t('Generating search query');
		}
		if (status?.description.includes('{{searchQuery}}')) {
			return $i18n.t(status.description, { searchQuery: status.query });
		}
		return status?.description;
	}

	/** Computes the visibility class for action buttons */
	function buttonVisibility(): string {
		return isLastMessage ? 'visible' : 'invisible group-hover:visible';
	}

	// ---------------------------------------------------------------------------
	// Lifecycle
	// ---------------------------------------------------------------------------

	onMount(async () => {
		await tick();
		if (buttonsContainerElement) {
			const wheelHandler = (event: WheelEvent) => {
				event.preventDefault();
				if (event.deltaY !== 0) {
					buttonsContainerElement.scrollLeft += event.deltaY;
				}
			};
			buttonsContainerElement.addEventListener('wheel', wheelHandler);

			return () => {
				buttonsContainerElement.removeEventListener('wheel', wheelHandler);
			};
		}
	});
</script>

<DeleteConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete message?')}
	onconfirm={deleteMessageHandler}
/>

{#key message.id}
	<div
		class="flex w-full message-{message.id}"
		id="message-{message.id}"
		dir={$settings.chatDirection}
		data-ai-generated="true"
	>
		<div class={`shrink-0 ${($settings?.chatDirection ?? 'LTR') === 'LTR' ? 'mr-3' : 'ml-3'}`}>
			<ProfileImage
				src={getModelIconUrl({
					id: model?.id ?? '',
					owned_by: model?.owned_by,
					direct: model?.direct,
					profileImageUrl: (model?.info as Record<string, unknown>)?.meta
						? ((model?.info as Record<string, unknown>).meta as Record<string, unknown>)
								?.profile_image_url
						: undefined
				})}
				className="size-8"
			/>
		</div>

		<div class="flex-auto w-0 pl-1">
			<Name>
				<Tooltip content={(model?.name as string) ?? message.model} placement="top-start">
					<span class="line-clamp-1 text-black dark:text-white">
						{(model?.name as string) ?? message.model}
					</span>
				</Tooltip>

				{#if $settings?.ai_transparency_enabled !== false}
					<span
						class="ml-1.5 px-1.5 py-0.5 text-[10px] font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded"
					>
						{$settings?.ai_response_label || $i18n.t('AI-generated response')}
					</span>
				{/if}

				{#if message.timestamp}
					<div
						class="self-center text-xs invisible group-hover:visible text-gray-400 font-medium first-letter:capitalize ml-0.5 translate-y-[1px]"
					>
						<Tooltip content={dayjs(message.timestamp * 1000).format('LLLL')}>
							<span class="line-clamp-1">{formatDate(message.timestamp * 1000)}</span>
						</Tooltip>
					</div>
				{/if}
			</Name>

			<div>
				{#if message?.files && message.files?.filter((f) => f.type === 'image').length > 0}
					<div class="my-2.5 w-full flex overflow-x-auto gap-2 flex-wrap">
						{#each message.files as file (file.url)}
							<div>
								{#if file.type === 'image'}
									<Image src={file.url} alt={message.content} />
								{/if}
							</div>
						{/each}
					</div>
				{/if}

				<div class="chat-{message.role} w-full min-w-full markdown-prose">
					<div>
						{#if true}
							{@const status = getLatestStatus()}
							{#if status && !status?.hidden}
								<div class="status-description flex items-center gap-2 py-0.5">
									{#if status?.done === false}
										<div>
											<Spinner className="size-4" />
										</div>
									{/if}

									{#if status?.action === 'web_search' && status?.urls}
										<WebSearchResults {status}>
											<div class="flex flex-col justify-center -space-y-0.5">
												<div
													class="{status?.done === false
														? 'shimmer'
														: ''} text-base line-clamp-1 text-wrap"
												>
													{formatStatusDescription(status)}
												</div>
											</div>
										</WebSearchResults>
									{:else if status?.action === 'knowledge_search'}
										<div class="flex flex-col justify-center -space-y-0.5">
											<div
												class="{status?.done === false
													? 'shimmer'
													: ''} text-gray-500 dark:text-gray-500 text-base line-clamp-1 text-wrap"
											>
												{$i18n.t(`Searching Knowledge for "{{searchQuery}}"`, {
													searchQuery: status.query
												})}
											</div>
										</div>
									{:else if status?.action === 'context_compression'}
										<div
											class="flex items-center gap-1 text-purple-500 dark:text-purple-400 {status?.done ===
											false
												? 'shimmer'
												: ''}"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 20 20"
												fill="currentColor"
												class="size-4 shrink-0"
											>
												<path
													fill-rule="evenodd"
													d="M15.988 3.012A2.25 2.25 0 0 1 18 5.25v6.5A2.25 2.25 0 0 1 15.75 14H13.5V7.637L11.356 9.78a.75.75 0 0 1-.53.22H4.5v5.25a.75.75 0 0 1-.75.75h-.01a.75.75 0 0 1-.75-.75V4.5A2.25 2.25 0 0 1 5.25 2.25h6.5a2.25 2.25 0 0 1 2.238 2.012Z"
													clip-rule="evenodd"
												/>
											</svg>
											<span>{$i18n.t('Compressing conversation history...')}</span>
										</div>
									{:else if status?.action === 'smart_query'}
										<div
											class="flex items-center gap-1 text-green-500 dark:text-green-400 {status?.done ===
											false
												? 'shimmer'
												: ''}"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 20 20"
												fill="currentColor"
												class="size-4 shrink-0"
											>
												<path
													fill-rule="evenodd"
													d="M14.615 1.595a.75.75 0 0 1 .359.852L12.982 9.75h7.268a.75.75 0 0 1 .548 1.262l-10.5 11.25a.75.75 0 0 1-1.272-.71l1.992-7.302H3.75a.75.75 0 0 1-.548-1.262l10.5-11.25a.75.75 0 0 1 .913-.143Z"
													clip-rule="evenodd"
												/>
											</svg>
											<span>{$i18n.t('Enhancing query with conversation context...')}</span>
										</div>
									{:else}
										<div class="flex flex-col justify-center -space-y-0.5">
											<div
												class="{status?.done === false
													? 'shimmer'
													: ''} text-gray-500 dark:text-gray-500 text-base line-clamp-1 text-wrap"
											>
												{formatStatusDescription(status)}
											</div>
										</div>
									{/if}
								</div>
							{/if}
						{/if}

						{#if edit === true}
							<div class="w-full bg-gray-50 dark:bg-gray-800 rounded-3xl px-5 py-3 my-2">
								<textarea
									id="message-edit-{message.id}"
									bind:this={editTextAreaElement}
									class="bg-transparent outline-hidden w-full resize-none"
									bind:value={editedContent}
									aria-label="Edit message"
									oninput={handleEditInput}
									onkeydown={handleEditKeydown}
								></textarea>

								<div class="mt-2 mb-1 flex justify-between text-sm font-medium">
									<div>
										<button
											id="save-new-message-button"
											class="px-4 py-2 bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 border dark:border-gray-700 text-gray-700 dark:text-gray-200 transition rounded-3xl"
											onclick={saveAsCopyHandler}
										>
											{$i18n.t('Save As Copy')}
										</button>
									</div>

									<div class="flex space-x-1.5">
										<button
											id="close-edit-message-button"
											class="px-4 py-2 bg-white dark:bg-gray-900 hover:bg-gray-100 text-gray-800 dark:text-gray-100 transition rounded-3xl"
											onclick={cancelEditMessage}
										>
											{$i18n.t('Cancel')}
										</button>

										<button
											id="confirm-edit-message-button"
											class="px-4 py-2 bg-gray-900 dark:bg-white hover:bg-gray-850 text-gray-100 dark:text-gray-800 transition rounded-3xl"
											onclick={editMessageConfirmHandler}
										>
											{$i18n.t('Save')}
										</button>
									</div>
								</div>
							</div>
						{:else}
							<div class="w-full flex flex-col relative" id="response-content-container">
								{#if message.content === '' && !message.error}
									<Skeleton />
								{:else if message.content && message.error !== true}
									<ContentRenderer
										id={message.id}
										{history}
										content={message.content}
										sources={message.sources}
										floatingButtons={message?.done && !readOnly}
										save={!readOnly}
										{model}
										onTaskClick={async (_e: CustomEvent) => {}}
										onSourceClick={async (_id: string, idx: number) => {
											let sourceButton = document.getElementById(`source-${message.id}-${idx}`);
											const sourcesCollapsible = document.getElementById(
												`collapsible-${message.id}`
											);

											if (sourceButton) {
												sourceButton.click();
											} else if (sourcesCollapsible) {
												sourcesCollapsible
													.querySelector('div:first-child')
													.dispatchEvent(new PointerEvent('pointerup', {}));

												await new Promise((resolve) => {
													requestAnimationFrame(() => {
														requestAnimationFrame(resolve);
													});
												});

												sourceButton = document.getElementById(`source-${message.id}-${idx}`);
												if (sourceButton) sourceButton.click();
											}
										}}
										onAddMessages={({ modelId, parentId, messages }: Record<string, unknown>) => {
											addMessages({ modelId, parentId, messages });
										}}
										onUpdate={(e: CustomEvent) => {
											const { raw, oldContent, newContent } = e.detail as Record<string, string>;
											const msgContent = (history.messages[message.id] as Record<string, unknown>)
												.content as string;
											(history.messages[message.id] as Record<string, unknown>).content =
												msgContent.replace(raw, raw.replace(oldContent, newContent));
											updateChat();
										}}
									/>
								{/if}

								{#if message?.error}
									<Error
										content={typeof message.error === 'object'
											? message.error.content
											: message.content}
									/>
								{/if}

								{#if (message?.sources || message?.citations) && (model?.info as Record<string, unknown>)?.meta ? ((((model?.info as Record<string, unknown>).meta as Record<string, unknown>)?.capabilities as Record<string, unknown>)?.citations ?? true) : true}
									<Citations id={message?.id} sources={message?.sources ?? message?.citations} />
								{/if}
							</div>
						{/if}
					</div>
				</div>

				{#if !edit}
					<div
						bind:this={buttonsContainerElement}
						class="flex justify-start overflow-x-auto buttons text-gray-600 dark:text-gray-500 mt-0.5"
					>
						{#if message.done || siblings.length > 1}
							{#if siblings.length > 1}
								<div class="flex self-center min-w-fit" dir="ltr">
									<button
										class="self-center p-1 hover:bg-black/5 dark:hover:bg-white/5 dark:hover:text-white hover:text-black rounded-md transition"
										aria-label={$i18n.t('Previous')}
										onclick={() => {
											showPreviousMessage(message);
										}}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke="currentColor"
											stroke-width="2.5"
											class="size-3.5"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M15.75 19.5 8.25 12l7.5-7.5"
											/>
										</svg>
									</button>

									{#if messageIndexEdit}
										<div
											class="text-sm flex justify-center font-semibold self-center dark:text-gray-100 min-w-fit"
										>
											<input
												id="message-index-input-{message.id}"
												type="number"
												value={(siblings as string[]).indexOf(message.id) + 1}
												min="1"
												max={siblings.length}
												onfocus={(e: FocusEvent) => {
													(e.target as HTMLInputElement)?.select();
												}}
												onblur={(e: FocusEvent) => {
													gotoMessage(message, (e.target as HTMLInputElement).value - 1);
													messageIndexEdit = false;
												}}
												onkeydown={(e: KeyboardEvent) => {
													if (e.key === 'Enter') {
														gotoMessage(message, (e.target as HTMLInputElement).value - 1);
														messageIndexEdit = false;
													}
												}}
												class="bg-transparent font-semibold self-center dark:text-gray-100 min-w-fit outline-hidden"
											/>/{siblings.length}
										</div>
									{:else}
										<!-- svelte-ignore a11y_no_static_element_interactions -->
										<div
											class="text-sm tracking-widest font-semibold self-center dark:text-gray-100 min-w-fit"
											ondblclick={async () => {
												messageIndexEdit = true;

												await tick();
												const input = document.getElementById(`message-index-input-${message.id}`);
												if (input) {
													input.focus();
													input.select();
												}
											}}
										>
											{(siblings as string[]).indexOf(message.id) + 1}/{siblings.length}
										</div>
									{/if}

									<button
										class="self-center p-1 hover:bg-black/5 dark:hover:bg-white/5 dark:hover:text-white hover:text-black rounded-md transition"
										aria-label={$i18n.t('Next')}
										onclick={() => {
											showNextMessage(message);
										}}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke="currentColor"
											stroke-width="2.5"
											class="size-3.5"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="m8.25 4.5 7.5 7.5-7.5 7.5"
											/>
										</svg>
									</button>
								</div>
							{/if}

							{#if message.done}
								{#if !readOnly}
									{#if $user.role === 'user' ? ($user?.permissions?.chat?.edit ?? true) : true}
										<Tooltip content={$i18n.t('Edit')} placement="bottom">
											<button
												class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition"
												aria-label={$i18n.t('Edit')}
												onclick={editMessageHandler}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="2.3"
													stroke="currentColor"
													class="w-4 h-4"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125"
													/>
												</svg>
											</button>
										</Tooltip>
									{/if}
								{/if}

								<Tooltip content={$i18n.t('Copy')} placement="bottom">
									<button
										class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition copy-response-button"
										aria-label={$i18n.t('Copy')}
										onclick={() => {
											copyToClipboard(message.content);
										}}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke-width="2.3"
											stroke="currentColor"
											class="w-4 h-4"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"
											/>
										</svg>
									</button>
								</Tooltip>

								<Tooltip content={$i18n.t('Read Aloud')} placement="bottom">
									<button
										id="speak-button-{message.id}"
										class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition"
										aria-label={$i18n.t('Read Aloud')}
										onclick={() => {
											if (!tts.loadingSpeech) {
												tts.toggleSpeakMessage();
											}
										}}
									>
										{#if tts.loadingSpeech}
											<svg
												class="w-4 h-4"
												fill="currentColor"
												viewBox="0 0 24 24"
												xmlns="http://www.w3.org/2000/svg"
											>
												<style>
													.spinner_S1WN {
														animation: spinner_MGfb 0.8s linear infinite;
														animation-delay: -0.8s;
													}
													.spinner_Km9P {
														animation-delay: -0.65s;
													}
													.spinner_JApP {
														animation-delay: -0.5s;
													}
													@keyframes spinner_MGfb {
														93.75%,
														100% {
															opacity: 0.2;
														}
													}
												</style>
												<circle class="spinner_S1WN" cx="4" cy="12" r="3" />
												<circle class="spinner_S1WN spinner_Km9P" cx="12" cy="12" r="3" />
												<circle class="spinner_S1WN spinner_JApP" cx="20" cy="12" r="3" />
											</svg>
										{:else if tts.speaking}
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="2.3"
												stroke="currentColor"
												class="w-4 h-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M17.25 9.75 19.5 12m0 0 2.25 2.25M19.5 12l2.25-2.25M19.5 12l-2.25 2.25m-10.5-6 4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z"
												/>
											</svg>
										{:else}
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="2.3"
												stroke="currentColor"
												class="w-4 h-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"
												/>
											</svg>
										{/if}
									</button>
								</Tooltip>

								{#if $config?.features.enable_image_generation && ($user.role === 'admin' || $user?.permissions?.features?.image_generation) && !readOnly}
									<Tooltip content={$i18n.t('Generate Image')} placement="bottom">
										<button
											class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition"
											onclick={() => {
												if (!generatingImage) {
													generateImage(message);
												}
											}}
										>
											{#if generatingImage}
												<svg
													class="w-4 h-4"
													fill="currentColor"
													viewBox="0 0 24 24"
													xmlns="http://www.w3.org/2000/svg"
												>
													<style>
														.spinner_S1WN {
															animation: spinner_MGfb 0.8s linear infinite;
															animation-delay: -0.8s;
														}
														.spinner_Km9P {
															animation-delay: -0.65s;
														}
														.spinner_JApP {
															animation-delay: -0.5s;
														}
														@keyframes spinner_MGfb {
															93.75%,
															100% {
																opacity: 0.2;
															}
														}
													</style>
													<circle class="spinner_S1WN" cx="4" cy="12" r="3" />
													<circle class="spinner_S1WN spinner_Km9P" cx="12" cy="12" r="3" />
													<circle class="spinner_S1WN spinner_JApP" cx="20" cy="12" r="3" />
												</svg>
											{:else}
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="2.3"
													stroke="currentColor"
													class="w-4 h-4"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z"
													/>
												</svg>
											{/if}
										</button>
									</Tooltip>
								{/if}

								{#if message.usage}
									<Tooltip
										content={message.usage
											? `<pre>${sanitizeResponseContent(
													JSON.stringify(message.usage, null, 2)
														.replace(/"([^(")"]+)":/g, '$1:')
														.slice(1, -1)
														.split('\n')
														.map((line) => line.slice(2))
														.map((line) => (line.endsWith(',') ? line.slice(0, -1) : line))
														.join('\n')
												)}</pre>`
											: ''}
										placement="bottom"
									>
										<button
											class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition whitespace-pre-wrap"
											aria-label={$i18n.t('Details')}
											onclick={() => {}}
											id="info-{message.id}"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="2.3"
												stroke="currentColor"
												class="w-4 h-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
												/>
											</svg>
										</button>
									</Tooltip>
								{/if}

								{#if !readOnly}
									{#if !$temporaryChatEnabled && ($config?.features.enable_message_rating ?? true)}
										<Tooltip content={$i18n.t('Good Response')} placement="bottom">
											<button
												class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg {(
													message?.annotation?.rating ?? ''
												).toString() === '1'
													? 'bg-gray-100 dark:bg-gray-800'
													: ''} dark:hover:text-white hover:text-black transition disabled:cursor-progress disabled:hover:bg-transparent"
												disabled={feedbackLoading}
												aria-label={$i18n.t('Good Response')}
												onclick={async () => {
													await feedbackHandler(1);
													window.setTimeout(() => {
														document
															.getElementById(`message-feedback-${message.id}`)
															?.scrollIntoView();
													}, 0);
												}}
											>
												<svg
													stroke="currentColor"
													fill="none"
													stroke-width="2.3"
													viewBox="0 0 24 24"
													stroke-linecap="round"
													stroke-linejoin="round"
													class="w-4 h-4"
													xmlns="http://www.w3.org/2000/svg"
												>
													<path
														d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"
													/>
												</svg>
											</button>
										</Tooltip>

										<Tooltip content={$i18n.t('Bad Response')} placement="bottom">
											<button
												class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg {(
													message?.annotation?.rating ?? ''
												).toString() === '-1'
													? 'bg-gray-100 dark:bg-gray-800'
													: ''} dark:hover:text-white hover:text-black transition disabled:cursor-progress disabled:hover:bg-transparent"
												disabled={feedbackLoading}
												aria-label={$i18n.t('Bad Response')}
												onclick={async () => {
													await feedbackHandler(-1);
													window.setTimeout(() => {
														document
															.getElementById(`message-feedback-${message.id}`)
															?.scrollIntoView();
													}, 0);
												}}
											>
												<svg
													stroke="currentColor"
													fill="none"
													stroke-width="2.3"
													viewBox="0 0 24 24"
													stroke-linecap="round"
													stroke-linejoin="round"
													class="w-4 h-4"
													xmlns="http://www.w3.org/2000/svg"
												>
													<path
														d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"
													/>
												</svg>
											</button>
										</Tooltip>
									{/if}

									{#if isLastMessage}
										<Tooltip content={$i18n.t('Continue Response')} placement="bottom">
											<button
												type="button"
												id="continue-response-button"
												class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition regenerate-response-button"
												aria-label={$i18n.t('Continue Response')}
												onclick={continueResponse}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="2.3"
													stroke="currentColor"
													class="w-4 h-4"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
													/>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="M15.91 11.672a.375.375 0 0 1 0 .656l-5.603 3.113a.375.375 0 0 1-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112Z"
													/>
												</svg>
											</button>
										</Tooltip>
									{/if}

									<Tooltip content={$i18n.t('Regenerate')} placement="bottom">
										<button
											type="button"
											class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition regenerate-response-button"
											aria-label={$i18n.t('Regenerate')}
											onclick={() => {
												showRateComment = false;
												regenerateResponse(message);

												((model?.actions ?? []) as Array<Record<string, unknown>>).forEach(
													(action) => {
														onAction?.({
															id: action.id,
															event: {
																id: 'regenerate-response',
																data: {
																	messageId: message.id
																}
															}
														});
													}
												);
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="2.3"
												stroke="currentColor"
												class="w-4 h-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
												/>
											</svg>
										</button>
									</Tooltip>

									{#if siblings.length > 1}
										<Tooltip content={$i18n.t('Delete')} placement="bottom">
											<button
												type="button"
												id="delete-response-button"
												class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition regenerate-response-button"
												aria-label={$i18n.t('Delete')}
												onclick={() => {
													showDeleteConfirm = true;
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="2"
													stroke="currentColor"
													class="w-4 h-4"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
													/>
												</svg>
											</button>
										</Tooltip>
									{/if}

									{#if isLastMessage}
										{#each model?.actions ?? [] as action (action.id)}
											<Tooltip content={action.name} placement="bottom">
												<button
													type="button"
													class="{buttonVisibility()} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition"
													onclick={() => {
														actionMessage(action.id, message);
													}}
												>
													{#if action.icon_url}
														<div class="size-4">
															<img
																src={action.icon_url}
																class="w-4 h-4 {action.icon_url.includes('svg')
																	? 'dark:invert-[80%]'
																	: ''}"
																style="fill: currentColor;"
																alt={action.name}
															/>
														</div>
													{:else}
														<Sparkles strokeWidth="2.1" className="size-4" />
													{/if}
												</button>
											</Tooltip>
										{/each}
									{/if}
								{/if}
							{/if}
						{/if}
					</div>

					{#if message.done && showRateComment}
						<RateComment
							bind:message
							bind:show={showRateComment}
							onSave={async (e: CustomEvent) => {
								await feedbackHandler(null, {
									...e.detail
								});
							}}
						/>
					{/if}
				{/if}
			</div>
		</div>
	</div>
{/key}

<style>
	.buttons::-webkit-scrollbar {
		display: none; /* for Chrome, Safari and Opera */
	}

	.buttons {
		-ms-overflow-style: none; /* IE and Edge */
		scrollbar-width: none; /* Firefox */
	}
</style>
