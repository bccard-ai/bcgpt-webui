<script lang="ts">
	import { get } from 'svelte/store';

	import Fuse from 'fuse.js';
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';

	import { onMount, getContext, onDestroy } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';
	import { showSidebar, knowledge as _knowledge, config, user } from '$lib/stores';

	import { updateFileDataContentById, uploadFile } from '$lib/apis/files';
	import {
		addFileToKnowledgeById,
		getKnowledgeById,
		getKnowledgeBases,
		removeFileFromKnowledgeById,
		resetKnowledgeById,
		updateFileFromKnowledgeById,
		updateKnowledgeById
	} from '$lib/apis/knowledge';

	import { blobToFile } from '$lib/utils';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Files from './KnowledgeBase/Files.svelte';
	import AddFilesPlaceholder from '$lib/components/AddFilesPlaceholder.svelte';

	import AddContentMenu from './KnowledgeBase/AddContentMenu.svelte';
	import AddTextContentModal from './KnowledgeBase/AddTextContentModal.svelte';

	import SyncConfirmDialog from '../../common/ConfirmDialog.svelte';
	import RichTextInput from '$lib/components/common/RichTextInput.svelte';
	import Drawer from '$lib/components/common/Drawer.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import LockClosed from '$lib/components/icons/LockClosed.svelte';
	import AccessControlModal from '../common/AccessControlModal.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	let largeScreen = $state(true);

	type PaneApi = {
		isExpanded: () => boolean;
		getSize: () => number;
		resize: (size: number) => void;
		expand: () => void;
	};
	let pane = $state<PaneApi | undefined>(undefined);
	let showSidepanel = $state(true);
	let minSize = 0;

	type FileItem = {
		id?: string | null;
		itemId?: string;
		data?: { content?: string; [key: string]: unknown };
		meta?: { name?: string; [key: string]: unknown };
		[key: string]: unknown;
	};

	type SelectedFile = FileItem & {
		data: { content?: string; [key: string]: unknown };
	};

	type KnowledgeFile = {
		id?: string;
		name?: string;
		size?: number | string;
		status?: string;
		meta?: { name?: string; size?: number | string };
		file?: { data?: { content?: string } };
		[key: string]: unknown;
	};

	type Knowledge = {
		id: string;
		name: string;
		description: string;
		data: {
			file_ids: string[];
		};
		files: FileItem[];
	};

	let id = $state<string | null>(null);
	let knowledge: Knowledge | null = $state(null);
	let query = $state('');

	let showAddTextContentModal = $state(false);
	let showSyncConfirmModal = $state(false);
	let showAccessControlModal = $state(false);

	let inputFiles = $state<FileList | null>(null);

	let selectedFile = $state<SelectedFile | null>(null);
	let selectedFileId = $state<string | null>(null);

	let fuse = $derived(
		knowledge?.files ? new Fuse(knowledge.files, { keys: ['meta.name', 'meta.description'] }) : null
	);

	let filteredItems = $derived(
		query && fuse
			? fuse.search(query).map((e: { item: FileItem }) => e.item)
			: (knowledge?.files ?? [])
	);
	let debounceTimeout = null;
	let mediaQuery;
	let resizeObserver: ResizeObserver | undefined;
	let dragged = $state(false);

	const createFileFromText = (name, content) => {
		const blob = new Blob([content], { type: 'text/plain' });
		const file = blobToFile(blob, `${name}.txt`);

		return file;
	};

	const uploadFileHandler = async (file) => {
		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: '',
			name: file.name,
			size: file.size,
			status: 'uploading',
			error: '',
			itemId: tempItemId
		};

		if (fileItem.size == 0) {
			toast.error($i18n.t('You cannot upload an empty file.'));
			return null;
		}

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

		knowledge.files = [...(knowledge.files ?? []), fileItem];

		try {
			const uploadedFile = await uploadFile('', file, { process: false }).catch((e) => {
				toast.error(`${e}`);
				return null;
			});

			if (uploadedFile) {
				knowledge.files = knowledge.files.map((item) => {
					if (item.itemId === tempItemId) {
						item.id = uploadedFile.id;
					}

					delete item.itemId;
					return item;
				});
				await addFileHandler(uploadedFile.id);
			} else {
				toast.error($i18n.t('Failed to upload file.'));
			}
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	const uploadDirectoryHandler = async () => {
		const isFileSystemAccessSupported = 'showDirectoryPicker' in window;

		try {
			if (isFileSystemAccessSupported) {
				await handleModernBrowserUpload();
			} else {
				await handleFirefoxUpload();
			}
		} catch (error) {
			handleUploadError(error);
		}
	};

	const hasHiddenFolder = (path) => {
		return path.split('/').some((part) => part.startsWith('.'));
	};

	const handleModernBrowserUpload = async () => {
		const dirHandle = await window.showDirectoryPicker();
		let totalFiles = 0;
		let uploadedFiles = 0;

		const updateProgress = () => {
			const percentage = (uploadedFiles / totalFiles) * 100;
			toast.info(
				$i18n.t('Upload Progress: {{uploaded}}/{{total}} ({{percentage}}%)', {
					uploaded: uploadedFiles,
					total: totalFiles,
					percentage: percentage.toFixed(2)
				})
			);
		};

		async function countFiles(dirHandle) {
			for await (const entry of dirHandle.values()) {
				if (entry.name.startsWith('.')) continue;

				if (entry.kind === 'file') {
					totalFiles++;
				} else if (entry.kind === 'directory') {
					if (!entry.name.startsWith('.')) {
						await countFiles(entry);
					}
				}
			}
		}

		async function processDirectory(dirHandle, path = '') {
			for await (const entry of dirHandle.values()) {
				if (entry.name.startsWith('.')) continue;

				const entryPath = path ? `${path}/${entry.name}` : entry.name;

				if (hasHiddenFolder(entryPath)) continue;

				if (entry.kind === 'file') {
					const file = await entry.getFile();
					const fileWithPath = new File([file], entryPath, { type: file.type });

					await uploadFileHandler(fileWithPath);
					uploadedFiles++;
					updateProgress();
				} else if (entry.kind === 'directory') {
					if (!entry.name.startsWith('.')) {
						await processDirectory(entry, entryPath);
					}
				}
			}
		}

		await countFiles(dirHandle);
		updateProgress();

		if (totalFiles > 0) {
			await processDirectory(dirHandle);
		}
	};

	const handleFirefoxUpload = async () => {
		return new Promise((resolve, reject) => {
			const input = document.createElement('input');
			input.type = 'file';
			input.webkitdirectory = true;
			input.directory = true;
			input.multiple = true;
			input.style.display = 'none';

			document.body.appendChild(input);

			input.onchange = async () => {
				try {
					const files = Array.from(input.files).filter(
						(file) => !hasHiddenFolder(file.webkitRelativePath)
					);

					let totalFiles = files.length;
					let uploadedFiles = 0;

					const updateProgress = () => {
						const percentage = (uploadedFiles / totalFiles) * 100;
						toast.info(
							$i18n.t('Upload Progress: {{uploaded}}/{{total}} ({{percentage}}%)', {
								uploaded: uploadedFiles,
								total: totalFiles,
								percentage: percentage.toFixed(2)
							})
						);
					};

					updateProgress();

					for (const file of files) {
						if (!file.name.startsWith('.')) {
							const relativePath = file.webkitRelativePath || file.name;
							const fileWithPath = new File([file], relativePath, { type: file.type });

							await uploadFileHandler(fileWithPath);
							uploadedFiles++;
							updateProgress();
						}
					}

					document.body.removeChild(input);
					resolve();
				} catch (error) {
					reject(error);
				}
			};

			input.onerror = (error) => {
				document.body.removeChild(input);
				reject(error);
			};

			input.click();
		});
	};

	const handleUploadError = (error) => {
		if (error.name === 'AbortError') {
			toast.info($i18n.t('Directory selection was cancelled'));
		} else {
			toast.error($i18n.t('Error accessing directory'));
		}
	};

	const syncDirectoryHandler = async () => {
		if (!id) {
			return;
		}

		if ((knowledge?.files ?? []).length > 0) {
			const res = await resetKnowledgeById('', id).catch((e) => {
				toast.error(`${e}`);
			});

			if (res) {
				knowledge = res;
				toast.success($i18n.t('Knowledge reset successfully.'));

				uploadDirectoryHandler();
			}
		} else {
			uploadDirectoryHandler();
		}
	};

	const addFileHandler = async (fileId) => {
		if (!id) {
			return;
		}

		const updatedKnowledge = await addFileToKnowledgeById('', id, fileId).catch((e) => {
			toast.error(`${e}`);
			return null;
		});

		if (updatedKnowledge) {
			knowledge = updatedKnowledge;
			toast.success($i18n.t('File added successfully.'));
		} else {
			toast.error($i18n.t('Failed to add file.'));
			knowledge.files = knowledge.files.filter((file) => file.id !== fileId);
		}
	};

	const deleteFileHandler = async (fileId) => {
		if (!id) {
			return;
		}

		try {
			const updatedKnowledge = await removeFileFromKnowledgeById('', id, fileId);

			if (updatedKnowledge) {
				knowledge = updatedKnowledge;
				toast.success($i18n.t('File removed successfully.'));
			}
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	const updateFileContentHandler = async () => {
		const fileId = selectedFile?.id;
		if (!id || !fileId) {
			return;
		}

		const content = selectedFile?.data?.content ?? '';

		const res = updateFileDataContentById('', fileId, content).catch((e) => {
			toast.error(`${e}`);
		});

		const updatedKnowledge = await updateFileFromKnowledgeById('', id, fileId).catch((e) => {
			toast.error(`${e}`);
		});

		if (res && updatedKnowledge) {
			knowledge = updatedKnowledge;
			toast.success($i18n.t('File content updated successfully.'));
		}
	};

	const changeDebounceHandler = () => {
		if (debounceTimeout) {
			clearTimeout(debounceTimeout);
		}

		debounceTimeout = setTimeout(async () => {
			if (!id) {
				return;
			}

			if (knowledge.name.trim() === '' || knowledge.description.trim() === '') {
				toast.error($i18n.t('Please fill in all fields.'));
				return;
			}

			const res = await updateKnowledgeById('', id, {
				...knowledge,
				name: knowledge.name,
				description: knowledge.description,
				access_control: knowledge.access_control
			}).catch((e) => {
				toast.error(`${e}`);
			});

			if (res) {
				toast.success($i18n.t('Knowledge updated successfully'));
				_knowledge.set(await getKnowledgeBases(''));
			}
		}, 1000);
	};

	const handleMediaQuery = async (e: MediaQueryListEvent) => {
		if (e.matches) {
			largeScreen = true;
		} else {
			largeScreen = false;
		}
	};

	const onDragOver = (e: DragEvent) => {
		e.preventDefault();

		if (e.dataTransfer?.types?.includes('Files')) {
			dragged = true;
		} else {
			dragged = false;
		}
	};

	const onDragLeave = () => {
		dragged = false;
	};

	const onDrop = async (e: DragEvent) => {
		e.preventDefault();
		dragged = false;

		if (e.dataTransfer?.types?.includes('Files')) {
			if (e.dataTransfer?.files) {
				const inputFiles = e.dataTransfer?.files;

				if (inputFiles && inputFiles.length > 0) {
					for (const file of inputFiles) {
						await uploadFileHandler(file);
					}
				} else {
					toast.error($i18n.t(`File not found.`));
				}
			}
		}
	};

	onMount(async () => {
		mediaQuery = window.matchMedia('(min-width: 1024px)');

		mediaQuery.addEventListener('change', handleMediaQuery);
		handleMediaQuery(mediaQuery);

		const container = document.getElementById('collection-container');

		minSize = !largeScreen ? 100 : Math.floor((300 / container.clientWidth) * 100);

		resizeObserver = new ResizeObserver((entries) => {
			for (let entry of entries) {
				const width = entry.contentRect.width;
				const percentage = (300 / width) * 100;
				minSize = !largeScreen ? 100 : Math.floor(percentage);

				if (showSidepanel) {
					if (pane && pane.isExpanded() && pane.getSize() < minSize) {
						pane.resize(minSize);
					}
				}
			}
		});

		resizeObserver.observe(container);

		if (pane) {
			pane.expand();
		}

		id = get(page).params.id ?? null;

		const res = id
			? await getKnowledgeById('', id).catch((e) => {
					toast.error(`${e}`);
					return null;
				})
			: null;

		if (res) {
			knowledge = res;
		} else {
			goto(resolve('/workspace/knowledge'));
		}

		const dropZone = document.querySelector('body');
		dropZone?.addEventListener('dragover', onDragOver);
		dropZone?.addEventListener('drop', onDrop);
		dropZone?.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		mediaQuery?.removeEventListener('change', handleMediaQuery);
		resizeObserver?.disconnect();
		const dropZone = document.querySelector('body');
		dropZone?.removeEventListener('dragover', onDragOver);
		dropZone?.removeEventListener('drop', onDrop);
		dropZone?.removeEventListener('dragleave', onDragLeave);
	});

	$effect(() => {
		if (selectedFileId) {
			const file = (knowledge?.files ?? []).find((file) => file.id === selectedFileId);
			if (file) {
				file.data = file.data ?? { content: '' };
				selectedFile = file as SelectedFile;
			} else {
				selectedFile = null;
			}
		} else {
			selectedFile = null;
		}
	});
</script>

{#if dragged}
	<div
		class="fixed {$showSidebar
			? 'left-0 md:left-[260px] md:w-[calc(100%-260px)]'
			: 'left-0'}  w-full h-full flex z-50 touch-none pointer-events-none"
		id="dropzone"
		role="region"
		aria-label={$i18n.t('Drag and Drop Container')}
	>
		<div class="absolute w-full h-full backdrop-blur-sm bg-gray-800/40 flex justify-center">
			<div class="m-auto pt-64 flex flex-col justify-center">
				<div class="max-w-md">
					<AddFilesPlaceholder>
						<div class=" mt-2 text-center text-sm dark:text-gray-200 w-full">
							{$i18n.t('Drop any files here to add to my documents')}
						</div>
					</AddFilesPlaceholder>
				</div>
			</div>
		</div>
	</div>
{/if}

<SyncConfirmDialog
	bind:show={showSyncConfirmModal}
	message={$i18n.t(
		'This will reset the knowledge base and sync all files. Do you wish to continue?'
	)}
	onconfirm={() => {
		syncDirectoryHandler();
	}}
/>

<AddTextContentModal
	bind:show={showAddTextContentModal}
	onSubmit={(payload: unknown) => {
		const { name, content } = payload as { name: string; content: string };
		const file = createFileFromText(name, content);
		uploadFileHandler(file);
	}}
/>

<input
	id="files-input"
	bind:files={inputFiles}
	type="file"
	multiple
	hidden
	onchange={async () => {
		if (inputFiles && inputFiles.length > 0) {
			for (const file of inputFiles) {
				await uploadFileHandler(file);
			}

			inputFiles = null;
			const fileInputElement = document.getElementById('files-input');

			if (fileInputElement) {
				fileInputElement.value = '';
			}
		} else {
			toast.error($i18n.t(`File not found.`));
		}
	}}
/>

<div class="flex flex-col w-full translate-y-1" id="collection-container">
	{#if id && knowledge}
		<AccessControlModal
			bind:show={showAccessControlModal}
			bind:accessControl={knowledge.access_control}
			allowPublic={$user?.permissions?.sharing?.public_knowledge || $user?.role === 'admin'}
			onChange={() => {
				changeDebounceHandler();
			}}
			accessRoles={['read', 'write']}
		/>
		<div class="w-full mb-2.5">
			<div class=" flex w-full">
				<div class="flex-1">
					<div class="flex items-center justify-between w-full px-0.5 mb-1">
						<div class="w-full">
							<input
								type="text"
								class="text-left w-full font-semibold text-2xl font-primary bg-transparent outline-hidden"
								bind:value={knowledge.name}
								placeholder={$i18n.t('Knowledge Name')}
								oninput={() => {
									changeDebounceHandler();
								}}
							/>
						</div>

						<div class="self-center shrink-0">
							<button
								class="bg-gray-50 hover:bg-gray-100 text-black dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-white transition px-2 py-1 rounded-full flex gap-1 items-center"
								type="button"
								onclick={() => {
									showAccessControlModal = true;
								}}
							>
								<LockClosed strokeWidth="2.5" className="size-3.5" />

								<div class="text-sm font-medium shrink-0">
									{$i18n.t('Access')}
								</div>
							</button>
						</div>
					</div>

					<div class="flex w-full px-1">
						<input
							type="text"
							class="text-left text-xs w-full text-gray-500 bg-transparent outline-hidden"
							bind:value={knowledge.description}
							placeholder={$i18n.t('Knowledge Description')}
							oninput={() => {
								changeDebounceHandler();
							}}
						/>
					</div>
				</div>
			</div>
		</div>

		<div class="flex flex-row flex-1 h-full max-h-full pb-2.5 gap-3">
			{#if largeScreen}
				<div class="flex-1 flex justify-start w-full h-full max-h-full">
					{#if selectedFile}
						<div class=" flex flex-col w-full h-full max-h-full">
							<div class="shrink-0 mb-2 flex items-center">
								{#if !showSidepanel}
									<div class="-translate-x-2">
										<button
											class="w-full text-left text-sm p-1.5 rounded-lg dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-gray-850"
											onclick={() => {
												pane?.expand();
											}}
										>
											<ChevronLeft strokeWidth="2.5" />
										</button>
									</div>
								{/if}

								<div class=" flex-1 text-xl font-medium">
									<a
										class="hover:text-gray-500 dark:hover:text-gray-100 hover:underline grow line-clamp-1"
										href={selectedFile?.id
											? resolve(`/api/v1/files/${selectedFile.id}/content` as unknown as '/')
											: '#'}
										target="_blank"
									>
										{decodeURIComponent(selectedFile?.meta?.name ?? '')}
									</a>
								</div>

								<div>
									<button
										class="self-center w-fit text-sm py-1 px-2.5 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-lg"
										onclick={() => {
											updateFileContentHandler();
										}}
									>
										{$i18n.t('Save')}
									</button>
								</div>
							</div>

							<div
								class=" flex-1 w-full h-full max-h-full text-sm bg-transparent outline-hidden overflow-y-auto scrollbar-hidden"
							>
								{#key selectedFile.id}
									<RichTextInput
										className="input-prose-sm"
										bind:value={selectedFile.data.content}
										placeholder={$i18n.t('Add content here')}
										preserveBreaks={true}
									/>
								{/key}
							</div>
						</div>
					{:else}
						<div class="h-full flex w-full">
							<div class="m-auto text-xs text-center text-gray-200 dark:text-gray-700">
								{$i18n.t('Drag and drop a file to upload or select a file to view')}
							</div>
						</div>
					{/if}
				</div>
			{:else if !largeScreen && selectedFileId !== null}
				<Drawer
					className="h-full"
					show={selectedFileId !== null}
					onClose={() => {
						selectedFileId = null;
					}}
				>
					<div class="flex flex-col justify-start h-full max-h-full p-2">
						<div class=" flex flex-col w-full h-full max-h-full">
							<div class="shrink-0 mt-1 mb-2 flex items-center">
								<div class="mr-2">
									<button
										class="w-full text-left text-sm p-1.5 rounded-lg dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-gray-850"
										onclick={() => {
											selectedFileId = null;
										}}
									>
										<ChevronLeft strokeWidth="2.5" />
									</button>
								</div>
								<div class=" flex-1 text-xl line-clamp-1">
									{selectedFile?.meta?.name}
								</div>

								<div>
									<button
										class="self-center w-fit text-sm py-1 px-2.5 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-lg"
										onclick={() => {
											updateFileContentHandler();
										}}
									>
										{$i18n.t('Save')}
									</button>
								</div>
							</div>

							<div
								class=" flex-1 w-full h-full max-h-full py-2.5 px-3.5 rounded-lg text-sm bg-transparent overflow-y-auto scrollbar-hidden"
							>
								{#if selectedFile}
									{#key selectedFile.id}
										<RichTextInput
											className="input-prose-sm"
											bind:value={selectedFile.data.content}
											placeholder={$i18n.t('Add content here')}
											preserveBreaks={true}
										/>
									{/key}
								{/if}
							</div>
						</div>
					</div>
				</Drawer>
			{/if}

			<div
				class="{largeScreen ? 'shrink-0 w-72 max-w-72' : 'flex-1'}
			flex
			py-2
			rounded-2xl
			border
			border-gray-50
			h-full
			dark:border-gray-850"
			>
				<div class=" flex flex-col w-full space-x-2 rounded-lg h-full">
					<div class="w-full h-full flex flex-col">
						<div class=" px-3">
							<div class="flex mb-0.5">
								<div class=" self-center ml-1 mr-3">
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="w-4 h-4"
									>
										<path
											fill-rule="evenodd"
											d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
											clip-rule="evenodd"
										/>
									</svg>
								</div>
								<input
									class=" w-full text-sm pr-4 py-1 rounded-r-xl outline-hidden bg-transparent"
									bind:value={query}
									placeholder={$i18n.t('Search Collection')}
									onfocus={() => {
										selectedFileId = null;
									}}
								/>

								<div>
									<AddContentMenu
										onUpload={(payload: unknown) => {
											const { type } = payload as { type?: string };
											if (type === 'directory') {
												uploadDirectoryHandler();
											} else if (type === 'text') {
												showAddTextContentModal = true;
											} else {
												document.getElementById('files-input')?.click();
											}
										}}
										onSync={() => {
											showSyncConfirmModal = true;
										}}
									/>
								</div>
							</div>
						</div>

						{#if filteredItems.length > 0}
							<div class=" flex overflow-y-auto h-full w-full scrollbar-hidden text-xs">
								<Files
									small
									files={filteredItems as KnowledgeFile[]}
									{selectedFileId}
									onClick={(fileId: unknown) => {
										const next = typeof fileId === 'string' ? fileId : null;
										selectedFileId = selectedFileId === next ? null : next;
									}}
									onDelete={(fileId: unknown) => {
										selectedFileId = null;
										if (typeof fileId === 'string') {
											deleteFileHandler(fileId);
										}
									}}
								/>
							</div>
						{:else}
							<div class="my-3 flex flex-col justify-center text-center text-gray-500 text-xs">
								<div>
									{$i18n.t('No content found')}
								</div>
							</div>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{:else}
		<Spinner />
	{/if}
</div>
