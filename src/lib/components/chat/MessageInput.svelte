<script lang="ts">
	import { get } from 'svelte/store';
	import { logger } from '$lib/utils/logger';
	import { preventDefault } from 'svelte/legacy';

	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';
	import { createPicker } from '$lib/utils/google-drive-picker';
	import { pickAndDownloadFile } from '$lib/utils/onedrive-file-picker';

	import { onMount, tick, getContext, onDestroy } from 'svelte';
	import { type Model, mobile, settings, models, config, tools, user as _user } from '$lib/stores';

	import { compressImage, createMessagesList, findWordIndices } from '$lib/utils';
	import { uploadFile } from '$lib/apis/files';
	import { generateAutoCompletion } from '$lib/apis';
	import { deleteFileById } from '$lib/apis/files';

	import { API_BASE_URL, PASTED_TEXT_CHARACTER_LIMIT } from '$lib/constants';

	import InputMenu from './MessageInput/InputMenu.svelte';
	import VoiceRecording from './MessageInput/VoiceRecording.svelte';
	import FilesOverlay from './MessageInput/FilesOverlay.svelte';
	import Commands from './MessageInput/Commands.svelte';

	import RichTextInput from '../common/RichTextInput.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import FileItem from '../common/FileItem.svelte';
	import Image from '../common/Image.svelte';

	import XMark from '../icons/XMark.svelte';
	import GlobeAlt from '../icons/GlobeAlt.svelte';
	import Photo from '../icons/Photo.svelte';
	import ToolServersModal from './ToolServersModal.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Whether the background should be transparent */
		transparentBackground?: boolean;
		/** Callback when any input state changes */
		onchange?: (input: {
			prompt?: string;
			files?: unknown[];
			selectedToolIds?: string[];
			imageGenerationEnabled?: boolean;
			webSearchEnabled?: boolean;
			contextCompressionEnabled?: boolean;
			smartQueryEnabled?: boolean;
		}) => void;
		/** Create a pre-filled message pair */
		createMessagePair: (messages: unknown) => void;
		/** Stop the current streaming response */
		stopResponse: () => void;
		/** Whether any response generation for the current chat is active */
		generating?: boolean;
		/** Whether auto-scroll is enabled */
		autoScroll?: boolean;
		/** The @-selected model override */
		atSelectedModel?: Model | undefined;
		/** Currently selected model IDs */
		selectedModels: [''];
		/** Chat history object */
		history: Record<string, unknown>;
		/** Current prompt text */
		prompt?: string;
		/** Attached files */
		files?: Record<string, unknown>[];
		/** Available tool servers */
		toolServers?: unknown[];
		/** Selected tool IDs */
		selectedToolIds?: string[];
		/** Whether image generation is enabled */
		imageGenerationEnabled?: boolean;
		/** Whether web search is enabled */
		webSearchEnabled?: boolean;
		/** Whether context compression is enabled */
		contextCompressionEnabled?: boolean;
		/** Whether smart query is enabled */
		smartQueryEnabled?: boolean;
		/** Input placeholder text */
		placeholder?: string;
		/** Callback when the user submits the prompt */
		onSubmit?: (...args: unknown[]) => void;
		/** Callback for file upload events */
		onUpload?: (...args: unknown[]) => void;
	}

	let {
		transparentBackground = false,
		onchange = () => {},
		createMessagePair,
		stopResponse,
		generating = false,
		autoScroll = $bindable(false),
		atSelectedModel = $bindable(undefined),
		selectedModels,
		history,
		prompt = $bindable(''),
		files = $bindable([]),
		toolServers = [],
		selectedToolIds = $bindable([]),
		imageGenerationEnabled = $bindable(false),
		webSearchEnabled = $bindable(false),
		contextCompressionEnabled = $bindable(false),
		smartQueryEnabled = $bindable(false),
		placeholder = '',
		onSubmit = () => {},
		onUpload = () => {}
	}: Props = $props();

	// ---------------------------------------------------------------------------
	// Component State
	// ---------------------------------------------------------------------------

	let selectedModelIds = $derived(
		atSelectedModel !== undefined ? [atSelectedModel.id] : selectedModels
	);
	let showToolServers = $state(false);
	let loaded = $state(false);
	let recording = $state(false);
	let isComposing = $state(false);
	let chatInputElement = $state();
	let filesInputElement = $state();
	let commandsElement = $state();
	let inputFiles = $state();
	let dragged = $state(false);
	let visionCapableModels = $derived(
		[...(atSelectedModel ? [atSelectedModel] : selectedModels)].filter(
			(modelId) =>
				get(models).find((m) => m.id === modelId)?.info?.meta?.capabilities?.vision ?? true
		)
	);

	// ---------------------------------------------------------------------------
	// Scroll Helpers
	// ---------------------------------------------------------------------------

	/** Scroll the messages container to the bottom */
	const scrollToBottom = (): void => {
		const element = document.getElementById('messages-container');
		element?.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
	};

	// ---------------------------------------------------------------------------
	// Screen Capture
	// ---------------------------------------------------------------------------

	/**
	 * Capture a screenshot of the user's screen and add it as an image file.
	 * Uses the Screen Capture API and converts the frame to a data URL.
	 */
	const screenCaptureHandler = async (): Promise<void> => {
		try {
			const mediaStream = await navigator.mediaDevices.getDisplayMedia({
				video: { cursor: 'never' },
				audio: false
			});

			const video = document.createElement('video');
			video.srcObject = mediaStream;
			await video.play();

			const canvas = document.createElement('canvas');
			canvas.width = video.videoWidth;
			canvas.height = video.videoHeight;

			const ctx = canvas.getContext('2d');
			ctx!.drawImage(video, 0, 0, canvas.width, canvas.height);

			mediaStream.getTracks().forEach((track) => track.stop());
			window.focus();

			const imageUrl = canvas.toDataURL('image/png');
			files = [...files, { type: 'image', url: imageUrl }];
			video.srcObject = null;
		} catch (error) {
			logger.error('chat', 'Error capturing screen', undefined, error);
		}
	};

	// ---------------------------------------------------------------------------
	// File Upload
	// ---------------------------------------------------------------------------

	/**
	 * Upload a single file to the server and track its upload progress in the files array.
	 * Returns null on failure, the file item on success.
	 */
	const uploadFileHandler = async (
		file: File,
		fullContext: boolean = false
	): Promise<Record<string, unknown> | null> => {
		if (get(_user)?.role !== 'admin' && !(get(_user)?.permissions?.chat?.file_upload ?? true)) {
			toast.error($i18n.t('You do not have permission to upload files.'));
			return null;
		}

		const tempItemId = uuidv4();
		const fileItem: Record<string, unknown> = {
			type: 'file',
			file: '',
			id: null,
			url: '',
			name: file.name,
			collection_name: '',
			status: 'uploading',
			size: file.size,
			error: '',
			itemId: tempItemId,
			...(fullContext ? { context: 'full' } : {})
		};

		if (file.size === 0) {
			toast.error($i18n.t('You cannot upload an empty file.'));
			return null;
		}

		files = [...files, fileItem];

		try {
			const uploadedFile = await uploadFile('', file);

			if (uploadedFile) {
				if (uploadedFile.error) {
					logger.warn('chat', 'File upload warning', uploadedFile.error);
					toast.warning(uploadedFile.error);
				}

				fileItem.status = 'uploaded';
				fileItem.file = uploadedFile;
				fileItem.id = uploadedFile.id;
				fileItem.collection_name =
					uploadedFile?.meta?.collection_name || uploadedFile?.collection_name;
				fileItem.url = `${API_BASE_URL}/files/${uploadedFile.id}`;
				files = files;
			} else {
				files = files.filter((item) => item?.itemId !== tempItemId);
			}
		} catch (e) {
			toast.error(`${e}`);
			files = files.filter((item) => item?.itemId !== tempItemId);
		}

		return fileItem;
	};

	/**
	 * Process a list of input files: images are read as data URLs,
	 * other files are uploaded to the server.
	 */
	const inputFilesHandler = async (inputFileList: File[]): Promise<void> => {
		const IMAGE_TYPES = ['image/gif', 'image/webp', 'image/jpeg', 'image/png', 'image/avif'];

		for (const file of inputFileList) {
			// Check file size limit
			const maxSize = (get(config)?.file?.max_size ?? null) as number | null;
			if (maxSize !== null && file.size > maxSize * 1024 * 1024) {
				toast.error($i18n.t(`File size should not exceed {{maxSize}} MB.`, { maxSize }));
				continue;
			}

			if (IMAGE_TYPES.includes(file.type)) {
				// Image file: read as data URL, optionally compress
				if (visionCapableModels.length === 0) {
					toast.error($i18n.t('Selected model(s) do not support image inputs'));
					continue;
				}

				const reader = new FileReader();
				reader.onload = async (event) => {
					let imageUrl = event.target?.result as string;

					if (get(settings)?.imageCompression ?? false) {
						const width = get(settings)?.imageCompressionSize?.width ?? null;
						const height = get(settings)?.imageCompressionSize?.height ?? null;
						if (width || height) {
							imageUrl = await compressImage(imageUrl, width, height);
						}
					}

					files = [...files, { type: 'image', url: imageUrl }];
				};
				reader.readAsDataURL(file);
			} else {
				// Non-image file: upload to server
				await uploadFileHandler(file);
			}
		}
	};

	// ---------------------------------------------------------------------------
	// Drag and Drop
	// ---------------------------------------------------------------------------

	const handleKeyDown = (event: KeyboardEvent): void => {
		if (event.key === 'Escape') {
			dragged = false;
		}
	};

	const onDragOver = (e: DragEvent): void => {
		e.preventDefault();
		dragged = e.dataTransfer?.types?.includes('Files') ?? false;
	};

	const onDragLeave = (): void => {
		dragged = false;
	};

	const onDrop = async (e: DragEvent): Promise<void> => {
		e.preventDefault();
		if (e.dataTransfer?.files) {
			const droppedFiles = Array.from(e.dataTransfer.files);
			if (droppedFiles.length > 0) {
				inputFilesHandler(droppedFiles);
			}
		}
		dragged = false;
	};

	// ---------------------------------------------------------------------------
	// Computed State
	// ---------------------------------------------------------------------------

	/** Resolve model IDs from the @-selected model or selected models list */
	/** Notify parent of input state changes */
	$effect(() => {
		onchange({
			prompt,
			files,
			selectedToolIds,
			imageGenerationEnabled,
			webSearchEnabled,
			contextCompressionEnabled,
			smartQueryEnabled
		});
	});

	// ---------------------------------------------------------------------------
	// Lifecycle
	// ---------------------------------------------------------------------------

	onMount(async () => {
		loaded = true;

		window.setTimeout(() => {
			document.getElementById('chat-input')?.focus();
		}, 0);

		window.addEventListener('keydown', handleKeyDown);
		await tick();

		const dropzone = document.getElementById('chat-container');
		dropzone?.addEventListener('dragover', onDragOver);
		dropzone?.addEventListener('drop', onDrop);
		dropzone?.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		window.removeEventListener('keydown', handleKeyDown);

		const dropzone = document.getElementById('chat-container');
		if (dropzone) {
			dropzone.removeEventListener('dragover', onDragOver);
			dropzone.removeEventListener('drop', onDrop);
			dropzone.removeEventListener('dragleave', onDragLeave);
		}
	});
</script>

<FilesOverlay show={dragged} />

<ToolServersModal bind:show={showToolServers} />

{#if loaded}
	<div class="w-full font-primary">
		<div class=" mx-auto inset-x-0 bg-transparent flex justify-center">
			<div
				class="flex flex-col px-3 {($settings?.widescreenMode ?? null)
					? 'max-w-full'
					: 'max-w-6xl'} w-full"
			>
				<div class="relative">
					{#if autoScroll === false && history?.currentId}
						<div
							class=" absolute -top-12 left-0 right-0 flex justify-center z-30 pointer-events-none"
						>
							<button
								class=" bg-white border border-gray-100 dark:border-none dark:bg-white/20 p-1.5 rounded-full pointer-events-auto"
								aria-label={$i18n.t('Scroll to bottom')}
								onclick={() => {
									autoScroll = true;
									scrollToBottom();
								}}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="w-5 h-5"
								>
									<path
										fill-rule="evenodd"
										d="M10 3a.75.75 0 01.75.75v10.638l3.96-4.158a.75.75 0 111.08 1.04l-5.25 5.5a.75.75 0 01-1.08 0l-5.25-5.5a.75.75 0 111.08-1.04l3.96 4.158V3.75A.75.75 0 0110 3z"
										clip-rule="evenodd"
									/>
								</svg>
							</button>
						</div>
					{/if}
				</div>

				<div class="w-full relative">
					{#if atSelectedModel !== undefined || selectedToolIds.length > 0 || webSearchEnabled || ($settings?.webSearch ?? false) === 'always' || imageGenerationEnabled || contextCompressionEnabled || smartQueryEnabled}
						<div
							class="px-3 pb-0.5 pt-1.5 text-left w-full flex flex-col absolute bottom-0 left-0 right-0 bg-linear-to-t from-white dark:from-gray-900 z-10"
						>
							{#if selectedToolIds.length > 0}
								<div class="flex items-center justify-between w-full">
									<div class="flex items-center gap-2.5 text-sm dark:text-gray-500">
										<div class="pl-1">
											<span class="relative flex size-2">
												<span
													class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"
												></span>
												<span class="relative inline-flex rounded-full size-2 bg-yellow-500"></span>
											</span>
										</div>
										<div class="  text-ellipsis line-clamp-1 flex">
											{#each selectedToolIds.map((id) => {
												return $tools ? $tools.find((t) => t.id === id) : { id: id, name: id };
											}) as tool, toolIdx (toolIdx)}
												<Tooltip
													content={tool?.meta?.description ?? ''}
													className=" {toolIdx !== 0 ? 'pl-0.5' : ''} shrink-0"
													placement="top"
												>
													{tool.name}
												</Tooltip>

												{#if toolIdx !== selectedToolIds.length - 1}
													<span>, </span>
												{/if}
											{/each}
										</div>
									</div>
								</div>
							{/if}

							{#if atSelectedModel !== undefined}
								<div class="flex items-center justify-between w-full">
									<div class="pl-[1px] flex items-center gap-2 text-sm dark:text-gray-500">
										<img
											crossorigin="anonymous"
											alt="model profile"
											class="size-3.5 max-w-[28px] object-cover rounded-full"
											src={$models.find((model) => model.id === atSelectedModel.id)?.info?.meta
												?.profile_image_url ??
												($i18n.language === 'dg-DG' ? `/doge.png` : `/static/favicon.png`)}
										/>
										<div class="translate-y-[0.5px]">
											{$i18n.t('Talking to')}
											<span class=" font-medium">{atSelectedModel.name}</span>
										</div>
									</div>
									<div>
										<button
											class="flex items-center dark:text-gray-500"
											onclick={() => {
												atSelectedModel = undefined;
											}}
										>
											<XMark />
										</button>
									</div>
								</div>
							{/if}
						</div>
					{/if}

					<Commands
						bind:this={commandsElement}
						bind:prompt
						bind:files
						onUpload={(data) => {
							onUpload?.(data);
						}}
						onSelect={(...args: unknown[]) => {
							const data = args[0] as { type?: string; data?: Model } | undefined;
							if (data?.type === 'model') {
								atSelectedModel = data.data;
							}

							document.getElementById('chat-input')?.focus();
						}}
					/>
				</div>
			</div>
		</div>

		<div class="{transparentBackground ? 'bg-transparent' : 'bg-white dark:bg-gray-900'} ">
			<div
				class="{($settings?.widescreenMode ?? null)
					? 'max-w-full'
					: 'max-w-6xl'} px-2.5 mx-auto inset-x-0"
			>
				<div class="">
					<input
						bind:this={filesInputElement}
						bind:files={inputFiles}
						type="file"
						hidden
						multiple
						onchange={async () => {
							if (inputFiles && inputFiles.length > 0) {
								inputFilesHandler(Array.from(inputFiles));
							} else {
								toast.error($i18n.t(`File not found.`));
							}
							filesInputElement.value = '';
						}}
					/>

					{#if recording}
						<VoiceRecording
							bind:recording
							onCancel={async () => {
								recording = false;
								await tick();
								document.getElementById('chat-input')?.focus();
							}}
							onconfirm={async (...args: unknown[]) => {
								const e = args[0] as { detail: { text: string } };
								const { text } = e.detail;
								prompt = `${prompt}${text} `;
								recording = false;

								await tick();
								document.getElementById('chat-input')?.focus();

								if ($settings?.speechAutoSend ?? false) {
									onSubmit?.(prompt);
								}
							}}
						/>
					{:else}
						<form
							class="w-full flex gap-1.5"
							onsubmit={preventDefault(() => {
								let submitPrompt = prompt;
								if (!submitPrompt && chatInputElement) {
									submitPrompt = chatInputElement.getText?.() ?? '';
								}
								onSubmit?.(submitPrompt);
							})}
						>
							<div
								class="flex-1 flex flex-col relative w-full shadow-lg rounded-3xl border border-gray-100 dark:border-gray-850 hover:border-gray-200 focus-within:border-gray-200 hover:dark:border-gray-800 focus-within:dark:border-gray-800 transition px-1 bg-white/90 dark:bg-gray-400/5 dark:text-gray-100"
								dir={$settings?.chatDirection ?? 'LTR'}
							>
								{#if files.length > 0}
									<div class="mx-2 mt-2.5 -mb-1 flex items-center flex-wrap gap-2">
										{#each files as file, fileIdx (fileIdx)}
											{#if file.type === 'image'}
												<div class=" relative group">
													<div class="relative flex items-center">
														<Image
															src={file.url as string}
															alt="input"
															imageClassName=" size-14 rounded-xl object-cover"
														/>
														{#if atSelectedModel ? visionCapableModels.length === 0 : selectedModels.length !== visionCapableModels.length}
															<Tooltip
																className=" absolute top-1 left-1"
																content={$i18n.t('{{ models }}', {
																	models: [
																		...(atSelectedModel ? [atSelectedModel] : selectedModels)
																	]
																		.filter((id) => !visionCapableModels.includes(id))
																		.join(', ')
																})}
															>
																<svg
																	xmlns="http://www.w3.org/2000/svg"
																	viewBox="0 0 24 24"
																	fill="currentColor"
																	class="size-4 fill-yellow-300"
																>
																	<path
																		fill-rule="evenodd"
																		d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003ZM12 8.25a.75.75 0 0 1 .75.75v3.75a.75.75 0 0 1-1.5 0V9a.75.75 0 0 1 .75-.75Zm0 8.25a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z"
																		clip-rule="evenodd"
																	/>
																</svg>
															</Tooltip>
														{/if}
													</div>
													<div class=" absolute -top-1 -right-1">
														<button
															class=" bg-white text-black border border-white rounded-full group-hover:visible invisible transition"
															type="button"
															aria-label={$i18n.t('Remove file')}
															onclick={() => {
																files.splice(fileIdx, 1);
																files = files;
															}}
														>
															<svg
																xmlns="http://www.w3.org/2000/svg"
																viewBox="0 0 20 20"
																fill="currentColor"
																class="size-4"
															>
																<path
																	d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
																/>
															</svg>
														</button>
													</div>
												</div>
											{:else}
												<FileItem
													item={file as { file?: { data?: { content?: string } } } | null}
													name={file.name as string}
													type={file.type as string}
													size={(file?.size ?? 0) as number}
													loading={file.status === 'uploading'}
													dismissible={true}
													edit={true}
													onDismiss={async () => {
														if (file.type !== 'collection' && !file?.collection) {
															if (file.id) {
																await deleteFileById('', file.id as string);
															}
														}
														files.splice(fileIdx, 1);
														files = files;
													}}
													onClick={() => {}}
												/>
											{/if}
										{/each}
									</div>
								{/if}

								<div class="px-2.5">
									{#if $settings?.richTextInput ?? true}
										<div
											class="scrollbar-hidden text-left bg-transparent dark:text-gray-100 outline-hidden w-full pt-3 px-1 resize-none h-fit max-h-80 overflow-auto"
										>
											<RichTextInput
												bind:this={chatInputElement}
												bind:value={prompt}
												id="chat-input"
												messageInput={true}
												shiftEnter={!($settings?.ctrlEnterToSend ?? false) &&
													(!$mobile ||
														!(
															'ontouchstart' in window ||
															navigator.maxTouchPoints > 0 ||
															navigator.msMaxTouchPoints > 0
														))}
												placeholder={placeholder ? placeholder : $i18n.t('Send a Message')}
												largeTextAsFile={$settings?.largeTextAsFile ?? false}
												autocomplete={$config?.features?.enable_autocomplete_generation &&
													($settings?.promptAutocomplete ?? false)}
												generateAutoCompletion={async (text) => {
													if (selectedModelIds.length === 0 || !selectedModelIds.at(0)) {
														toast.error($i18n.t('Please select a model first.'));
													}

													const res = await generateAutoCompletion(
														'',
														selectedModelIds.at(0),
														text,
														history?.currentId
															? createMessagesList(history, history.currentId)
															: null
													).catch(() => null);

													return res;
												}}
												oncompositionstart={() => (isComposing = true)}
												oncompositionend={() => (isComposing = false)}
												onkeydown={async (wrapper: { detail: { event: Event } }) => {
													const e = wrapper.detail.event as KeyboardEvent;
													const isCtrlPressed = e.ctrlKey || e.metaKey;
													const commandsContainer = document.getElementById('commands-container');

													if (e.key === 'Escape') stopResponse();
													if (isCtrlPressed && e.key === 'Enter' && e.shiftKey) {
														e.preventDefault();
														createMessagePair(prompt);
													}
													if (prompt === '' && isCtrlPressed && e.key.toLowerCase() === 'r') {
														e.preventDefault();
														[...document.getElementsByClassName('regenerate-response-button')]
															?.at(-1)
															?.click();
													}
													if (prompt === '' && e.key == 'ArrowUp') {
														e.preventDefault();
														const userEl = [...document.getElementsByClassName('user-message')]?.at(
															-1
														);
														if (userEl) {
															userEl.scrollIntoView({ block: 'center' });
															[...document.getElementsByClassName('edit-user-message-button')]
																?.at(-1)
																?.click();
														}
													}

													if (commandsContainer) {
														if (e.key === 'ArrowUp') {
															e.preventDefault();
															commandsElement.selectUp();
															[...document.getElementsByClassName('selected-command-option-button')]
																?.at(-1)
																?.scrollIntoView({ block: 'center' });
														}
														if (e.key === 'ArrowDown') {
															e.preventDefault();
															commandsElement.selectDown();
															[...document.getElementsByClassName('selected-command-option-button')]
																?.at(-1)
																?.scrollIntoView({ block: 'center' });
														}
														if (e.key === 'Tab') {
															e.preventDefault();
															[...document.getElementsByClassName('selected-command-option-button')]
																?.at(-1)
																?.click();
														}
														if (e.key === 'Enter') {
															e.preventDefault();
															const btn = [
																...document.getElementsByClassName('selected-command-option-button')
															]?.at(-1);
															if (btn) btn.click();
															else document.getElementById('send-message-button')?.click();
														}
													} else {
														if (
															!$mobile ||
															!(
																'ontouchstart' in window ||
																navigator.maxTouchPoints > 0 ||
																navigator.msMaxTouchPoints > 0
															)
														) {
															if (isComposing) return;
															const enterPressed =
																($settings?.ctrlEnterToSend ?? false)
																	? (e.key === 'Enter' || e.keyCode === 13) && isCtrlPressed
																	: (e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey;
															if (enterPressed) {
																e.preventDefault();
																let submitPrompt = prompt;
																if (!submitPrompt && chatInputElement)
																	submitPrompt = chatInputElement.getText?.() ?? '';
																if (submitPrompt !== '' || files.length > 0)
																	onSubmit?.(submitPrompt);
															}
														}
													}

													if (e.key === 'Escape') {
														atSelectedModel = undefined;
														selectedToolIds = [];
														webSearchEnabled = false;
														imageGenerationEnabled = false;
														contextCompressionEnabled = false;
														smartQueryEnabled = false;
													}
												}}
												onpaste={async (wrapper: { detail: { event: Event } }) => {
													const e = wrapper.detail.event as ClipboardEvent;
													const clipboardData = e.clipboardData || window.clipboardData;
													if (!clipboardData?.items) return;

													for (const item of clipboardData.items) {
														if (item.type.indexOf('image') !== -1) {
															const blob = item.getAsFile();
															const reader = new FileReader();
															reader.onload = function (ev) {
																files = [...files, { type: 'image', url: `${ev.target?.result}` }];
															};
															reader.readAsDataURL(blob);
														} else if (item.type === 'text/plain') {
															if ($settings?.largeTextAsFile ?? false) {
																const text = clipboardData.getData('text/plain');
																if (text.length > PASTED_TEXT_CHARACTER_LIMIT) {
																	e.preventDefault();
																	const blob = new Blob([text], { type: 'text/plain' });
																	const file = new File([blob], `Pasted_Text_${Date.now()}.txt`, {
																		type: 'text/plain'
																	});
																	await uploadFileHandler(file, true);
																}
															}
														}
													}
												}}
												onchange={(e: { detail: { value: string } }) => {
													if (e.detail?.value !== undefined) prompt = e.detail.value;
												}}
											/>
										</div>
									{:else}
										<textarea
											id="chat-input"
											bind:this={chatInputElement}
											class="scrollbar-hidden bg-transparent dark:text-gray-100 outline-hidden w-full pt-3 px-1 resize-none"
											placeholder={placeholder ? placeholder : $i18n.t('Send a Message')}
											bind:value={prompt}
											oncompositionstart={() => (isComposing = true)}
											oncompositionend={() => (isComposing = false)}
											onkeydown={async (e: KeyboardEvent) => {
												const isCtrlPressed = e.ctrlKey || e.metaKey;
												const commandsContainer = document.getElementById('commands-container');

												if (e.key === 'Escape') stopResponse();
												if (isCtrlPressed && e.key === 'Enter' && e.shiftKey) {
													e.preventDefault();
													createMessagePair(prompt);
												}
												if (prompt === '' && isCtrlPressed && e.key.toLowerCase() === 'r') {
													e.preventDefault();
													[...document.getElementsByClassName('regenerate-response-button')]
														?.at(-1)
														?.click();
												}
												if (prompt === '' && e.key == 'ArrowUp') {
													e.preventDefault();
													const userEl = [...document.getElementsByClassName('user-message')]?.at(
														-1
													);
													const editBtn = [
														...document.getElementsByClassName('edit-user-message-button')
													]?.at(-1);
													userEl?.scrollIntoView({ block: 'center' });
													editBtn?.click();
												}

												if (commandsContainer) {
													if (e.key === 'ArrowUp') {
														e.preventDefault();
														commandsElement.selectUp();
														[...document.getElementsByClassName('selected-command-option-button')]
															?.at(-1)
															?.scrollIntoView({ block: 'center' });
													}
													if (e.key === 'ArrowDown') {
														e.preventDefault();
														commandsElement.selectDown();
														[...document.getElementsByClassName('selected-command-option-button')]
															?.at(-1)
															?.scrollIntoView({ block: 'center' });
													}
													if (e.key === 'Enter') {
														e.preventDefault();
														const btn = [
															...document.getElementsByClassName('selected-command-option-button')
														]?.at(-1);
														if (e.shiftKey) prompt = `${prompt}\n`;
														else if (btn) btn.click();
														else document.getElementById('send-message-button')?.click();
													}
													if (e.key === 'Tab') {
														e.preventDefault();
														[...document.getElementsByClassName('selected-command-option-button')]
															?.at(-1)
															?.click();
													}
												} else {
													if (
														!$mobile ||
														!(
															'ontouchstart' in window ||
															navigator.maxTouchPoints > 0 ||
															navigator.msMaxTouchPoints > 0
														)
													) {
														if (isComposing) return;
														const ctrlPressed = e.ctrlKey || e.metaKey;
														const enterPressed =
															($settings?.ctrlEnterToSend ?? false)
																? (e.key === 'Enter' || e.keyCode === 13) && ctrlPressed
																: (e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey;
														if (enterPressed) e.preventDefault();
														if ((prompt !== '' || files.length > 0) && enterPressed)
															onSubmit?.(prompt);
													}
												}

												if (e.key === 'Tab') {
													const words = findWordIndices(prompt);
													if (words.length > 0) {
														const word = words.at(0);
														const fullPrompt = prompt;
														prompt = prompt.substring(0, word?.endIndex + 1);
														await tick();
														if (e.target)
															e.target.scrollTop = (e.target as HTMLTextAreaElement).scrollHeight;
														prompt = fullPrompt;
														await tick();
														e.preventDefault();
														(e.target as HTMLTextAreaElement)!.setSelectionRange(
															word?.startIndex ?? 0,
															(word?.endIndex ?? 0) + 1
														);
													}
													(e.target as HTMLTextAreaElement)!.style.height = '';
													(e.target as HTMLTextAreaElement)!.style.height =
														Math.min((e.target as HTMLTextAreaElement)!.scrollHeight, 320) + 'px';
												}

												if (e.key === 'Escape') {
													atSelectedModel = undefined;
													selectedToolIds = [];
													webSearchEnabled = false;
													imageGenerationEnabled = false;
													contextCompressionEnabled = false;
													smartQueryEnabled = false;
												}
											}}
											rows="1"
											oninput={async (e) => {
												(e.target as HTMLTextAreaElement)!.style.height = '';
												(e.target as HTMLTextAreaElement)!.style.height =
													Math.min((e.target as HTMLTextAreaElement)!.scrollHeight, 320) + 'px';
											}}
											onfocus={async (e) => {
												(e.target as HTMLTextAreaElement)!.style.height = '';
												(e.target as HTMLTextAreaElement)!.style.height =
													Math.min((e.target as HTMLTextAreaElement)!.scrollHeight, 320) + 'px';
											}}
											onpaste={async (e: ClipboardEvent) => {
												const clipboardData = e.clipboardData || window.clipboardData;
												if (!clipboardData?.items) return;

												for (const item of clipboardData.items) {
													if (item.type.indexOf('image') !== -1) {
														const blob = item.getAsFile();
														const reader = new FileReader();
														reader.onload = function (ev) {
															files = [...files, { type: 'image', url: `${ev.target?.result}` }];
														};
														reader.readAsDataURL(blob);
													} else if (item.type === 'text/plain') {
														if ($settings?.largeTextAsFile ?? false) {
															const text = clipboardData.getData('text/plain');
															if (text.length > PASTED_TEXT_CHARACTER_LIMIT) {
																e.preventDefault();
																const blob = new Blob([text], { type: 'text/plain' });
																const file = new File([blob], `Pasted_Text_${Date.now()}.txt`, {
																	type: 'text/plain'
																});
																await uploadFileHandler(file, true);
															}
														}
													}
												}
											}}
										></textarea>
									{/if}
								</div>

								<div class=" flex justify-between mt-1.5 mb-2.5 mx-0.5 max-w-full">
									<div class="ml-1 self-end gap-0.5 flex items-center flex-1 max-w-[80%]">
										<InputMenu
											bind:selectedToolIds
											{screenCaptureHandler}
											{inputFilesHandler}
											uploadFilesHandler={() => {
												filesInputElement.click();
											}}
											uploadGoogleDriveHandler={async () => {
												try {
													const fileData = await createPicker();
													if (fileData) {
														const file = new File([fileData.blob], fileData.name, {
															type: fileData.blob.type
														});
														await uploadFileHandler(file);
													}
												} catch (error) {
													logger.error('chat', 'Google Drive Error', undefined, error);
													toast.error(
														$i18n.t('Error accessing Google Drive: {{error}}', {
															error: error.message
														})
													);
												}
											}}
											uploadOneDriveHandler={async () => {
												try {
													const fileData = await pickAndDownloadFile();
													if (fileData) {
														const file = new File([fileData.blob], fileData.name, {
															type: fileData.blob.type || 'application/octet-stream'
														});
														await uploadFileHandler(file);
													}
												} catch (error) {
													logger.error('chat', 'OneDrive Error', undefined, error);
												}
											}}
											onClose={async () => {
												await tick();
												document.getElementById('chat-input')?.focus();
											}}
										>
											<button
												class="bg-transparent hover:bg-gray-100 text-gray-800 dark:text-white dark:hover:bg-gray-800 transition rounded-full p-1.5 outline-hidden focus:outline-hidden"
												type="button"
												aria-label={$i18n.t('More')}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 20 20"
													fill="currentColor"
													class="size-5"
												>
													<path
														d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z"
													/>
												</svg>
											</button>
										</InputMenu>

										<div class="flex gap-0.5 items-center overflow-x-auto scrollbar-none flex-1">
											{#if $_user}
												{#if $config?.features?.enable_web_search && ($_user.role === 'admin' || $_user?.permissions?.features?.web_search)}
													<Tooltip content={$i18n.t('Search the internet')} placement="top">
														<button
															onclick={preventDefault(() => (webSearchEnabled = !webSearchEnabled))}
															type="button"
															class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden {webSearchEnabled ||
															($settings?.webSearch ?? false) === 'always'
																? 'bg-blue-100 dark:bg-blue-500/20 text-blue-500 dark:text-blue-400'
																: 'bg-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}"
														>
															<GlobeAlt className="size-5" strokeWidth="1.75" />
															<span
																class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px] mr-0.5"
																>{$i18n.t('Web Search')}</span
															>
														</button>
													</Tooltip>
												{/if}

												{#if $config?.features?.enable_context_compression && ($_user.role === 'admin' || $_user?.permissions?.features?.context_compression)}
													<Tooltip
														content={$i18n.t('Compress conversation history')}
														placement="top"
													>
														<button
															onclick={preventDefault(
																() => (contextCompressionEnabled = !contextCompressionEnabled)
															)}
															type="button"
															class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden {contextCompressionEnabled
																? 'bg-purple-100 dark:bg-purple-500/20 text-purple-500 dark:text-purple-400'
																: 'bg-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}"
														>
															<svg
																xmlns="http://www.w3.org/2000/svg"
																viewBox="0 0 24 24"
																fill="currentColor"
																class="size-5"
																style="stroke-width: 1.75"
															>
																<path
																	d="M3.375 3C2.339 3 1.5 3.84 1.5 4.875v.75c0 1.036.84 1.875 1.875 1.875h17.25c1.035 0 1.875-.84 1.875-1.875v-.75C22.5 3.839 21.66 3 20.625 3H3.375Z"
																/>
																<path
																	fill-rule="evenodd"
																	d="m3.087 9 .54 9.176A3 3 0 0 0 6.62 21h10.757a3 3 0 0 0 2.995-2.824L20.913 9H3.087Zm6.163 3.75A.75.75 0 0 1 10 12h4a.75.75 0 0 1 0 1.5h-4a.75.75 0 0 1-.75-.75Z"
																	clip-rule="evenodd"
																/>
															</svg>
															<span
																class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px] mr-0.5"
																>{$i18n.t('Compress')}</span
															>
														</button>
													</Tooltip>
												{/if}

												{#if $config?.features?.enable_smart_query && ($_user.role === 'admin' || $_user?.permissions?.features?.smart_query)}
													<Tooltip content={$i18n.t('Enhance query with context')} placement="top">
														<button
															onclick={preventDefault(
																() => (smartQueryEnabled = !smartQueryEnabled)
															)}
															type="button"
															class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden {smartQueryEnabled
																? 'bg-green-100 dark:bg-green-500/20 text-green-500 dark:text-green-400'
																: 'bg-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}"
														>
															<svg
																xmlns="http://www.w3.org/2000/svg"
																viewBox="0 0 24 24"
																fill="currentColor"
																class="size-5"
																style="stroke-width: 1.75"
															>
																<path
																	d="M11.625 16.5a1.875 1.875 0 1 0 0-3.75 1.875 1.875 0 0 0 0 3.75Z"
																/>
																<path
																	fill-rule="evenodd"
																	d="M5.625 1.5H9a3.75 3.75 0 0 1 3.75 3.75v1.875c0 1.036.84 1.875 1.875 1.875h1.875A3.75 3.75 0 0 1 20.25 12v7.875c0 1.035-.84 1.875-1.875 1.875H5.625a1.875 1.875 0 0 1-1.875-1.875V3.375c0-1.036.84-1.875 1.875-1.875Zm6 14.25a3.375 3.375 0 1 0 0-6.75 3.375 3.375 0 0 0 0 6.75ZM8.25 8.625a1.125 1.125 0 1 0 0-2.25 1.125 1.125 0 0 0 0 2.25Z"
																	clip-rule="evenodd"
																/>
															</svg>
															<span
																class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px] mr-0.5"
																>{$i18n.t('Smart Query')}</span
															>
														</button>
													</Tooltip>
												{/if}

												{#if $config?.features?.enable_image_generation && ($_user.role === 'admin' || $_user?.permissions?.features?.image_generation)}
													<Tooltip content={$i18n.t('Generate an image')} placement="top">
														<button
															onclick={preventDefault(
																() => (imageGenerationEnabled = !imageGenerationEnabled)
															)}
															type="button"
															class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden {imageGenerationEnabled
																? 'bg-gray-100 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400'
																: 'bg-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 '}"
														>
															<Photo className="size-5" strokeWidth="1.75" />
															<span
																class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px] mr-0.5"
																>{$i18n.t('Image')}</span
															>
														</button>
													</Tooltip>
												{/if}
											{/if}
										</div>
									</div>

									<div class="self-end flex space-x-1 mr-1 shrink-0">
										{#if toolServers.length > 0}
											<Tooltip
												content={$i18n.t('{{COUNT}} Available Tool Servers', {
													COUNT: toolServers.length
												})}
											>
												<button
													class="translate-y-[1.5px] flex gap-1 items-center text-gray-600 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg px-1.5 py-0.5 mr-0.5 self-center border border-gray-100 dark:border-gray-800 transition"
													aria-label={$i18n.t('Available Tool Servers')}
													type="button"
													onclick={() => {
														showToolServers = !showToolServers;
													}}
												>
													<svg
														xmlns="http://www.w3.org/2000/svg"
														fill="none"
														viewBox="0 0 24 24"
														stroke-width="1.5"
														stroke="currentColor"
														class="size-3"
													>
														<path
															stroke-linecap="round"
															stroke-linejoin="round"
															d="M21.75 6.75a4.5 4.5 0 0 1-4.884 4.484c-1.076-.091-2.264.071-2.95.904l-7.152 8.684a2.548 2.548 0 1 1-3.586-3.586l8.684-7.152c.833-.686.995-1.874.904-2.95a4.5 4.5 0 0 1 6.336-4.486l-3.276 3.276a3.004 3.004 0 0 0 2.25 2.25l3.276-3.276c.256.565.398 1.192.398 1.852Z"
														/>
														<path
															stroke-linecap="round"
															stroke-linejoin="round"
															d="M4.867 19.125h.008v.008h-.008v-.008Z"
														/>
													</svg>
													<span class="text-xs">{toolServers.length}</span>
												</button>
											</Tooltip>
										{/if}

										{#if !generating}
											<Tooltip content={$i18n.t('Record voice')}>
												<button
													id="voice-input-button"
													class=" text-gray-600 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-200 transition rounded-full p-1.5 mr-0.5 self-center"
													type="button"
													onclick={async () => {
														try {
															let stream = await navigator.mediaDevices
																.getUserMedia({ audio: true })
																.catch((err) => {
																	toast.error(
																		$i18n.t(
																			'Permission denied when accessing microphone: {{error}}',
																			{ error: err }
																		)
																	);
																	return null;
																});
															if (stream) {
																recording = true;
																stream.getTracks().forEach((track) => track.stop());
															}
															stream = null;
														} catch {
															toast.error($i18n.t('Permission denied when accessing microphone'));
														}
													}}
													aria-label={$i18n.t('Voice Input')}
												>
													<svg
														xmlns="http://www.w3.org/2000/svg"
														viewBox="0 0 20 20"
														fill="currentColor"
														class="w-5 h-5 translate-y-[0.5px]"
													>
														<path d="M7 4a3 3 0 016 0v6a3 3 0 11-6 0V4z" />
														<path
															d="M5.5 9.643a.75.75 0 00-1.5 0V10c0 3.06 2.29 5.585 5.25 5.954V17.5h-1.5a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-1.5v-1.546A6.001 6.001 0 0016 10v-.357a.75.75 0 00-1.5 0V10a4.5 4.5 0 01-9 0v-.357z"
														/>
													</svg>
												</button>
											</Tooltip>
										{/if}

										{#if !generating}
											<div class=" flex items-center">
												<Tooltip content={$i18n.t('Send message')}>
													<button
														id="send-message-button"
														aria-label={$i18n.t('Send message')}
														class="{!(prompt === '' && files.length === 0)
															? webSearchEnabled || ($settings?.webSearch ?? false) === 'always'
																? 'bg-blue-500 text-white hover:bg-blue-400 '
																: 'bg-black text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100 '
															: 'text-white bg-gray-200 dark:text-gray-900 dark:bg-gray-700 disabled'} transition rounded-full p-1.5 self-center"
														type="submit"
														disabled={!prompt && files.length === 0}
													>
														<svg
															xmlns="http://www.w3.org/2000/svg"
															viewBox="0 0 16 16"
															fill="currentColor"
															class="size-5"
														>
															<path
																fill-rule="evenodd"
																d="M8 14a.75.75 0 0 1-.75-.75V4.56L4.03 7.78a.75.75 0 0 1-1.06-1.06l4.5-4.5a.75.75 0 0 1 1.06 0l4.5 4.5a.75.75 0 0 1-1.06 1.06L8.75 4.56v8.69A.75.75 0 0 1 8 14Z"
																clip-rule="evenodd"
															/>
														</svg>
													</button>
												</Tooltip>
											</div>
										{:else}
											<div class=" flex items-center">
												<Tooltip content={$i18n.t('Stop')}>
													<button
														class="bg-white hover:bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-800 transition rounded-full p-1.5"
														aria-label={$i18n.t('Stop')}
														onclick={stopResponse}
													>
														<svg
															xmlns="http://www.w3.org/2000/svg"
															viewBox="0 0 24 24"
															fill="currentColor"
															class="size-5"
														>
															<path
																fill-rule="evenodd"
																d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm6-2.438c0-.724.588-1.312 1.313-1.312h4.874c.725 0 1.313.588 1.313 1.313v4.874c0 .725-.588 1.313-1.313 1.313H9.564a1.312 1.312 0 01-1.313-1.313V9.564z"
																clip-rule="evenodd"
															/>
														</svg>
													</button>
												</Tooltip>
											</div>
										{/if}
									</div>
								</div>
							</div>
						</form>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
