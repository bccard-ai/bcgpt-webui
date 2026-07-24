<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import { toast } from 'svelte-sonner';
	import { PaneGroup, Pane } from 'paneforge';
	import type { PaneAPI } from 'paneforge';

	import { getContext, onDestroy, onMount, tick } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	const i18n: Writable<i18nType> = getContext('i18n');

	import { goto, replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';

	import { get, type Unsubscriber, type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { APP_BASE_URL, API_BASE_URL } from '$lib/constants';
	import { uploadFile } from '$lib/apis/files';
	import { ApiError } from '$lib/apis/client';
	import { logger } from '$lib/utils/logger';

	import {
		chatId,
		chats,
		config,
		type Model,
		models,
		tags as allTags,
		settings,
		showSidebar,
		APP_NAME_STORE,
		banners,
		user,
		socket,
		showControls,
		showCallOverlay,
		currentChatPage,
		temporaryChatEnabled,
		mobile,
		showOverview,
		chatTitle,
		showArtifacts,
		tools,
		toolServers
	} from '$lib/stores';
	import {
		convertMessagesToHistory,
		copyToClipboard,
		getMessageContentParts,
		createMessagesList,
		promptTemplate,
		removeDetails,
		getPromptVariables
	} from '$lib/utils';
	import { safeJsonParse } from '$lib/utils/json';
	import {
		isChatGenerationStopSettled,
		sameChatGenerationAuthority,
		type ChatGenerationAuthority
	} from '$lib/utils/chat-generation';
	import {
		migrateLegacyComposerDraft,
		readComposerDraft,
		removeComposerDraft,
		removeComposerDraftIfMatches,
		writeComposerDraft,
		type ComposerDraftScope,
		type ComposerDraftValue
	} from '$lib/utils/composer-draft';

	import {
		createNewChat,
		getAllTags,
		getChatById,
		getChatList,
		getTagsById,
		updateChatById,
		updateChatEntryInList
	} from '$lib/apis/chats';
	import { generateOpenAIChatCompletion } from '$lib/apis/openai';
	import { createChatUploads } from './chat-uploads.svelte';
	import { createOpenAITextStream } from '$lib/apis/streaming';
	import { queryMemory } from '$lib/apis/memories';
	import { getAndUpdateUserLocation, getUserSettings } from '$lib/apis/users';
	import {
		chatCompleted,
		chatAction,
		generateMoACompletion,
		getActiveChatGenerations,
		getChatGeneration,
		stopChatGeneration,
		stopTask,
		type ChatGeneration
	} from '$lib/apis';
	import { getTools } from '$lib/apis/tools';

	import Banner from '../common/Banner.svelte';
	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import Messages from '$lib/components/chat/Messages.svelte';
	import Navbar from '$lib/components/chat/Navbar.svelte';
	import ChatControls from './ChatControls.svelte';
	import EventConfirmDialog from '../common/ConfirmDialog.svelte';
	import Placeholder from './Placeholder.svelte';
	import Spinner from '../common/Spinner.svelte';

	interface Props {
		chatIdProp?: string;
	}

	interface ChatEventPayload {
		type: string;
		content: string;
		title: string;
		message: string;
		placeholder: string;
		value: string;
		user_message_id: string;
		masked_content: string;
		[key: string]: unknown;
	}

	interface ChatEvent {
		chat_id: string;
		message_id: string;
		generation_id?: string;
		data: {
			type: string;
			data: ChatEventPayload;
		};
	}

	interface HistoryMessage {
		id: string;
		role: string;
		parentId: string | null;
		childrenIds: string[];
		[key: string]: unknown;
	}

	interface HistoryType {
		messages: Record<string, HistoryMessage>;
		currentId: string | null;
		[key: string]: unknown;
	}

	let { chatIdProp = '' }: Props = $props();

	let loading = $state(false);

	const eventTarget = new EventTarget();
	let controlPane = $state<PaneAPI | null>(null);
	let controlPaneComponent = $state<{ openPane: () => void } | null>(null);

	let autoScroll = $state(true);
	let messagesContainerElement = $state<HTMLDivElement | undefined>(undefined);
	let focusedSearchAnchorKey = $state<string | null>(null);

	let dismissedBannerIds = $state<string[]>(
		safeJsonParse(localStorage.getItem('dismissedBannerIds'), [])
	);
	let saveInputTimeout: ReturnType<typeof setTimeout> | null = null;
	let composerDraftHydrated = false;
	let pendingComposerDraft: { scope: ComposerDraftScope; value: ComposerDraftValue } | null = null;
	let activeComposerDraftScope: ComposerDraftScope | null = null;
	let latestComposerInput: ComposerDraftValue = {
		prompt: '',
		selectedToolIds: [],
		imageGenerationEnabled: false,
		webSearchEnabled: false,
		contextCompressionEnabled: false,
		smartQueryEnabled: false
	};

	let navbarElement = $state<unknown>();

	let showEventConfirmation = $state(false);
	let eventConfirmationTitle = $state('');
	let eventConfirmationMessage = $state('');
	let eventConfirmationInput = $state(false);
	let eventConfirmationInputPlaceholder = $state('');
	let eventConfirmationInputValue = $state('');
	let eventCallback = $state(null as ((detail: unknown) => void) | null);

	let chatIdUnsubscriber: Unsubscriber | undefined;

	let selectedModels = $state(['']);
	let atSelectedModel: Model | undefined = $state();
	let selectedModelIds = $derived(
		atSelectedModel !== undefined ? [atSelectedModel.id] : selectedModels
	);

	let selectedToolIds = $state([] as string[]);
	let selectedSkillIds = $state([] as string[]);
	let imageGenerationEnabled = $state(false);
	let webSearchEnabled = $state(false);
	let contextCompressionEnabled = $state(false);
	let smartQueryEnabled = $state(false);

	let chat = $state(null as Record<string, unknown> | null);
	let tags: string[] = []; // eslint-disable-line @typescript-eslint/no-unused-vars -- used in template

	let history = $state<HistoryType>({
		messages: {},
		currentId: null
	});

	let activeGenerations = $state<Record<string, ChatGenerationAuthority>>({});
	let activeGenerationEpoch = 0;
	const durableGenerationObservers = new SvelteSet<string>();
	let chatComponentDestroyed = false;
	let hasActiveGeneration = $derived(
		Object.values(activeGenerations).some((authority) => authority.chatId === $chatId)
	);

	const registerActiveGeneration = (
		taskId: string | null,
		generationId: string,
		_chatId: string,
		messageId: string,
		durable = false
	): ChatGenerationAuthority => {
		const authority = {
			taskId,
			generationId,
			chatId: _chatId,
			messageId,
			epoch: ++activeGenerationEpoch,
			durable
		};
		activeGenerations = { ...activeGenerations, [messageId]: authority };
		return authority;
	};

	const bindActiveGenerationTask = (
		authority: ChatGenerationAuthority,
		taskId: string | null
	): boolean => {
		const current = activeGenerations[authority.messageId];
		if (!current || !sameChatGenerationAuthority(authority, current)) return false;
		activeGenerations = {
			...activeGenerations,
			[authority.messageId]: { ...current, taskId }
		};
		return true;
	};

	const clearActiveGeneration = (
		messageId: string,
		expected?: ChatGenerationAuthority
	): boolean => {
		const current = activeGenerations[messageId];
		if (!current || (expected && !sameChatGenerationAuthority(expected, current))) return false;

		const remaining = { ...activeGenerations };
		delete remaining[messageId];
		activeGenerations = remaining;
		return true;
	};

	const finishGenerationMessage = (authority: ChatGenerationAuthority): void => {
		const responseMessage = history.messages[authority.messageId];
		if (!responseMessage) return;

		responseMessage.done = true;
		history.messages[authority.messageId] = responseMessage;
		history = history;
	};

	const isTerminalGenerationStatus = (status: string): boolean =>
		['completed', 'stopped', 'error', 'timed_out'].includes(status);

	const applyGenerationSnapshot = (generation: ChatGeneration): void => {
		const responseMessage = history.messages[generation.message_id];
		if (!responseMessage) return;
		const replayCursor = Number(responseMessage.replayCursor ?? -1);
		if (
			generation.replay &&
			!generation.replay.degraded &&
			generation.replay.cursor > replayCursor
		) {
			responseMessage.content = generation.replay.content;
			responseMessage.replayCursor = generation.replay.cursor;
		}

		responseMessage.generationId = generation.generation_id;
		responseMessage.generationStatus = generation.status;
		responseMessage.terminalReason = generation.terminal_reason;
		responseMessage.deliveryStatus = 'accepted';
		responseMessage.done = isTerminalGenerationStatus(generation.status);
		history.messages[generation.message_id] = responseMessage;
		history = history;
	};

	const hydrateActiveChatGenerations = async (_chatId: string): Promise<boolean> => {
		const scopedChatId = _chatId.trim();
		if (!scopedChatId) return false;

		try {
			const response = await getActiveChatGenerations('', scopedChatId);
			activeGenerations = Object.fromEntries(
				Object.entries(activeGenerations).filter(
					([, authority]) => authority.chatId !== scopedChatId
				)
			);
			for (const generation of response.generations ?? []) {
				applyGenerationSnapshot(generation);
				const authority = registerActiveGeneration(
					generation.task_id,
					generation.generation_id,
					generation.chat_id,
					generation.message_id,
					true
				);
				observeDurableGeneration(authority);
			}
			return true;
		} catch (error) {
			logger.warn('chat', 'Could not recover durable chat generations', {
				chatId: _chatId,
				error
			});
			return false;
		}
	};

	const observeDurableGeneration = (authority: ChatGenerationAuthority): void => {
		if (!authority.durable || durableGenerationObservers.has(authority.generationId)) return;
		durableGenerationObservers.add(authority.generationId);
		void (async () => {
			try {
				for (let attempt = 0; attempt < 80 && !chatComponentDestroyed; attempt += 1) {
					await new Promise((resolve) => setTimeout(resolve, 750));
					if (!sameChatGenerationAuthority(authority, activeGenerations[authority.messageId])) {
						return;
					}
					const generation = await getChatGeneration('', authority.generationId, {
						chat_id: authority.chatId,
						message_id: authority.messageId
					}).catch(() => null);
					if (!generation) continue;
					applyGenerationSnapshot(generation);
					if (isTerminalGenerationStatus(generation.status)) {
						clearActiveGeneration(authority.messageId, authority);
						return;
					}
					bindActiveGenerationTask(authority, generation.task_id);
				}
			} finally {
				durableGenerationObservers.delete(authority.generationId);
			}
		})();
	};

	// Chat Input
	let prompt = $state('');
	let chatFiles = $state([] as Record<string, unknown>[]);
	let files = $state([] as Record<string, unknown>[]);
	let params = $state<Record<string, unknown>>({});

	const { uploadWeb, uploadYoutubeTranscription } = createChatUploads({
		getFiles: () => files as never[],
		setFiles: (updater) => {
			files = updater(files as never[]) as Record<string, unknown>[];
		},
		toastError: (msg) => toast.error(msg)
	});

	const getComposerDraftScope = (scopeChatId?: string | null): ComposerDraftScope | null => {
		if (scopeChatId === undefined && activeComposerDraftScope) return activeComposerDraftScope;
		const ownerId = get(user)?.id;
		if (!ownerId) return null;
		const resolvedChatId = scopeChatId ?? chatIdProp ?? get(chatId);
		return resolvedChatId && resolvedChatId !== 'local'
			? { ownerId, chatId: resolvedChatId }
			: { ownerId };
	};

	const currentComposerDraftValue = (input?: Partial<ComposerDraftValue>): ComposerDraftValue => ({
		prompt: input?.prompt ?? prompt ?? '',
		selectedToolIds: input?.selectedToolIds ?? selectedToolIds,
		imageGenerationEnabled: input?.imageGenerationEnabled ?? imageGenerationEnabled,
		webSearchEnabled: input?.webSearchEnabled ?? webSearchEnabled,
		contextCompressionEnabled: input?.contextCompressionEnabled ?? contextCompressionEnabled,
		smartQueryEnabled: input?.smartQueryEnabled ?? smartQueryEnabled
	});

	const applyComposerDraft = (draft: ComposerDraftValue): void => {
		prompt = draft.prompt;
		selectedToolIds = [...(draft.selectedToolIds ?? [])];
		imageGenerationEnabled = draft.imageGenerationEnabled === true;
		webSearchEnabled = draft.webSearchEnabled === true;
		contextCompressionEnabled = draft.contextCompressionEnabled === true;
		smartQueryEnabled = draft.smartQueryEnabled === true;
		latestComposerInput = currentComposerDraftValue(draft);
	};

	const hydrateComposerDraft = (scopeChatId?: string | null): void => {
		const scope = getComposerDraftScope(scopeChatId);
		activeComposerDraftScope = scope;
		if (!scope || get(temporaryChatEnabled)) {
			composerDraftHydrated = true;
			return;
		}

		const legacyChatId = scopeChatId ?? chatIdProp ?? '';
		const draft =
			readComposerDraft(scope) ?? migrateLegacyComposerDraft(scope, `chat-input-${legacyChatId}`);
		if (draft) applyComposerDraft(draft);
		else latestComposerInput = currentComposerDraftValue();
		composerDraftHydrated = true;
	};

	const flushComposerDraft = (): void => {
		if (!composerDraftHydrated) return;
		const scope = getComposerDraftScope();
		if (!scope) return;
		if (get(temporaryChatEnabled)) {
			removeComposerDraft(scope);
			return;
		}
		if (pendingComposerDraft && !latestComposerInput.prompt.trim()) return;
		writeComposerDraft(scope, latestComposerInput);
	};

	const handleComposerInputChange = (input: Partial<ComposerDraftValue>): void => {
		latestComposerInput = currentComposerDraftValue(input);
		if (!composerDraftHydrated) return;

		const scope = getComposerDraftScope();
		if (!scope) return;
		if (get(temporaryChatEnabled)) {
			if (saveInputTimeout) clearTimeout(saveInputTimeout);
			saveInputTimeout = null;
			removeComposerDraft(scope);
			return;
		}
		// Clearing the visible input while a submission is being admitted must not
		// erase the only durable copy of that submitted revision.
		if (pendingComposerDraft && !latestComposerInput.prompt.trim()) return;

		if (saveInputTimeout) clearTimeout(saveInputTimeout);
		saveInputTimeout = setTimeout(() => {
			writeComposerDraft(scope, latestComposerInput);
			saveInputTimeout = null;
		}, 500);
	};

	const saveSessionSelectedModels = () => {
		if (selectedModels.length === 0 || (selectedModels.length === 1 && selectedModels[0] === '')) {
			return;
		}
		sessionStorage.selectedModels = JSON.stringify(selectedModels);
	};

	const setToolIds = async () => {
		if (!get(tools)) {
			tools.set(await getTools(''));
		}

		if (selectedModels.length !== 1 && !atSelectedModel) {
			return;
		}

		const model = atSelectedModel ?? get(models).find((m) => m.id === selectedModels[0]);
		if (model) {
			selectedToolIds = (model?.info?.meta?.toolIds ?? []).filter((id) =>
				get(tools).find((t) => t.id === id)
			);
		}
	};

	const selectMessageBranch = (messageId: string | null) => {
		let leafId = messageId;
		let childIds =
			leafId === null
				? Object.keys(history.messages).filter((id) => history.messages[id].parentId === null)
				: (history.messages[leafId]?.childrenIds ?? []);
		const visited = new SvelteSet<string>();

		while (childIds.length !== 0) {
			const nextId = childIds.at(-1);
			if (!nextId || visited.has(nextId) || !history.messages[nextId]) break;
			visited.add(nextId);
			leafId = nextId;
			childIds = history.messages[nextId].childrenIds ?? [];
		}
		history.currentId = leafId;
	};

	const focusMessageElement = async (
		messageId: string,
		behavior: 'auto' | 'smooth' | 'instant' = 'smooth'
	) => {
		await tick();
		await tick();
		await tick();

		const messageElement = document.getElementById(`message-${messageId}`);
		messageElement?.scrollIntoView({ behavior, block: 'center' });
	};

	const focusSearchMessage = async (messageId: string) => {
		if (!history.messages[messageId]) return;
		selectMessageBranch(messageId);
		await focusMessageElement(messageId, 'auto');
	};

	const showMessage = async (message) => {
		const _chatId = get(chatId);
		selectMessageBranch(message.id);

		await focusMessageElement(message.id);

		await tick();
		saveChatHandler(_chatId, history);
	};

	const chatEventHandler = async (event: ChatEvent, cb: (detail: unknown) => void) => {
		if (event.chat_id === get(chatId)) {
			await tick();
			let message = history.messages[event.message_id];
			const activeGeneration = activeGenerations[event.message_id];
			if (
				activeGeneration?.durable &&
				event.generation_id &&
				event.generation_id !== activeGeneration.generationId
			) {
				logger.warn('chat', 'Ignored an event from a stale chat generation', {
					messageId: event.message_id,
					expectedGenerationId: activeGeneration.generationId,
					actualGenerationId: event.generation_id
				});
				return;
			}

			if (message) {
				const type = event?.data?.type ?? null;
				const data = event?.data?.data ?? null;

				if (type === 'status') {
					if (message?.statusHistory) {
						message.statusHistory.push(data);
					} else {
						message.statusHistory = [data];
					}
				} else if (type === 'source' || type === 'citation') {
					// Regular source.
					if (message?.sources) {
						message.sources.push(data);
					} else {
						message.sources = [data];
					}
				} else if (type === 'chat:completion') {
					chatCompletionEventHandler(data, message, event.chat_id);
				} else if (type === 'task-cancelled') {
					clearActiveGeneration(event.message_id);
					message.done = true;
					message.generationStatus = 'stopped';
					message.terminalReason = 'user_requested';
				} else if (type === 'chat:title') {
					// For `chat:title` events the backend sends the title as the `data` value itself.
					const title = (data ?? '') as unknown as string;
					chatTitle.set(title);
					chats.set(
						updateChatEntryInList(get(chats), event.chat_id, {
							title,
							updated_at: Date.now() / 1000
						})
					);
				} else if (type === 'chat:tags') {
					chat = await getChatById('', get(chatId));
					allTags.set(await getAllTags(''));
				} else if (type === 'pii_masked') {
					const userMsg = history.messages[data.user_message_id];
					if (userMsg) {
						userMsg.content = data.masked_content;
						await tick();
						saveChatHandler(get(chatId), history);
					}
				} else if (type === 'chat:message:delta' || type === 'message') {
					message.content += data.content;
				} else if (type === 'chat:message' || type === 'replace') {
					message.content = data.content;
				} else if (type === 'confirmation') {
					eventCallback = cb;

					eventConfirmationInput = false;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
				} else if (type === 'execute') {
					eventCallback = cb;

					// SECURITY: new Function() / eval() removed — arbitrary code execution
					// from server-sent events is a critical RCE vector. Return undefined
					// so callers that depend on a result value degrade gracefully.
					logger.warn(
						'chat',
						'[SECURITY] Blocked remote execute event — code execution from server events is disabled.'
					);
					if (cb) {
						cb(undefined);
					}
				} else if (type === 'input') {
					eventCallback = cb;

					eventConfirmationInput = true;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
					eventConfirmationInputPlaceholder = data.placeholder;
					eventConfirmationInputValue = data?.value ?? '';
				} else if (type === 'notification') {
					const toastType = data?.type ?? 'info';
					const toastContent = data?.content ?? '';

					if (toastType === 'success') {
						toast.success(toastContent);
					} else if (toastType === 'error') {
						toast.error(toastContent);
					} else if (toastType === 'warning') {
						toast.warning(toastContent);
					} else {
						toast.info(toastContent);
					}
				} else {
					// Unknown message type: ignored
				}

				history.messages[event.message_id] = message;
			}
		}
	};

	const onMessageHandler = async (event: {
		origin: string;
		data: { type: string; text: string };
	}) => {
		if (event.origin !== window.origin) {
			return;
		}

		// Replace with your iframe's origin
		if (event.data.type === 'input:prompt') {
			const inputElement = document.getElementById('chat-input');

			if (inputElement) {
				prompt = event.data.text;
				inputElement.focus();
			}
		}

		if (event.data.type === 'action:submit') {
			if (prompt !== '') {
				await tick();
				submitPrompt(prompt);
			}
		}

		if (event.data.type === 'input:prompt:submit') {
			if (event.data.text !== '') {
				await tick();
				submitPrompt(event.data.text);
			}
		}
	};

	onMount(async () => {
		window.addEventListener('message', onMessageHandler);
		window.addEventListener('pagehide', flushComposerDraft);
		get(socket)?.on('chat-events', chatEventHandler);

		if (!get(chatId)) {
			chatIdUnsubscriber = chatId.subscribe(async (value) => {
				if (!value) {
					await initNewChat();
				}
			});
		} else {
			if (get(temporaryChatEnabled)) {
				await goto(resolve('/'));
			}
		}

		if (!chatIdProp) hydrateComposerDraft(null);

		showControls.subscribe(async (value) => {
			if (controlPane && !get(mobile)) {
				try {
					if (value) {
						controlPaneComponent.openPane();
					} else {
						controlPane.collapse();
					}
				} catch (_e) {
					// ignore
				}
			}

			if (!value) {
				showCallOverlay.set(false);
				showOverview.set(false);
				showArtifacts.set(false);
			}
		});

		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		chats.subscribe(() => {});
	});

	onDestroy(() => {
		chatComponentDestroyed = true;
		durableGenerationObservers.clear();
		if (saveInputTimeout) clearTimeout(saveInputTimeout);
		flushComposerDraft();
		chatIdUnsubscriber?.();
		window.removeEventListener('message', onMessageHandler);
		window.removeEventListener('pagehide', flushComposerDraft);
		get(socket)?.off('chat-events', chatEventHandler);
	});

	// File upload functions

	const uploadGoogleDriveFile = async (fileData) => {
		// Validate input
		if (!fileData?.id || !fileData?.name || !fileData?.url || !fileData?.headers?.Authorization) {
			throw new Error('Invalid file data provided');
		}

		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: fileData.url,
			name: fileData.name,
			collection_name: '',
			status: 'uploading',
			error: '',
			itemId: tempItemId,
			size: 0
		};

		try {
			files = [...files, fileItem];

			// Configure fetch options with proper headers
			const fetchOptions = {
				headers: {
					Authorization: fileData.headers.Authorization,
					Accept: '*/*'
				},
				method: 'GET'
			};

			// Attempt to fetch the file
			const fileResponse = await fetch(fileData.url, fetchOptions);

			if (!fileResponse.ok) {
				const errorText = await fileResponse.text();
				throw new Error(`Failed to fetch file (${fileResponse.status}): ${errorText}`);
			}

			// Get content type from response
			const contentType = fileResponse.headers.get('content-type') || 'application/octet-stream';

			// Convert response to blob
			const fileBlob = await fileResponse.blob();

			if (fileBlob.size === 0) {
				throw new Error('Retrieved file is empty');
			}

			// Create File object with proper MIME type
			const file = new File([fileBlob], fileData.name, {
				type: fileBlob.type || contentType
			});

			if (file.size === 0) {
				throw new Error('Created file is empty');
			}

			// Upload file to server
			const uploadedFile = await uploadFile('', file);

			if (!uploadedFile) {
				throw new Error('Server returned null response for file upload');
			}

			// Update file item with upload results
			fileItem.status = 'uploaded';
			fileItem.file = uploadedFile;
			fileItem.id = uploadedFile.id;
			fileItem.size = file.size;
			fileItem.collection_name = uploadedFile?.meta?.collection_name;
			fileItem.url = `${API_BASE_URL}/files/${uploadedFile.id}`;

			files = files;
			toast.success($i18n.t('File uploaded successfully'));
		} catch (e) {
			logger.error('chat', 'Error uploading file', undefined, e);
			files = files.filter((f) => f.itemId !== tempItemId);
			toast.error(
				$i18n.t('Error uploading file: {{error}}', {
					error: e.message || 'Unknown error'
				})
			);
		}
	};

	//////////////////////////
	// Web functions
	//////////////////////////

	const initNewChat = async () => {
		if (get(page).url.searchParams.get('models')) {
			selectedModels = get(page).url.searchParams.get('models')?.split(',');
		} else if (get(page).url.searchParams.get('model')) {
			const urlModels = get(page).url.searchParams.get('model')?.split(',');

			if (urlModels.length === 1) {
				const m = get(models).find((m) => m.id === urlModels[0]);
				if (!m) {
					const modelSelectorButton = document.getElementById('model-selector-0-button');
					if (modelSelectorButton) {
						modelSelectorButton.click();
						await tick();

						const modelSelectorInput = document.getElementById('model-search-input');
						if (modelSelectorInput) {
							modelSelectorInput.focus();
							modelSelectorInput.value = urlModels[0];
							modelSelectorInput.dispatchEvent(new Event('input'));
						}
					}
				} else {
					selectedModels = urlModels;
				}
			} else {
				selectedModels = urlModels;
			}
		} else {
			if (sessionStorage.selectedModels) {
				selectedModels = safeJsonParse(sessionStorage.selectedModels, []);
				sessionStorage.removeItem('selectedModels');
			} else {
				if (get(settings)?.models) {
					selectedModels = get(settings)?.models;
				} else if (get(config)?.default_models) {
					selectedModels = get(config)?.default_models.split(',');
				}
			}
		}

		selectedModels = selectedModels.filter((modelId) =>
			get(models)
				.map((m) => m.id)
				.includes(modelId)
		);
		if (selectedModels.length === 0 || (selectedModels.length === 1 && selectedModels[0] === '')) {
			if (get(models).length > 0) {
				selectedModels = [get(models)[0].id];
			} else {
				selectedModels = [''];
			}
		}

		await showControls.set(false);
		await showCallOverlay.set(false);
		await showOverview.set(false);
		await showArtifacts.set(false);

		if (get(page).url.pathname.includes('/c/')) {
			// Use SvelteKit's replaceState (not window.history) to avoid router conflicts.
			replaceState(resolve('/'), {});
		}

		autoScroll = true;

		await chatId.set('');
		await chatTitle.set('');

		history = {
			messages: {},
			currentId: null
		};

		chatFiles = [];
		params = {};

		if (get(page).url.searchParams.get('youtube')) {
			uploadYoutubeTranscription(
				`https://www.youtube.com/watch?v=${$page.url.searchParams.get('youtube')}`
			);
		}
		if (get(page).url.searchParams.get('web-search') === 'true') {
			webSearchEnabled = true;
		}

		if (get(page).url.searchParams.get('image-generation') === 'true') {
			imageGenerationEnabled = true;
		}

		if (get(page).url.searchParams.get('tools')) {
			selectedToolIds = get(page)
				.url.searchParams.get('tools')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		} else if (get(page).url.searchParams.get('tool-ids')) {
			selectedToolIds = get(page)
				.url.searchParams.get('tool-ids')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		}

		if (get(page).url.searchParams.get('call') === 'true') {
			showCallOverlay.set(true);
			showControls.set(true);
		}

		if (get(page).url.searchParams.get('q')) {
			prompt = get(page).url.searchParams.get('q') ?? '';

			if (prompt) {
				await tick();
				submitPrompt(prompt);
			}
		}

		selectedModels = selectedModels.map((modelId) =>
			get(models)
				.map((m) => m.id)
				.includes(modelId)
				? modelId
				: ''
		);

		const userSettings = await getUserSettings('');

		if (userSettings) {
			settings.set(userSettings.ui);
		} else {
			settings.set(safeJsonParse(localStorage.getItem('settings'), {}));
		}

		const chatInput = document.getElementById('chat-input');
		setTimeout(() => chatInput?.focus(), 0);
	};

	const loadChat = async () => {
		const scopedChatId = chatIdProp.trim();
		if (!scopedChatId) return null;

		focusedSearchAnchorKey = null;
		// Capture the validated id once at entry. The global `chatId` store can
		// be reset while this component loads; all requests below must use this
		// stable value rather than the mutable store.
		const id = scopedChatId;
		chatId.set(id);
		chat = await getChatById('', id).catch(async (_error) => {
			await goto(resolve('/'));
			return null;
		});

		if (chat) {
			tags = await getTagsById('', id).catch(async (_error) => {
				return [];
			});

			const chatContent = chat.chat;

			if (chatContent) {
				selectedModels =
					(chatContent?.models ?? undefined) !== undefined
						? chatContent.models
						: [chatContent.models ?? ''];
				history =
					(chatContent?.history ?? undefined) !== undefined
						? chatContent.history
						: convertMessagesToHistory(chatContent.messages);

				chatTitle.set(chatContent.title);

				const userSettings = await getUserSettings('');

				if (userSettings) {
					await settings.set(userSettings.ui);
				} else {
					await settings.set(safeJsonParse(localStorage.getItem('settings'), {}));
				}

				params = chatContent?.params ?? {};
				chatFiles = chatContent?.files ?? [];

				autoScroll = true;
				await tick();

				const generationHydrationSucceeded = await hydrateActiveChatGenerations(scopedChatId);
				if (history.currentId) {
					const currentMessage = history.messages[history.currentId];
					let exactGenerationLookupSettled = !currentMessage?.generationId;
					if (
						currentMessage?.role === 'assistant' &&
						currentMessage.generationId &&
						!activeGenerations[currentMessage.id]
					) {
						const recovered = await getChatGeneration('', currentMessage.generationId, {
							chat_id: scopedChatId,
							message_id: currentMessage.id
						}).catch((error) => {
							if (error instanceof ApiError && error.status === 404) {
								exactGenerationLookupSettled = true;
							}
							return null;
						});
						if (recovered) {
							exactGenerationLookupSettled = true;
							applyGenerationSnapshot(recovered);
							if (!isTerminalGenerationStatus(recovered.status)) {
								const authority = registerActiveGeneration(
									recovered.task_id,
									recovered.generation_id,
									recovered.chat_id,
									recovered.message_id,
									true
								);
								observeDurableGeneration(authority);
							}
						}
					}

					if (currentMessage?.role === 'assistant' && !currentMessage.done) {
						if (
							generationHydrationSucceeded &&
							exactGenerationLookupSettled &&
							!activeGenerations[currentMessage.id]
						) {
							currentMessage.done = true;
							currentMessage.deliveryStatus = 'unknown';
							currentMessage.terminalReason = 'reload_without_generation_receipt';
							history.messages[currentMessage.id] = currentMessage;
						}
					} else if (currentMessage && currentMessage.role !== 'assistant') {
						currentMessage.done = true;
						history.messages[currentMessage.id] = currentMessage;
					}
				}
				await tick();

				return true;
			} else {
				return null;
			}
		}
	};

	const scrollToBottom = async () => {
		await tick();
		if (messagesContainerElement) {
			messagesContainerElement.scrollTo({
				top: messagesContainerElement.scrollHeight,
				behavior: 'smooth'
			});
		}
	};
	const chatCompletedHandler = async (_chatId, modelId, responseMessageId, messages) => {
		const res = await chatCompleted('', {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.usage ? { usage: m.usage } : {}),
				...(m.sources ? { sources: m.sources } : {})
			})),
			model_item: get(models).find((m) => m.id === modelId),
			chat_id: _chatId,
			session_id: get(socket)?.id,
			id: responseMessageId
		}).catch((error) => {
			toast.error(`${error}`);
			messages.at(-1).error = { content: error };

			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				if (message?.id) {
					// Add null check for message and message.id
					history.messages[message.id] = {
						...history.messages[message.id],
						...(history.messages[message.id].content !== message.content
							? { originalContent: history.messages[message.id].content }
							: {}),
						...message
					};
				}
			}
		}

		await tick();

		if (get(chatId) == _chatId) {
			if (!get(temporaryChatEnabled)) {
				chat = await updateChatById('', _chatId, {
					models: selectedModels,
					messages: messages,
					history: history,
					params: params,
					files: chatFiles
				});

				chats.set(
					updateChatEntryInList(get(chats), _chatId, {
						updated_at: chat?.updated_at || Date.now() / 1000
					})
				);
			}
		}
	};

	const chatActionHandler = async (
		_chatId,
		actionId,
		modelId,
		responseMessageId,
		event: unknown = null
	) => {
		const messages = createMessagesList(history, responseMessageId);

		const res = await chatAction('', actionId, {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.sources ? { sources: m.sources } : {})
			})),
			...(event ? { event: event } : {}),
			model_item: get(models).find((m) => m.id === modelId),
			chat_id: _chatId,
			session_id: get(socket)?.id,
			id: responseMessageId
		}).catch((error) => {
			toast.error(`${error}`);
			messages.at(-1).error = { content: error };
			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				history.messages[message.id] = {
					...history.messages[message.id],
					...(history.messages[message.id].content !== message.content
						? { originalContent: history.messages[message.id].content }
						: {}),
					...message
				};
			}
		}

		if (get(chatId) == _chatId) {
			if (!get(temporaryChatEnabled)) {
				chat = await updateChatById('', _chatId, {
					models: selectedModels,
					messages: messages,
					history: history,
					params: params,
					files: chatFiles
				});

				chats.set(
					updateChatEntryInList(get(chats), _chatId, {
						updated_at: chat?.updated_at || Date.now() / 1000
					})
				);
			}
		}
	};

	const getChatEventEmitter = async (modelId: string, chatId: string = '') => {
		return setInterval(() => {
			get(socket)?.emit('usage', {
				action: 'chat',
				model: modelId,
				chat_id: chatId
			});
		}, 1000);
	};

	const createMessagePair = async (userPrompt) => {
		prompt = '';
		if (selectedModels.length === 0) {
			toast.error($i18n.t('Model not selected'));
		} else {
			const modelId = selectedModels[0];
			const model = get(models)
				.filter((m) => m.id === modelId)
				.at(0);

			const messages = createMessagesList(history, history.currentId);
			const parentMessage = messages.length !== 0 ? messages.at(-1) : null;

			const userMessageId = uuidv4();
			const responseMessageId = uuidv4();

			const userMessage = {
				id: userMessageId,
				parentId: parentMessage ? parentMessage.id : null,
				childrenIds: [responseMessageId],
				role: 'user',
				content: userPrompt ? userPrompt : `[PROMPT] ${userMessageId}`,
				timestamp: Math.floor(Date.now() / 1000)
			};

			const responseMessage = {
				id: responseMessageId,
				parentId: userMessageId,
				childrenIds: [],
				role: 'assistant',
				content: `[RESPONSE] ${responseMessageId}`,
				done: true,

				model: modelId,
				modelName: model.name ?? model.id,
				modelIdx: 0,
				timestamp: Math.floor(Date.now() / 1000)
			};

			if (parentMessage) {
				parentMessage.childrenIds.push(userMessageId);
				history.messages[parentMessage.id] = parentMessage;
			}
			history.messages[userMessageId] = userMessage;
			history.messages[responseMessageId] = responseMessage;

			history.currentId = responseMessageId;

			await tick();

			if (autoScroll) {
				scrollToBottom();
			}

			if (messages.length === 0) {
				await initChatHandler(history);
			} else {
				await saveChatHandler(get(chatId), history);
			}
		}
	};

	const addMessages = async (payload: unknown) => {
		const { modelId, parentId, messages } = payload as {
			modelId: string;
			parentId: string;
			messages: { role: string; [key: string]: unknown }[];
		};
		const model = get(models)
			.filter((m) => m.id === modelId)
			.at(0);

		let parentMessage = history.messages[parentId];
		let currentParentId = parentMessage ? parentMessage.id : null;
		for (const message of messages) {
			let messageId = uuidv4();

			if (message.role === 'user') {
				const userMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = userMessage;
				parentMessage = userMessage;
				currentParentId = messageId;
			} else {
				const responseMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					done: true,
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: 0,
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = responseMessage;
				parentMessage = responseMessage;
				currentParentId = messageId;
			}
		}

		history.currentId = currentParentId;
		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		if (messages.length === 0) {
			await initChatHandler(history);
		} else {
			await saveChatHandler(get(chatId), history);
		}
	};

	const chatCompletionEventHandler = async (data, message, chatId) => {
		const {
			id: _id,
			done,
			choices,
			content,
			sources,
			selected_model_id,
			error,
			usage,
			generation_cursor
		} = data;

		if (
			Number.isInteger(generation_cursor) &&
			generation_cursor > Number(message.replayCursor ?? -1)
		) {
			message.replayCursor = generation_cursor;
		}

		if (error) {
			clearActiveGeneration(message.id);
			message.generationStatus = 'error';
			message.terminalReason = 'stream_error';
			await handleOpenAIError(error, message);
		}

		if (sources) {
			message.sources = sources;
		}

		if (choices) {
			if (choices[0]?.message?.content) {
				// Non-stream response
				message.content += choices[0]?.message?.content;
			} else {
				// Stream response
				let value = choices[0]?.delta?.content ?? '';
				if (message.content == '' && value == '\n') {
					// Empty response: ignore leading newline
				} else {
					message.content += value;

					if (navigator.vibrate && (get(settings)?.hapticFeedback ?? false)) {
						navigator.vibrate(5);
					}

					// Emit chat event for TTS
					const messageContentParts = getMessageContentParts(
						message.content,
						get(config)?.audio?.tts?.split_on ?? 'punctuation'
					);
					messageContentParts.pop();

					// dispatch only last sentence and make sure it hasn't been dispatched before
					if (
						messageContentParts.length > 0 &&
						messageContentParts[messageContentParts.length - 1] !== message.lastSentence
					) {
						message.lastSentence = messageContentParts[messageContentParts.length - 1];
						eventTarget.dispatchEvent(
							new CustomEvent('chat', {
								detail: {
									id: message.id,
									content: messageContentParts[messageContentParts.length - 1]
								}
							})
						);
					}
				}
			}
		}

		if (content) {
			// REALTIME_CHAT_SAVE is disabled
			message.content = content;

			if (navigator.vibrate && (get(settings)?.hapticFeedback ?? false)) {
				navigator.vibrate(5);
			}

			// Emit chat event for TTS
			const messageContentParts = getMessageContentParts(
				message.content,
				get(config)?.audio?.tts?.split_on ?? 'punctuation'
			);
			messageContentParts.pop();

			// dispatch only last sentence and make sure it hasn't been dispatched before
			if (
				messageContentParts.length > 0 &&
				messageContentParts[messageContentParts.length - 1] !== message.lastSentence
			) {
				message.lastSentence = messageContentParts[messageContentParts.length - 1];
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: {
							id: message.id,
							content: messageContentParts[messageContentParts.length - 1]
						}
					})
				);
			}
		}

		if (selected_model_id) {
			message.selectedModelId = selected_model_id;
			message.arena = true;
		}

		if (usage) {
			message.usage = usage;
		}

		history.messages[message.id] = message;

		if (done) {
			clearActiveGeneration(message.id);
			message.done = true;
			message.generationStatus = 'completed';
			message.terminalReason = 'provider_completed';

			if (get(settings).responseAutoCopy) {
				copyToClipboard(message.content);
			}

			if (get(settings).responseAutoPlayback && !get(showCallOverlay)) {
				await tick();
				document.getElementById(`speak-button-${message.id}`)?.click();
			}

			// Emit chat event for TTS
			let lastMessageContentPart =
				getMessageContentParts(
					message.content,
					get(config)?.audio?.tts?.split_on ?? 'punctuation'
				)?.at(-1) ?? '';
			if (lastMessageContentPart) {
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: { id: message.id, content: lastMessageContentPart }
					})
				);
			}
			eventTarget.dispatchEvent(
				new CustomEvent('chat:finish', {
					detail: {
						id: message.id,
						content: message.content
					}
				})
			);

			history.messages[message.id] = message;
			await chatCompletedHandler(
				chatId,
				message.model,
				message.id,
				createMessagesList(history, message.id)
			);
		}

		if (autoScroll) {
			scrollToBottom();
		}
	};

	//////////////////////////
	// Chat functions
	//////////////////////////

	const submitPrompt = async (userPrompt, _options?: unknown) => {
		const messages = createMessagesList(history, history.currentId);
		const _selectedModels = selectedModels.map((modelId) =>
			get(models)
				.map((m) => m.id)
				.includes(modelId)
				? modelId
				: ''
		);
		if (JSON.stringify(selectedModels) !== JSON.stringify(_selectedModels)) {
			selectedModels = _selectedModels;
		}

		if (userPrompt === '' && files.length === 0) {
			toast.error($i18n.t('Please enter a prompt'));
			return;
		}
		if (selectedModels.includes('')) {
			toast.error($i18n.t('Model not selected'));
			return;
		}

		if (messages.length != 0 && messages.at(-1).done != true) {
			// Response not done
			return;
		}
		if (messages.length != 0 && messages.at(-1).error && !messages.at(-1).content) {
			// Error in previous response - allow user to continue with new message
			// instead of blocking. The errored message stays in history for context.
		}
		if (
			files.length > 0 &&
			files.filter((file) => file.type !== 'image' && file.status === 'uploading').length > 0
		) {
			toast.error(
				$i18n.t(`Oops! There are files still uploading. Please wait for the upload to complete.`)
			);
			return;
		}
		if (
			(get(config)?.file?.max_count ?? null) !== null &&
			files.length + chatFiles.length > get(config)?.file?.max_count
		) {
			toast.error(
				$i18n.t(`You can only chat with a maximum of {{maxCount}} file(s) at a time.`, {
					maxCount: get(config)?.file?.max_count
				})
			);
			return;
		}

		const submittedDraftScope = getComposerDraftScope();
		const submittedDraftValue = currentComposerDraftValue({ prompt: userPrompt });
		if (saveInputTimeout) clearTimeout(saveInputTimeout);
		saveInputTimeout = null;
		if (submittedDraftScope && !get(temporaryChatEnabled)) {
			writeComposerDraft(submittedDraftScope, submittedDraftValue);
			pendingComposerDraft = { scope: submittedDraftScope, value: submittedDraftValue };
		}

		prompt = '';

		// Reset chat input textarea
		if (!(get(settings)?.richTextInput ?? true)) {
			const chatInputElement = document.getElementById('chat-input');

			if (chatInputElement) {
				await tick();
				chatInputElement.style.height = '';
			}
		}

		const _files = $state.snapshot(files);
		chatFiles.push(..._files.filter((item) => ['doc', 'file', 'collection'].includes(item.type)));
		const _seen = new SvelteSet<string>();
		chatFiles = chatFiles.filter((item) => {
			const key = JSON.stringify(item);
			if (_seen.has(key)) return false;
			_seen.add(key);
			return true;
		});

		files = [];
		prompt = '';

		// Create user message
		let userMessageId = uuidv4();
		let userMessage = {
			id: userMessageId,
			parentId: messages.length !== 0 ? messages.at(-1).id : null,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			files: _files.length > 0 ? _files : undefined,
			timestamp: Math.floor(Date.now() / 1000), // Unix epoch
			models: selectedModels
		};

		// Add message to history and Set currentId to messageId
		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		// Append messageId to childrenIds of parent message
		if (messages.length !== 0) {
			history.messages[messages.at(-1).id].childrenIds.push(userMessageId);
		}

		// focus on chat input
		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		saveSessionSelectedModels();

		let admitted = false;
		try {
			admitted = await sendPrompt(history, userPrompt, userMessageId, { newChat: true });
		} catch (error) {
			logger.error('chat', 'Prompt submission failed before admission', undefined, error);
			toast.error(`${error}`);
		}

		pendingComposerDraft = null;
		if (submittedDraftScope && !get(temporaryChatEnabled)) {
			if (admitted) {
				removeComposerDraftIfMatches(submittedDraftScope, submittedDraftValue);
				const admittedChatId = get(chatId);
				if (!chatIdProp && admittedChatId && admittedChatId !== 'local') {
					activeComposerDraftScope = getComposerDraftScope(admittedChatId);
					if (prompt.trim() && activeComposerDraftScope) {
						if (saveInputTimeout) clearTimeout(saveInputTimeout);
						saveInputTimeout = null;
						latestComposerInput = currentComposerDraftValue();
						writeComposerDraft(activeComposerDraftScope, latestComposerInput);
					}
				}
			} else if (!prompt.trim()) {
				prompt = userPrompt;
				files = _files;
				applyComposerDraft(submittedDraftValue);
				const recoveryScope = getComposerDraftScope() ?? submittedDraftScope;
				if (recoveryScope !== submittedDraftScope) removeComposerDraft(submittedDraftScope);
				writeComposerDraft(recoveryScope, submittedDraftValue);
			} else {
				latestComposerInput = currentComposerDraftValue();
				const activeScope = getComposerDraftScope();
				if (activeScope) writeComposerDraft(activeScope, latestComposerInput);
			}
		}
		return admitted;
	};

	const sendPrompt = async (
		_history,
		prompt: string,
		parentId: string,
		{ modelId = null, modelIdx = null, newChat = false } = {}
	) => {
		let _chatId = structuredClone(get(chatId));
		_history = $state.snapshot(_history);
		const persistedChatId = () => (typeof _chatId === 'string' ? _chatId.trim() : '');

		// Regeneration is only valid for an already persisted chat. A 401 can
		// clear the global chat state while this component is still visible; do
		// not turn that stale UI into POST /api/v1/chats/ (405).
		if (!get(temporaryChatEnabled) && !newChat && !persistedChatId()) {
			logger.warn('chat', 'Blocked prompt dispatch without a persisted chat ID');
			toast.error($i18n.t('Your session is no longer active. Please sign in again.'));
			return false;
		}

		const responseMessageIds: Record<PropertyKey, string> = {};
		// If modelId is provided, use it, else use selected model
		let selectedModelIds = modelId
			? [modelId]
			: atSelectedModel !== undefined
				? [atSelectedModel.id]
				: selectedModels;

		// Create response messages for each selected model
		for (const [_modelIdx, modelId] of selectedModelIds.entries()) {
			const model = get(models)
				.filter((m) => m.id === modelId)
				.at(0);

			if (model) {
				let responseMessageId = uuidv4();
				let responseMessage = {
					parentId: parentId,
					id: responseMessageId,
					childrenIds: [],
					role: 'assistant',
					content: '',
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: modelIdx ? modelIdx : _modelIdx,
					userContext: null,
					timestamp: Math.floor(Date.now() / 1000) // Unix epoch
				};

				// Add message to history and Set currentId to messageId
				history.messages[responseMessageId] = responseMessage;
				history.currentId = responseMessageId;

				// Append messageId to childrenIds of parent message
				if (parentId !== null && history.messages[parentId]) {
					// Add null check before accessing childrenIds
					history.messages[parentId].childrenIds = [
						...history.messages[parentId].childrenIds,
						responseMessageId
					];
				}

				responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`] = responseMessageId;
			}
		}
		history = history;

		// Create new chat if newChat is true and first user message
		if (newChat && _history.messages[_history.currentId].parentId === null) {
			_chatId = await initChatHandler(_history);
		}

		if (!get(temporaryChatEnabled) && !persistedChatId()) {
			logger.warn('chat', 'Blocked prompt dispatch because chat creation did not return an ID');
			toast.error($i18n.t('Unable to create a chat. Please try again.'));
			return false;
		}

		await tick();

		// $state.snapshot: history is a $state proxy; structuredClone throws DataCloneError.
		_history = $state.snapshot(history);
		// Save chat after all messages have been created
		await saveChatHandler(_chatId, _history);

		const dispatchResults = await Promise.allSettled(
			selectedModelIds.map(async (modelId, _modelIdx) => {
				const model = get(models)
					.filter((m) => m.id === modelId)
					.at(0);

				if (model) {
					const messages = createMessagesList(_history, parentId);
					// If there are image files, check if model is vision capable
					const hasImages = messages.some((message) =>
						message.files?.some((file) => file.type === 'image')
					);

					if (hasImages && !(model.info?.meta?.capabilities?.vision ?? true)) {
						toast.error(
							$i18n.t('Model {{modelName}} is not vision capable', {
								modelName: model.name ?? model.id
							})
						);
					}

					let responseMessageId =
						responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`];
					let responseMessage = _history.messages[responseMessageId];

					let userContext = null;
					if (get(settings)?.memory ?? false) {
						if (userContext === null) {
							const res = await queryMemory('', prompt).catch((error) => {
								toast.error(`${error}`);
								return null;
							});
							if (res) {
								if (res.documents[0].length > 0) {
									userContext = res.documents[0].reduce((acc, doc, index) => {
										const createdAtTimestamp = res.metadatas[0][index].created_at;
										const createdAtDate = new Date(createdAtTimestamp * 1000)
											.toISOString()
											.split('T')[0];
										return `${acc}${index + 1}. [${createdAtDate}]. ${doc}\n`;
									}, '');
								}
							}
						}
					}
					responseMessage.userContext = userContext;

					const chatEventEmitter = await getChatEventEmitter(model.id, _chatId);

					scrollToBottom();
					await sendPromptSocket(_history, model, responseMessageId, _chatId);

					if (chatEventEmitter) clearInterval(chatEventEmitter);
				} else {
					toast.error($i18n.t(`Model {{modelId}} not found`, { modelId }));
				}
			})
		);
		for (const result of dispatchResults) {
			if (result.status === 'rejected') {
				logger.error(
					'chat',
					'Model dispatch failed after prompt admission',
					undefined,
					result.reason
				);
				toast.error(`${result.reason}`);
			}
		}
		return true;
	};

	const sendPromptSocket = async (_history, model, responseMessageId, _chatId) => {
		const responseMessage = _history.messages[responseMessageId];
		const userMessage = _history.messages[responseMessage.parentId];
		const updateResponseState = (fields: Record<string, unknown>): void => {
			Object.assign(responseMessage, fields);
			const currentResponse = history.messages[responseMessageId];
			if (currentResponse) Object.assign(currentResponse, fields);
			else history.messages[responseMessageId] = responseMessage;
			history = history;
		};
		const durableGenerationEnabled =
			!get(temporaryChatEnabled) && Boolean(_chatId) && _chatId !== 'local';
		const generationId = durableGenerationEnabled ? uuidv4() : null;
		const generationAuthority = generationId
			? registerActiveGeneration(null, generationId, _chatId, responseMessageId, true)
			: null;

		if (generationAuthority) {
			updateResponseState({
				generationId: generationAuthority.generationId,
				turnId: userMessage.id,
				generationStatus: 'admitted',
				deliveryStatus: 'pending',
				done: false
			});
		}

		const recoverDurableGeneration = async (): Promise<ChatGeneration | null> => {
			if (!generationAuthority) return null;
			return getChatGeneration('', generationAuthority.generationId, {
				chat_id: generationAuthority.chatId,
				message_id: generationAuthority.messageId
			}).catch(() => null);
		};

		const reconcileDurableGeneration = (generation: ChatGeneration): void => {
			if (!generationAuthority) return;
			applyGenerationSnapshot(generation);
			if (isTerminalGenerationStatus(generation.status)) {
				clearActiveGeneration(generationAuthority.messageId, generationAuthority);
			} else {
				bindActiveGenerationTask(generationAuthority, generation.task_id);
				observeDurableGeneration(generationAuthority);
			}
		};

		let files = $state.snapshot(chatFiles);
		files.push(
			...(userMessage?.files ?? []).filter((item) =>
				['doc', 'file', 'collection'].includes(item.type)
			),
			...(responseMessage?.files ?? []).filter((item) => ['web_search_results'].includes(item.type))
		);
		const _seenFiles = new SvelteSet<string>();
		files = files.filter((item) => {
			const key = JSON.stringify(item);
			if (_seenFiles.has(key)) return false;
			_seenFiles.add(key);
			return true;
		});

		scrollToBottom();
		eventTarget.dispatchEvent(
			new CustomEvent('chat:start', {
				detail: {
					id: responseMessageId
				}
			})
		);
		await tick();

		const stream =
			model?.info?.params?.stream_response ??
			get(settings)?.params?.stream_response ??
			params?.stream_response ??
			true;

		let messages = [
			params?.system || get(settings).system || (responseMessage?.userContext ?? null)
				? {
						role: 'system',
						content: `${promptTemplate(
							params?.system ?? get(settings)?.system ?? '',
							get(user).name,
							get(settings)?.userLocation
								? await getAndUpdateUserLocation('').catch((err) => {
										logger.error('chat', 'Chat error', undefined, err);
										return undefined;
									})
								: undefined
						)}${
							(responseMessage?.userContext ?? null)
								? `\n\nUser Context:\n${responseMessage?.userContext ?? ''}`
								: ''
						}`
					}
				: undefined,
			...createMessagesList(_history, responseMessageId).map((message) => ({
				...message,
				content: removeDetails(message.content, ['reasoning'])
			}))
		].filter((message) => message);

		messages = messages
			.map((message, _idx, _arr) => ({
				role: message.role,
				...((message.files?.filter((file) => file.type === 'image').length ?? 0) > 0 &&
				message.role === 'user'
					? {
							content: [
								{
									type: 'text',
									text: message?.merged?.content ?? message.content
								},
								...message.files
									.filter((file) => file.type === 'image')
									.map((file) => ({
										type: 'image_url',
										image_url: {
											url: file.url
										}
									}))
							]
						}
					: {
							content: message?.merged?.content ?? message.content
						})
			}))
			.filter((message) => message?.role === 'user' || message?.content?.trim());

		const res = await generateOpenAIChatCompletion(
			'',
			{
				stream: stream,
				model: model.id,
				messages: messages,
				params: {
					...get(settings)?.params,
					...params,

					format: get(settings).requestFormat ?? undefined,
					keep_alive: get(settings).keepAlive ?? undefined,
					stop:
						(params?.stop ?? get(settings)?.params?.stop ?? undefined)
							? (
									params?.stop.split(',').map((token) => token.trim()) ?? get(settings).params.stop
								).map((str) => decodeURIComponent(JSON.parse('"' + str.replace(/"/g, '\\"') + '"')))
							: undefined
				},

				files: (files?.length ?? 0) > 0 ? files : undefined,
				tool_ids: selectedToolIds.length > 0 ? selectedToolIds : undefined,
				tool_servers: get(toolServers),
				skill_ids: selectedSkillIds.length > 0 ? selectedSkillIds : undefined,

				features: {
					image_generation:
						get(config)?.features?.enable_image_generation &&
						(get(user).role === 'admin' || get(user)?.permissions?.features?.image_generation)
							? imageGenerationEnabled
							: false,
					web_search:
						get(config)?.features?.enable_web_search &&
						(get(user).role === 'admin' || get(user)?.permissions?.features?.web_search)
							? webSearchEnabled ||
								(get(settings)?.webSearch ?? false) === 'always' ||
								(model?.info?.meta?.capabilities?.web_search ?? false)
							: false,
					context_compression:
						get(config)?.features?.enable_context_compression &&
						(get(user).role === 'admin' || get(user)?.permissions?.features?.context_compression)
							? contextCompressionEnabled
							: false,
					smart_query:
						get(config)?.features?.enable_smart_query &&
						(get(user).role === 'admin' || get(user)?.permissions?.features?.smart_query)
							? smartQueryEnabled
							: false
				},
				variables: {
					...getPromptVariables(
						get(user).name,
						get(settings)?.userLocation
							? await getAndUpdateUserLocation('').catch((err) => {
									logger.error('chat', 'Chat error', undefined, err);
									return undefined;
								})
							: undefined
					)
				},
				model_item: get(models).find((m) => m.id === model.id),

				session_id: get(socket)?.id,
				chat_id: _chatId,
				id: responseMessageId,
				...(generationAuthority
					? {
							generation_id: generationAuthority.generationId,
							turn_id: userMessage.id,
							client_message_id: userMessage.id
						}
					: {}),

				...(!get(temporaryChatEnabled) &&
				(messages.length == 1 ||
					(messages.length == 2 &&
						messages.at(0)?.role === 'system' &&
						messages.at(1)?.role === 'user') ||
					!get(chatTitle)?.trim()) &&
				(selectedModels[0] === model.id || atSelectedModel !== undefined)
					? {
							background_tasks: {
								title_generation: !get(chatTitle)?.trim() || (get(settings)?.title?.auto ?? true),
								tags_generation: get(settings)?.autoTags ?? true
							}
						}
					: {}),

				...(stream && (model.info?.meta?.capabilities?.usage ?? false)
					? {
							stream_options: {
								include_usage: true
							}
						}
					: {})
			},
			`${APP_BASE_URL}/api`
		).catch(async (error) => {
			if (generationAuthority) {
				const recovered = await recoverDurableGeneration();
				if (recovered) {
					reconcileDurableGeneration(recovered);
					if (!isTerminalGenerationStatus(recovered.status)) {
						toast.warning(
							$i18n.t(
								'The request was accepted, but its connection was interrupted. You can still stop it safely.'
							)
						);
					}
					return null;
				}

				const definitiveClientRejection =
					error instanceof ApiError &&
					error.status >= 400 &&
					error.status < 500 &&
					![408, 425, 429].includes(error.status);
				if (definitiveClientRejection) {
					clearActiveGeneration(responseMessageId, generationAuthority);
					updateResponseState({
						error: { content: error.message },
						deliveryStatus: 'rejected',
						generationStatus: 'error',
						terminalReason: 'request_rejected',
						done: true
					});
					toast.error(error.message);
				} else {
					updateResponseState({ deliveryStatus: 'unknown', done: false });
					observeDurableGeneration(generationAuthority);
					toast.warning(
						$i18n.t(
							'Could not confirm whether the request was accepted. It remains available to Stop safely.'
						)
					);
				}
			} else {
				toast.error(`${error}`);
				updateResponseState({ error: { content: error }, done: true });
			}

			history.currentId = responseMessageId;
			return null;
		});

		if (res) {
			if (res.error) {
				await handleOpenAIError(res.error, responseMessage);
				if (generationAuthority) {
					const recovered = await recoverDurableGeneration();
					if (recovered) reconcileDurableGeneration(recovered);
				}
			} else if (generationAuthority) {
				const responseBindingMatches =
					(res.generation_id === undefined ||
						res.generation_id === generationAuthority.generationId) &&
					(res.chat_id === undefined || res.chat_id === generationAuthority.chatId) &&
					(res.message_id === undefined || res.message_id === generationAuthority.messageId);
				if (!responseBindingMatches) {
					logger.error(
						'chat',
						'Admission returned a mismatched durable generation binding',
						undefined,
						{
							expectedGenerationId: generationAuthority.generationId,
							expectedChatId: generationAuthority.chatId,
							expectedMessageId: generationAuthority.messageId,
							actualGenerationId: res.generation_id,
							actualChatId: res.chat_id,
							actualMessageId: res.message_id
						}
					);
					updateResponseState({ deliveryStatus: 'unknown', done: false });
					toast.error($i18n.t('The response could not be attached to this message.'));
					await stopChatGeneration('', generationAuthority.generationId, {
						chat_id: generationAuthority.chatId,
						message_id: generationAuthority.messageId
					})
						.then((receipt) => {
							if (receipt.generation) reconcileDurableGeneration(receipt.generation);
						})
						.catch(() => undefined);
				} else {
					const generation = res.admission?.generation as ChatGeneration | undefined;
					if (generation) {
						reconcileDurableGeneration(generation);
					} else if (res.admission?.terminal || res.admission?.accepted === false) {
						clearActiveGeneration(responseMessageId, generationAuthority);
						updateResponseState({
							deliveryStatus: 'accepted',
							generationStatus: res.admission?.stopped ? 'stopped' : 'error',
							done: true
						});
					} else if (!history.messages[responseMessageId]?.done && get(chatId) === _chatId) {
						bindActiveGenerationTask(generationAuthority, res.task_id ?? null);
						observeDurableGeneration(generationAuthority);
						updateResponseState({
							deliveryStatus: 'accepted',
							generationStatus: res.task_id ? 'running' : 'admitted'
						});
					}
				}
			} else if (res.task_id) {
				const responseBindingMatches =
					(res.chat_id === undefined || res.chat_id === _chatId) &&
					(res.message_id === undefined || res.message_id === responseMessageId);
				if (!responseBindingMatches) {
					logger.error(
						'chat',
						'Task admission returned a mismatched generation binding',
						undefined,
						{
							expectedChatId: _chatId,
							expectedMessageId: responseMessageId,
							actualChatId: res.chat_id,
							actualMessageId: res.message_id
						}
					);
					toast.error($i18n.t('The response could not be attached to this message.'));
					responseMessage.error = {
						content: $i18n.t('The response could not be attached to this message.')
					};
					responseMessage.done = true;
					history.messages[responseMessageId] = responseMessage;
				} else if (!history.messages[responseMessageId]?.done && get(chatId) === _chatId) {
					registerActiveGeneration(
						res.task_id,
						res.generation_id ?? res.task_id,
						_chatId,
						responseMessageId
					);
				}
			}
		}

		await tick();
		scrollToBottom();
	};

	const handleOpenAIError = async (error, responseMessage) => {
		let errorMessage = '';
		let innerError;

		if (error) {
			innerError = error;
		}

		logger.error('chat', 'Chat error', undefined, innerError);
		if ('detail' in innerError) {
			// FastAPI error
			toast.error(innerError.detail);
			errorMessage = innerError.detail;
		} else if ('error' in innerError) {
			// OpenAI error
			if ('message' in innerError.error) {
				toast.error(innerError.error.message);
				errorMessage = innerError.error.message;
			} else {
				toast.error(innerError.error);
				errorMessage = innerError.error;
			}
		} else if ('message' in innerError) {
			// OpenAI error
			toast.error(innerError.message);
			errorMessage = innerError.message;
		}

		responseMessage.error = {
			content: $i18n.t(`Uh-oh! There was an issue with the response.`) + '\n' + errorMessage
		};
		responseMessage.done = true;

		if (responseMessage.statusHistory) {
			responseMessage.statusHistory = responseMessage.statusHistory.filter(
				(status) => status.action !== 'knowledge_search'
			);
		}

		history.messages[responseMessage.id] = responseMessage;
	};

	const stopResponse = async () => {
		const currentChatId = get(chatId);
		const capturedGenerations = Object.values(activeGenerations).filter(
			(authority) => authority.chatId === currentChatId
		);
		if (capturedGenerations.length === 0) return;

		const stopResults = await Promise.allSettled(
			capturedGenerations.map(async (authority) => {
				const binding = {
					chat_id: authority.chatId,
					message_id: authority.messageId
				};
				if (authority.durable) {
					return {
						authority,
						receipt: await stopChatGeneration('', authority.generationId, binding)
					};
				}
				if (!authority.taskId) throw new Error('Legacy generation has no task authority');
				return {
					authority,
					receipt: await stopTask('', authority.taskId, binding)
				};
			})
		);

		for (const result of stopResults) {
			if (result.status === 'rejected') {
				toast.error(`${result.reason}`);
				continue;
			}

			const { authority, receipt } = result.value;
			if (!sameChatGenerationAuthority(authority, activeGenerations[authority.messageId])) {
				continue;
			}
			const receiptMatches = authority.durable
				? receipt.generation_id === authority.generationId &&
					receipt.chat_id === authority.chatId &&
					receipt.message_id === authority.messageId
				: receipt.task_id === authority.taskId && receipt.generation_id === authority.generationId;
			if (!receiptMatches) {
				logger.error('chat', 'Ignored a Stop receipt for a different task generation', undefined, {
					expectedTaskId: authority.taskId,
					actualTaskId: receipt.task_id,
					actualGenerationId: receipt.generation_id
				});
				continue;
			}
			if (!isChatGenerationStopSettled(receipt)) {
				if (receipt.generation) applyGenerationSnapshot(receipt.generation);
				else {
					const responseMessage = history.messages[authority.messageId];
					if (responseMessage) {
						responseMessage.generationStatus = 'stop_requested';
						responseMessage.deliveryStatus = 'accepted';
						history.messages[authority.messageId] = responseMessage;
						history = history;
					}
				}
				observeDurableGeneration(authority);
				continue;
			}

			clearActiveGeneration(authority.messageId, authority);
			if (receipt.status !== 'different_generation') {
				if (receipt.generation) applyGenerationSnapshot(receipt.generation);
				finishGenerationMessage(authority);
			} else {
				logger.warn('chat', 'Cleared a stale local generation after a binding mismatch', {
					taskId: authority.taskId,
					chatId: authority.chatId,
					messageId: authority.messageId
				});
			}
		}

		if (autoScroll) scrollToBottom();
	};

	const submitMessage = async (parentId, prompt) => {
		let userPrompt = prompt;
		let userMessageId = uuidv4();

		let userMessage = {
			id: userMessageId,
			parentId: parentId,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			models: selectedModels
		};

		if (parentId !== null) {
			history.messages[parentId].childrenIds = [
				...history.messages[parentId].childrenIds,
				userMessageId
			];
		}

		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		await tick();
		await sendPrompt(history, userPrompt, userMessageId);
	};

	const regenerateResponse = async (message) => {
		if (!get(temporaryChatEnabled) && !String(get(chatId) ?? '').trim()) {
			logger.warn('chat', 'Blocked regeneration without a persisted chat ID');
			toast.error($i18n.t('Your session is no longer active. Please sign in again.'));
			return false;
		}

		if (history.currentId) {
			let userMessage = history.messages[message.parentId];
			let userPrompt = userMessage.content;

			if ((userMessage?.models ?? [...selectedModels]).length == 1) {
				// If user message has only one model selected, sendPrompt automatically selects it for regeneration
				await sendPrompt(history, userPrompt, userMessage.id);
			} else {
				// If there are multiple models selected, use the model of the response message for regeneration
				// e.g. many model chat
				await sendPrompt(history, userPrompt, userMessage.id, {
					modelId: message.model,
					modelIdx: message.modelIdx
				});
			}
		}
	};

	const continueResponse = async () => {
		const _chatId = get(chatId);

		if (history.currentId && history.messages[history.currentId].done == true) {
			const responseMessage = history.messages[history.currentId];
			responseMessage.done = false;
			await tick();

			const model = get(models)
				.filter((m) => m.id === (responseMessage?.selectedModelId ?? responseMessage.model))
				.at(0);

			if (model) {
				await sendPromptSocket(history, model, responseMessage.id, _chatId);
			}
		}
	};

	const mergeResponses = async (messageId, responses, _chatId) => {
		const message = history.messages[messageId];
		const mergedResponse = {
			status: true,
			content: ''
		};
		message.merged = mergedResponse;
		history.messages[messageId] = message;

		try {
			const [res, _controller] = await generateMoACompletion(
				'',
				message.model,
				history.messages[message.parentId].content,
				responses
			);

			if (res && res.ok && res.body) {
				const textStream = await createOpenAITextStream(res.body, get(settings).splitLargeChunks);
				for await (const update of textStream) {
					const { value, done, sources: _sources, error, usage: _usage } = update;
					if (error || done) {
						break;
					}

					if (mergedResponse.content == '' && value == '\n') {
						continue;
					} else {
						mergedResponse.content += value;
						history.messages[messageId] = message;
					}

					if (autoScroll) {
						scrollToBottom();
					}
				}

				await saveChatHandler(_chatId, history);
			} else {
				logger.error('chat', 'Chat error response', undefined, res);
			}
		} catch (e) {
			logger.error('chat', 'Chat error', undefined, e);
		}
	};

	const initChatHandler = async (history) => {
		let _chatId = get(chatId);

		if (!get(temporaryChatEnabled)) {
			chat = await createNewChat('', {
				id: _chatId,
				title: $i18n.t('New Chat'),
				models: selectedModels,
				system: get(settings).system ?? undefined,
				params: params,
				history: history,
				messages: createMessagesList(history, history.currentId),
				tags: [],
				timestamp: Date.now()
			});

			_chatId = chat.id;
			await chatId.set(_chatId);

			await chats.set(await getChatList('', get(currentChatPage)));
			currentChatPage.set(1);

			// Use SvelteKit's replaceState (not window.history) to avoid router conflicts.
			replaceState(resolve(`/c/${_chatId}`), {});
		} else {
			_chatId = 'local';
			await chatId.set('local');
		}
		await tick();

		return _chatId;
	};

	const saveChatHandler = async (_chatId, history) => {
		const persistedChatId = typeof _chatId === 'string' ? _chatId.trim() : '';
		if (!persistedChatId) {
			logger.warn('chat', 'Skipped chat save without a persisted chat ID');
			return;
		}

		if (get(chatId) == persistedChatId) {
			if (!get(temporaryChatEnabled)) {
				chat = await updateChatById('', persistedChatId, {
					models: selectedModels,
					history: history,
					messages: createMessagesList(history, history.currentId),
					params: params,
					files: chatFiles
				});
				chats.set(
					updateChatEntryInList(get(chats), persistedChatId, {
						updated_at: chat?.updated_at || Date.now() / 1000
					})
				);
			}
		}
	};

	$effect(() => {
		const scopedChatId = chatIdProp.trim();
		if (scopedChatId) {
			(async () => {
				if (saveInputTimeout) clearTimeout(saveInputTimeout);
				saveInputTimeout = null;
				if (!pendingComposerDraft) flushComposerDraft();
				composerDraftHydrated = false;
				loading = true;

				prompt = '';
				files = [];
				selectedToolIds = [];
				webSearchEnabled = false;
				imageGenerationEnabled = false;
				contextCompressionEnabled = false;
				smartQueryEnabled = false;

				if (chatIdProp && (await loadChat())) {
					await tick();
					hydrateComposerDraft(chatIdProp);
					loading = false;

					const requestedMessageId = get(page).url.searchParams.get('message');
					if (requestedMessageId && history.messages[requestedMessageId]) {
						focusedSearchAnchorKey = `${chatIdProp}:${requestedMessageId}`;
						window.setTimeout(() => focusSearchMessage(requestedMessageId), 0);
					} else {
						window.setTimeout(() => scrollToBottom(), 0);
					}
					const chatInput = document.getElementById('chat-input');
					chatInput?.focus();
				} else {
					await goto(resolve('/'));
				}
			})();
		}
	});
	$effect(() => {
		const requestedMessageId = $page.url.searchParams.get('message');
		const anchorKey = requestedMessageId ? `${chatIdProp}:${requestedMessageId}` : null;
		if (
			anchorKey &&
			!loading &&
			focusedSearchAnchorKey !== anchorKey &&
			history.messages[requestedMessageId]
		) {
			focusedSearchAnchorKey = anchorKey;
			void focusSearchMessage(requestedMessageId);
		}
	});
	$effect(() => {
		if (selectedModels && chatIdProp !== '') {
			saveSessionSelectedModels();
		}
	});
	$effect(() => {
		if (atSelectedModel || selectedModels) {
			setToolIds();
		}
	});
	$effect(() => {
		if ($temporaryChatEnabled && composerDraftHydrated) {
			if (saveInputTimeout) clearTimeout(saveInputTimeout);
			saveInputTimeout = null;
			const scope = getComposerDraftScope();
			if (scope) removeComposerDraft(scope);
		}
	});
</script>

<svelte:head>
	<title>
		{$chatTitle
			? `${$chatTitle.length > 30 ? `${$chatTitle.slice(0, 30)}...` : $chatTitle} | ${$APP_NAME_STORE}`
			: `${$APP_NAME_STORE}`}
	</title>
</svelte:head>

<audio id="audioElement" src="" style="display: none;"></audio>

<EventConfirmDialog
	bind:show={showEventConfirmation}
	title={eventConfirmationTitle}
	message={eventConfirmationMessage}
	input={eventConfirmationInput}
	inputPlaceholder={eventConfirmationInputPlaceholder}
	inputValue={eventConfirmationInputValue}
	onconfirm={(value: string) => {
		if (value) {
			eventCallback(value);
		} else {
			eventCallback(true);
		}
	}}
	onCancel={() => {
		eventCallback(false);
	}}
/>

<div
	class="h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? '  md:max-w-[calc(100%-260px)]'
		: ' '} w-full max-w-full flex flex-col"
	id="chat-container"
>
	{#if chatIdProp === '' || (!loading && chatIdProp)}
		{#if $settings?.backgroundImageUrl ?? null}
			<div
				class="absolute {$showSidebar
					? 'md:max-w-[calc(100%-260px)] md:translate-x-[260px]'
					: ''} top-0 left-0 w-full h-full bg-cover bg-center bg-no-repeat"
				style="background-image: url({$settings.backgroundImageUrl})  "
			></div>

			<div
				class="absolute top-0 left-0 w-full h-full bg-linear-to-t from-white to-white/85 dark:from-gray-900 dark:to-gray-900/90 z-0"
			></div>
		{/if}

		<Navbar
			bind:this={navbarElement}
			chat={{
				id: $chatId,
				chat: {
					title: $chatTitle,
					models: selectedModels,
					system: $settings.system ?? undefined,
					params: params,
					history: history,
					timestamp: Date.now()
				}
			}}
			title={$chatTitle}
			bind:selectedModels
			shareEnabled={!!history.currentId}
			{initNewChat}
		/>

		<PaneGroup direction="horizontal" class="w-full h-full">
			<Pane defaultSize={50} class="h-full flex w-full relative">
				{#if !history.currentId && !$chatId && selectedModels.length <= 1 && ($banners.length > 0 || ($config?.license_metadata?.type ?? null) === 'trial')}
					<div class="absolute top-12 left-0 right-0 w-full z-30">
						<div class=" flex flex-col gap-1 w-full">
							{#if ($config?.license_metadata?.type ?? null) === 'trial'}
								<Banner
									banner={{
										type: 'info',
										title: $i18n.t('Trial License'),
										content: $i18n.t(
											'You are currently using a trial license. Please contact support to upgrade your license.'
										)
									}}
								/>
							{/if}

							{#each $banners.filter( (b) => (b.dismissible ? !dismissedBannerIds.includes(b.id) : true) ) as banner (banner.id)}
								<Banner
									{banner}
									onDismiss={(e: CustomEvent) => {
										const bannerId = e.detail;
										dismissedBannerIds = [bannerId, ...dismissedBannerIds].filter((id) =>
											$banners.find((b) => b.id === id)
										);
										localStorage.setItem('dismissedBannerIds', JSON.stringify(dismissedBannerIds));
									}}
								/>
							{/each}
						</div>
					</div>
				{/if}

				<div class="flex flex-col flex-auto z-10 w-full @container">
					{#if $settings?.landingPageMode === 'chat' || createMessagesList(history, history.currentId).length > 0}
						<div
							class=" pb-2.5 flex flex-col justify-between w-full flex-auto overflow-auto h-0 max-w-full z-10 scrollbar-hidden"
							id="messages-container"
							bind:this={messagesContainerElement}
							onscroll={(_e: Event) => {
								autoScroll =
									messagesContainerElement.scrollHeight - messagesContainerElement.scrollTop <=
									messagesContainerElement.clientHeight + 5;
							}}
						>
							<div class=" h-full w-full flex flex-col">
								<Messages
									chatId={$chatId}
									bind:history
									bind:autoScroll
									bind:prompt
									{selectedModels}
									{atSelectedModel}
									sendPrompt={sendPrompt as (...args: unknown[]) => unknown}
									{showMessage}
									{submitMessage}
									{continueResponse}
									{regenerateResponse}
									{mergeResponses}
									{chatActionHandler}
									{addMessages}
									bottomPadding={files.length > 0}
								/>
							</div>
						</div>

						<div class=" pb-[1rem]">
							<MessageInput
								{history}
								{selectedModels}
								bind:files
								bind:prompt
								bind:autoScroll
								bind:selectedToolIds
								bind:imageGenerationEnabled
								bind:webSearchEnabled
								bind:contextCompressionEnabled
								bind:smartQueryEnabled
								bind:atSelectedModel
								toolServers={$toolServers}
								transparentBackground={$settings?.backgroundImageUrl ?? false}
								generating={hasActiveGeneration}
								{stopResponse}
								{createMessagePair}
								onchange={handleComposerInputChange}
								onUpload={async (e: CustomEvent) => {
									const { type, data } = e.detail;

									if (type === 'web') {
										await uploadWeb(data);
									} else if (type === 'youtube') {
										await uploadYoutubeTranscription(data);
									} else if (type === 'google-drive') {
										await uploadGoogleDriveFile(data);
									}
								}}
								onSubmit={async (text) => {
									if (text || files.length > 0) {
										await tick();
										submitPrompt(
											($settings?.richTextInput ?? true) ? text.replaceAll('\n\n', '\n') : text
										);
									}
								}}
							/>

							{#if $settings?.ai_transparency_enabled !== false}
								<p class="mx-4 mt-2 mb-1 text-xs text-center text-gray-500">
									{$settings?.ai_notification_message ||
										$i18n.t('This service uses generative AI.')}
								</p>
							{/if}

							<div
								class="absolute bottom-1 text-xs text-gray-500 text-center line-clamp-1 right-0 left-0"
							>
								{#if $settings?.ai_transparency_enabled !== false}
									{$settings?.ai_disclaimer_text ||
										$i18n.t(
											'AI responses are for reference only. For final confirmation of financial transactions, please contact a representative.'
										)}
								{/if}
							</div>
						</div>
					{:else}
						<div class="overflow-auto w-full h-full flex items-center">
							<Placeholder
								{history}
								{selectedModels}
								bind:files
								bind:prompt
								bind:autoScroll
								bind:selectedToolIds
								bind:imageGenerationEnabled
								bind:webSearchEnabled
								bind:contextCompressionEnabled
								bind:smartQueryEnabled
								bind:atSelectedModel
								transparentBackground={$settings?.backgroundImageUrl ?? false}
								toolServers={$toolServers}
								{stopResponse}
								generating={hasActiveGeneration}
								{createMessagePair}
								onchange={handleComposerInputChange}
								onUpload={async (e: CustomEvent) => {
									const { type, data } = e.detail;

									if (type === 'web') {
										await uploadWeb(data);
									} else if (type === 'youtube') {
										await uploadYoutubeTranscription(data);
									} else if (type === 'google-drive') {
										await uploadGoogleDriveFile(data);
									}
								}}
								onSubmit={async (text) => {
									if (text || files.length > 0) {
										await tick();
										submitPrompt(
											($settings?.richTextInput ?? true) ? text.replaceAll('\n\n', '\n') : text
										);
									}
								}}
							/>
						</div>
					{/if}
				</div>
			</Pane>

			<ChatControls
				bind:this={controlPaneComponent}
				bind:history
				bind:chatFiles
				bind:params
				bind:files
				bind:pane={controlPane}
				chatId={$chatId}
				modelId={selectedModelIds?.at(0) ?? ''}
				models={selectedModelIds.reduce((a, e, _i, _arr) => {
					const model = $models.find((m) => m.id === e);
					if (model) {
						return [...a, model];
					}
					return a;
				}, [] as Model[])}
				{submitPrompt}
				{stopResponse}
				{showMessage}
				{eventTarget}
			/>
		</PaneGroup>
	{:else if loading}
		<div class=" flex items-center justify-center h-full w-full">
			<div class="m-auto">
				<Spinner />
			</div>
		</div>
	{/if}
</div>
