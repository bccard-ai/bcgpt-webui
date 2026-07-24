<script lang="ts">
	import { get } from 'svelte/store';

	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';

	import { tick, getContext, onMount, onDestroy } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { config, mobile, settings } from '$lib/stores';
	import { compressImage } from '$lib/utils';

	import Tooltip from '../common/Tooltip.svelte';
	import RichTextInput from '../common/RichTextInput.svelte';
	import VoiceRecording from '../chat/MessageInput/VoiceRecording.svelte';
	import InputMenu from './MessageInput/InputMenu.svelte';
	import { uploadFile } from '$lib/apis/files';
	import { API_BASE_URL } from '$lib/constants';
	import FileItem from '../common/FileItem.svelte';
	import Image from '../common/Image.svelte';
	import FilesOverlay from '../chat/MessageInput/FilesOverlay.svelte';

	interface FileItemType {
		type: string;
		url?: string;
		file?: unknown;
		id?: string | null;
		name?: string;
		collection_name?: string;
		status?: string;
		size?: number;
		error?: string;
		itemId?: string;
	}

	/**
	 * Channel message input component with support for rich text editing,
	 * file uploads, image capture, drag-and-drop, voice recording, and typing indicators.
	 *
	 * @example
	 * ```svelte
	 * <MessageInput
	 *   id="root"
	 *   typingUsers={[]}
	 *   onChange={() => emitTyping()}
	 *   onSubmit={(data) => sendMessage(data)}
	 *   scrollEnd={true}
	 *   scrollToBottom={() => scrollDown()}
	 * />
	 * ```
	 *
	 * @param placeholder - Placeholder text for the input field.
	 * @param transparentBackground - Whether the input has a transparent background.
	 * @param id - Identifier for the input element.
	 * @param typingUsers - Array of currently typing users.
	 * @param onSubmit - Callback with content and file data when the message is submitted.
	 * @param onChange - Callback when the input content changes (e.g., for typing indicators).
	 * @param scrollEnd - Whether the view is scrolled to the bottom.
	 * @param scrollToBottom - Callback to scroll the view to the bottom.
	 */
	interface Props {
		placeholder?: string;
		transparentBackground?: boolean;
		id?: string | null;
		typingUsers?: { name: string }[];
		onSubmit: (data: { content: string; data: { files: FileItemType[] } }) => void;
		onChange: () => void;
		scrollEnd?: boolean;
		scrollToBottom?: () => void;
	}

	let {
		placeholder = $i18n.t('Send a Message'),
		transparentBackground: _transparentBackground = false,
		id = null,
		typingUsers = [],
		onSubmit,
		onChange,
		scrollEnd = true,
		scrollToBottom = () => {}
	}: Props = $props();

	let draggedOver = $state(false);
	let recording = $state(false);
	let content = $state('');
	let files = $state([] as FileItemType[]);

	let filesInputElement = $state<HTMLInputElement>();
	let inputFiles = $state<FileList>();

	const screenCaptureHandler = async () => {
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
			const context = canvas.getContext('2d');
			context!.drawImage(video, 0, 0, canvas.width, canvas.height);
			mediaStream.getTracks().forEach((track) => track.stop());

			window.focus();

			const imageUrl = canvas.toDataURL('image/png');
			files = [...files, { type: 'image', url: imageUrl }];
			video.srcObject = null;
		} catch (_error) {
			// User cancelled screen sharing or other capture error
		}
	};

	const inputFilesHandler = async (inputFiles: File[]) => {
		inputFiles.forEach((file) => {
			if (
				(get(config)?.file?.max_size ?? null) !== null &&
				file.size > (get(config)?.file?.max_size ?? 0) * 1024 * 1024
			) {
				toast.error(
					$i18n.t(`File size should not exceed {{maxSize}} MB.`, {
						maxSize: get(config)?.file?.max_size
					})
				);
				return;
			}

			if (
				['image/gif', 'image/webp', 'image/jpeg', 'image/png', 'image/avif'].includes(file['type'])
			) {
				let reader = new FileReader();

				reader.onload = async (event) => {
					let imageUrl = event.target?.result;

					if (get(settings)?.imageCompression ?? false) {
						const width = get(settings)?.imageCompressionSize?.width ?? null;
						const height = get(settings)?.imageCompressionSize?.height ?? null;

						if (width || height) {
							imageUrl = await compressImage(imageUrl, width, height);
						}
					}

					files = [
						...files,
						{
							type: 'image',
							url: `${imageUrl}`
						}
					];
				};

				reader.readAsDataURL(file);
			} else {
				uploadFileHandler(file);
			}
		});
	};

	const uploadFileHandler = async (file: File) => {
		const tempItemId = uuidv4();
		const fileItem: FileItemType = {
			type: 'file',
			file: '',
			id: null,
			url: '',
			name: file.name,
			collection_name: '',
			status: 'uploading',
			size: file.size,
			error: '',
			itemId: tempItemId
		};

		if (fileItem.size == 0) {
			toast.error($i18n.t('You cannot upload an empty file.'));
			return;
		}

		files = [...files, fileItem];

		try {
			const uploadedFile = await uploadFile('', file);

			if (uploadedFile) {
				if (uploadedFile.error) {
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
	};

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			draggedOver = false;
		}
	};

	const onDragOver = (e: DragEvent) => {
		e.preventDefault();

		if (e.dataTransfer?.types?.includes('Files')) {
			draggedOver = true;
		} else {
			draggedOver = false;
		}
	};

	const onDragLeave = () => {
		draggedOver = false;
	};

	const onDrop = async (e: DragEvent) => {
		e.preventDefault();

		if (e.dataTransfer?.files) {
			const droppedFiles = Array.from(e.dataTransfer?.files);
			if (droppedFiles && droppedFiles.length > 0) {
				inputFilesHandler(droppedFiles);
			}
		}

		draggedOver = false;
	};

	const submitHandler = async () => {
		if (content === '' && files.length === 0) {
			return;
		}

		onSubmit({
			content,
			data: {
				files: files
			}
		});

		content = '';
		files = [];

		await tick();

		const chatInputElement = document.getElementById(`chat-input-${id}`);
		chatInputElement?.focus();
	};

	$effect(() => {
		if (content) {
			onChange();
		}
	});

	onMount(async () => {
		window.setTimeout(() => {
			const chatInput = document.getElementById(`chat-input-${id}`);
			chatInput?.focus();
		}, 0);

		window.addEventListener('keydown', handleKeyDown);
		await tick();

		const dropzoneElement = document.getElementById('channel-container');

		dropzoneElement?.addEventListener('dragover', onDragOver);
		dropzoneElement?.addEventListener('drop', onDrop);
		dropzoneElement?.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		window.removeEventListener('keydown', handleKeyDown);

		const dropzoneElement = document.getElementById('channel-container');

		if (dropzoneElement) {
			dropzoneElement?.removeEventListener('dragover', onDragOver);
			dropzoneElement?.removeEventListener('drop', onDrop);
			dropzoneElement?.removeEventListener('dragleave', onDragLeave);
		}
	});
</script>

<FilesOverlay show={draggedOver} />

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

		filesInputElement!.value = '';
	}}
/>
<div class="bg-transparent">
	<div
		class="{($settings?.widescreenMode ?? null)
			? 'max-w-full'
			: 'max-w-6xl'} px-2.5 mx-auto inset-x-0 relative"
	>
		<div class="absolute top-0 left-0 right-0 mx-auto inset-x-0 bg-transparent flex justify-center">
			<div class="flex flex-col px-3 w-full">
				<div class="relative">
					{#if scrollEnd === false}
						<div
							class=" absolute -top-12 left-0 right-0 flex justify-center z-30 pointer-events-none"
						>
							<button
								class=" bg-white border border-gray-100 dark:border-none dark:bg-white/20 p-1.5 rounded-full pointer-events-auto"
								onclick={() => {
									scrollEnd = true;
									scrollToBottom();
								}}
								aria-label={$i18n.t('Scroll to bottom')}
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

				<div class="relative">
					<div class=" -mt-5">
						{#if typingUsers.length > 0}
							<div class=" text-xs px-4 mb-1">
								<span class=" font-normal text-black dark:text-white">
									{typingUsers.map((user) => user.name).join(', ')}
								</span>
								{$i18n.t('is typing...')}
							</div>
						{/if}
					</div>
				</div>
			</div>
		</div>

		<div class="">
			{#if recording}
				<VoiceRecording
					bind:recording
					onCancel={async () => {
						recording = false;

						await tick();
						document.getElementById(`chat-input-${id}`)?.focus();
					}}
					onconfirm={async (...args: unknown[]) => {
						const e = args[0] as { detail: { text: string; filename?: string } };
						const { text, filename: _filename } = e.detail;
						content = `${content}${text} `;
						recording = false;

						await tick();
						document.getElementById(`chat-input-${id}`)?.focus();
					}}
				/>
			{:else}
				<form
					class="w-full flex gap-1.5"
					onsubmit={(e: Event) => {
						e.preventDefault();
						submitHandler();
					}}
				>
					<div
						class="flex-1 flex flex-col relative w-full rounded-3xl px-1 bg-gray-600/5 dark:bg-gray-400/5 dark:text-gray-100"
						dir={$settings?.chatDirection ?? 'LTR'}
					>
						{#if files.length > 0}
							<div class="mx-2 mt-2.5 -mb-1 flex flex-wrap gap-2">
								{#each files as file, fileIdx (fileIdx)}
									{#if file.type === 'image'}
										<div class=" relative group">
											<div class="relative">
												<Image
													src={file.url}
													alt="input"
													imageClassName=" h-16 w-16 rounded-xl object-cover"
												/>
											</div>
											<div class=" absolute -top-1 -right-1">
												<button
													class=" bg-white text-black border border-white rounded-full group-hover:visible invisible transition"
													type="button"
													onclick={() => {
														files.splice(fileIdx, 1);
														files = files;
													}}
													aria-label={$i18n.t('Remove')}
												>
													<svg
														xmlns="http://www.w3.org/2000/svg"
														viewBox="0 0 20 20"
														fill="currentColor"
														class="w-4 h-4"
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
											item={file as { file?: { data?: { content?: string } } }}
											name={file.name ?? ''}
											type={file.type}
											size={file?.size ?? 0}
											loading={file.status === 'uploading'}
											dismissible={true}
											edit={true}
											onDismiss={() => {
												files.splice(fileIdx, 1);
												files = files;
											}}
										/>
									{/if}
								{/each}
							</div>
						{/if}

						<div class="px-2.5">
							<div
								class="scrollbar-hidden font-primary text-left bg-transparent dark:text-gray-100 outline-hidden w-full pt-3 px-1 rounded-xl resize-none h-fit max-h-80 overflow-auto"
							>
								<RichTextInput
									bind:value={content}
									id={`chat-input-${id}`}
									messageInput={true}
									shiftEnter={!$mobile ||
										!(
											'ontouchstart' in window ||
											navigator.maxTouchPoints > 0 ||
											navigator.msMaxTouchPoints > 0
										)}
									{placeholder}
									largeTextAsFile={$settings?.largeTextAsFile ?? false}
									onkeydown={async (e: { detail: { event: Event } }) => {
										const event = e.detail.event as KeyboardEvent;
										if (
											!$mobile ||
											!(
												'ontouchstart' in window ||
												navigator.maxTouchPoints > 0 ||
												navigator.msMaxTouchPoints > 0
											)
										) {
											if (event.keyCode === 13 && !event.shiftKey) {
												event.preventDefault();
											}

											if (content !== '' && event.keyCode === 13 && !event.shiftKey) {
												submitHandler();
											}
										}
									}}
									onpaste={async (_e: { detail: { event: Event } }) => {
										// Paste handled by RichTextInput internally
									}}
								/>
							</div>
						</div>

						<div class=" flex justify-between mb-2.5 mt-1.5 mx-0.5">
							<div class="ml-1 self-end flex space-x-1">
								<InputMenu
									{screenCaptureHandler}
									uploadFilesHandler={() => {
										filesInputElement!.click();
									}}
								>
									<button
										class="bg-transparent hover:bg-white/80 text-gray-800 dark:text-white dark:hover:bg-gray-800 transition rounded-full p-1.5 outline-hidden focus:outline-hidden"
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
							</div>

							<div class="self-end flex space-x-1 mr-1">
								{#if content === ''}
									<Tooltip content={$i18n.t('Record voice')}>
										<button
											id="voice-input-button"
											class=" text-gray-600 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-200 transition rounded-full p-1.5 mr-0.5 self-center"
											type="button"
											onclick={async () => {
												try {
													let stream = await navigator.mediaDevices
														.getUserMedia({ audio: true })
														.catch(function (err) {
															toast.error(
																$i18n.t(`Permission denied when accessing microphone: {{error}}`, {
																	error: err
																})
															);
															return null;
														});

													if (stream) {
														recording = true;
														const tracks = stream.getTracks();
														tracks.forEach((track) => track.stop());
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

								<div class=" flex items-center">
									<div class=" flex items-center">
										<Tooltip content={$i18n.t('Send message')}>
											<button
												id="send-message-button"
												class="{content !== '' || files.length !== 0
													? 'bg-black text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100 '
													: 'text-white bg-gray-200 dark:text-gray-900 dark:bg-gray-700 disabled'} transition rounded-full p-1.5 self-center"
												type="submit"
												disabled={content === '' && files.length === 0}
												aria-label={$i18n.t('Send message')}
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
								</div>
							</div>
						</div>
					</div>
				</form>
			{/if}
		</div>
	</div>
</div>
