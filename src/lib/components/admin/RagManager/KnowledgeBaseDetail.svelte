<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { config } from '$lib/stores';
	import { blobToFile } from '$lib/utils';
	import { uploadFile } from '$lib/apis/files';
	import {
		getKnowledgeById,
		addFileToKnowledgeById,
		removeFileFromKnowledgeById,
		updateKnowledgeById,
		reprocessKnowledgeById,
		resetKnowledgeById,
		type KnowledgeBase,
		type KnowledgeBaseFile,
		type AccessControlValue
	} from '$lib/apis/knowledge';

	import {
		getVectorDBCollectionInfo,
		getVectorDBCollectionPoints,
		getEmbeddingConfig,
		type CollectionInfo,
		type CollectionDetail
	} from '$lib/apis/retrieval';

	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import AccessControl from '$lib/components/workspace/common/AccessControl.svelte';
	import Files from '$lib/components/workspace/Knowledge/KnowledgeBase/Files.svelte';
	import AddTextContentModal from '$lib/components/workspace/Knowledge/KnowledgeBase/AddTextContentModal.svelte';

	// Mirrors the `KnowledgeFile` shape consumed by `Files.svelte`. `KnowledgeBaseFile`
	// differs only in nullability/optionality of a few fields, so a structural cast is
	// required to satisfy the child prop without changing runtime values.
	type FilesProp = Array<{
		id?: string;
		name?: string;
		size?: number | string;
		status?: string;
		meta?: { name?: string; size?: number | string };
		file?: { data?: { content?: string } };
		[key: string]: unknown;
	}>;

	interface Props {
		kb: KnowledgeBase;
		collections?: CollectionInfo[];
		onRefresh: () => void;
		onClose: () => void;
	}
	let { kb, collections = [], onRefresh, onClose }: Props = $props();
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let show = $state(true);
	let finalized = false;

	let knowledge = $state<KnowledgeBase | null>(null);
	let collectionInfo = $state<CollectionDetail | null>(null);
	let collectionLoading = $state(false);
	let loading = $state(true);
	let dirty = $state(false);

	// Reprocess / clear actions
	let reprocessing = $state(false);
	let showClearConfirm = $state(false);
	// Embedding-model mismatch detection (read-only)
	let activeEmbeddingModel = $state<string | null>(null);
	let storedEmbeddingModel = $state<string | null>(null);
	let embeddingMismatch = $derived(
		!!activeEmbeddingModel &&
			!!storedEmbeddingModel &&
			activeEmbeddingModel !== storedEmbeddingModel
	);

	let editName = $state('');
	let editDescription = $state('');
	let editAccessControl = $state<AccessControlValue>(null);

	let query = $state('');
	let selectedFileId = $state<string | null>(null);
	let showAddTextContentModal = $state(false);
	let inputFiles = $state<FileList | null>(null);
	let dragged = $state(false);

	let id = $derived(kb.id);

	let hasNameChange = $derived(
		knowledge && (editName !== knowledge.name || editDescription !== (knowledge.description ?? ''))
	);

	let hasAccessChange = $derived(
		knowledge && JSON.stringify(editAccessControl) !== JSON.stringify(knowledge.access_control)
	);

	let linkedCollection = $derived(collections.find((c) => c.name === id));
	let docCount = $derived(linkedCollection?.document_count ?? 0);

	let filteredItems = $derived.by(() => {
		const files = knowledge?.files ?? [];
		if (!query.trim()) return files;
		const q = query.toLowerCase();
		return files.filter((f) => {
			const name = (f?.meta?.name ?? f?.name ?? '').toString().toLowerCase();
			return name.includes(q);
		});
	});

	const createFileFromText = (name: string, content: string) => {
		const blob = new Blob([content], { type: 'text/plain' });
		return blobToFile(blob, `${name}.txt`);
	};

	const removeOptimisticItem = (tempItemId: string) => {
		if (knowledge) {
			knowledge.files = (knowledge.files ?? []).filter(
				(item: KnowledgeBaseFile) => item.itemId !== tempItemId
			);
		}
	};

	const saveNameDesc = async () => {
		if (!knowledge) return;
		if (!editName.trim()) {
			toast.error($i18n.t('Name cannot be empty'));
			return;
		}
		try {
			const updated = await updateKnowledgeById('', knowledge.id, {
				name: editName.trim(),
				description: editDescription.trim()
			});
			if (updated) {
				knowledge = updated;
				dirty = true;
				toast.success($i18n.t('Updated successfully'));
			}
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	const saveAccessControl = async () => {
		if (!knowledge) return;
		try {
			const updated = await updateKnowledgeById('', knowledge.id, {
				access_control: editAccessControl
			});
			if (updated) {
				knowledge = updated;
				dirty = true;
				toast.success($i18n.t('Access control updated'));
			}
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	const viewCollectionDetail = () => {
		show = false;
		goto(resolve(`/admin/rag?tab=collections&name=${id}`));
	};

	// Load collection stats + detect whether the stored vectors were embedded with a
	// different model than the one currently active (which would silently break retrieval).
	async function loadCollectionInfo() {
		collectionLoading = true;
		const collInfo = await getVectorDBCollectionInfo('', id).catch(() => null);
		collectionInfo = collInfo;
		collectionLoading = false;

		try {
			const [cfg, page] = await Promise.all([
				getEmbeddingConfig('').catch(() => null),
				getVectorDBCollectionPoints('', id, 1).catch(() => null)
			]);
			activeEmbeddingModel = cfg?.embedding_model ?? null;

			const raw = page?.points?.[0]?.metadata?.embedding_config;
			if (typeof raw === 'string' && raw.length > 0) {
				try {
					const parsed = JSON.parse(raw);
					storedEmbeddingModel =
						typeof parsed?.model === 'string' && parsed.model ? parsed.model : null;
				} catch {
					storedEmbeddingModel = null;
				}
			} else {
				storedEmbeddingModel = null;
			}
		} catch {
			// non-critical: mismatch detection must never break the view
		}
	}

	const reprocessHandler = async () => {
		if (!knowledge || reprocessing) return;
		reprocessing = true;
		try {
			const res = await reprocessKnowledgeById('', id);
			if (res) {
				knowledge = res as KnowledgeBase;
				dirty = true;
				if (res.warnings) {
					toast.error(`${res.warnings.message}: ${(res.warnings.errors ?? []).join('; ')}`);
				} else {
					toast.success($i18n.t('All files reprocessed successfully.'));
				}
				await loadCollectionInfo();
			}
		} catch (e) {
			toast.error(`${e}`);
		}
		reprocessing = false;
	};

	const clearHandler = async (typed: string) => {
		if (!knowledge) return;
		if ((typed ?? '').trim() !== (knowledge.name ?? '')) {
			toast.error($i18n.t('The name you typed does not match. Nothing was cleared.'));
			showClearConfirm = false;
			return;
		}
		try {
			const res = await resetKnowledgeById('', id);
			if (res) {
				knowledge = { ...(knowledge as KnowledgeBase), ...res, files: [] } as KnowledgeBase;
				dirty = true;
				toast.success($i18n.t('All documents cleared.'));
				await loadCollectionInfo();
			}
		} catch (e) {
			toast.error(`${e}`);
		}
		showClearConfirm = false;
	};

	const addFileHandler = async (fileId: string, tempItemId: string) => {
		const updatedKnowledge = await addFileToKnowledgeById('', id, fileId).catch((e) => {
			toast.error(`${e}`);
			return null;
		});

		if (updatedKnowledge) {
			knowledge = updatedKnowledge;
			dirty = true;
			toast.success($i18n.t('File added successfully.'));
		} else {
			removeOptimisticItem(tempItemId);
			toast.error($i18n.t('Failed to add file.'));
		}
	};

	const uploadFileHandler = async (file: File) => {
		if (!knowledge) return;

		if (file.size === 0) {
			toast.error($i18n.t('You cannot upload an empty file.'));
			return;
		}

		const maxSize = $config?.file?.max_size ?? null;
		if (maxSize !== null && file.size > maxSize * 1024 * 1024) {
			toast.error($i18n.t('File size should not exceed {{maxSize}} MB.', { maxSize }));
			return;
		}

		const tempItemId = uuidv4();
		const fileItem: KnowledgeBaseFile = {
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

		knowledge.files = [...(knowledge.files ?? []), fileItem];

		try {
			const uploadedFile = await uploadFile('', file).catch((e) => {
				toast.error(`${e}`);
				return null;
			});

			if (uploadedFile && knowledge) {
				knowledge.files = (knowledge.files ?? []).map((item) =>
					item.itemId === tempItemId ? { ...item, id: uploadedFile.id } : item
				);
				await addFileHandler(uploadedFile.id, tempItemId);
			} else {
				removeOptimisticItem(tempItemId);
				toast.error($i18n.t('Failed to upload file.'));
			}
		} catch (e) {
			removeOptimisticItem(tempItemId);
			toast.error(`${e}`);
		}
	};

	const deleteFileHandler = async (fileId: string) => {
		const updatedKnowledge = await removeFileFromKnowledgeById('', id, fileId).catch((e) => {
			toast.error(`${e}`);
			return null;
		});

		if (updatedKnowledge) {
			knowledge = updatedKnowledge;
			dirty = true;
			toast.success($i18n.t('File removed successfully.'));
		}
	};

	const onInputFilesChange = async () => {
		if (inputFiles && inputFiles.length > 0) {
			for (const file of Array.from(inputFiles)) {
				await uploadFileHandler(file);
			}
			inputFiles = null;
			const el = document.getElementById('kbd-files-input') as HTMLInputElement | null;
			if (el) el.value = '';
		} else {
			toast.error($i18n.t(`File not found.`));
		}
	};

	const onDragOver = (e: DragEvent) => {
		e.preventDefault();
		dragged = !!e.dataTransfer?.types?.includes('Files');
	};
	const onDragLeave = () => {
		dragged = false;
	};
	const onDrop = async (e: DragEvent) => {
		e.preventDefault();
		dragged = false;
		const files = e.dataTransfer?.files;
		if (files && files.length > 0) {
			for (const file of Array.from(files)) {
				await uploadFileHandler(file);
			}
		}
	};

	const finalize = () => {
		if (finalized) return;
		finalized = true;
		if (dirty) onRefresh();
		onClose();
	};

	$effect(() => {
		if (!show) finalize();
	});

	onMount(async () => {
		const res = await getKnowledgeById('', id).catch((e) => {
			toast.error(`${e}`);
			return null;
		});
		knowledge = res ?? ({ ...kb, files: kb.files ?? [] } as KnowledgeBase);
		editName = knowledge.name ?? '';
		editDescription = knowledge.description ?? '';
		editAccessControl = knowledge.access_control ?? null;
		loading = false;

		await loadCollectionInfo();
	});
</script>

<Modal bind:show size="lg">
	<div class="flex flex-col w-full max-h-[85vh]">
		<!-- Header with editable fields -->
		<div class="flex items-start justify-between gap-2 px-5 pt-5 pb-3">
			<div class="min-w-0 flex-1">
				<div class="flex items-center gap-2">
					<input
						class="text-lg font-medium bg-transparent border-b border-transparent hover:border-gray-300 dark:hover:border-gray-600 focus:border-blue-500 dark:focus:border-blue-400 outline-hidden transition w-full"
						type="text"
						bind:value={editName}
						placeholder={$i18n.t('Knowledge base name')}
					/>
					{#if hasNameChange}
						<button
							class="shrink-0 px-2 py-1 text-xs font-medium rounded-lg bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition"
							onclick={saveNameDesc}
						>
							{$i18n.t('Save')}
						</button>
					{/if}
				</div>
				<textarea
					class="w-full text-xs text-gray-500 dark:text-gray-400 bg-transparent border-b border-transparent hover:border-gray-300 dark:hover:border-gray-600 focus:border-blue-500 dark:focus:border-blue-400 outline-hidden transition resize-none mt-0.5"
					rows="1"
					bind:value={editDescription}
					placeholder={$i18n.t('Add description...')}
				></textarea>
				<div class="mt-2">
					<div class="px-3 py-2 bg-gray-50 dark:bg-gray-950 rounded-lg">
						<div class="flex items-center gap-2 mb-1">
							<span class="text-xs font-medium text-gray-500 dark:text-gray-400"
								>{$i18n.t('Access')}</span
							>
							{#if hasAccessChange}
								<button
									class="px-2 py-0.5 text-xs font-medium rounded bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition"
									onclick={saveAccessControl}
								>
									{$i18n.t('Save')}
								</button>
							{/if}
						</div>
						<AccessControl
							bind:accessControl={editAccessControl}
							accessRoles={['read', 'write']}
							allowPublic={true}
						/>
					</div>
				</div>
			</div>
			<button
				class="self-start p-1 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-850 transition"
				title={$i18n.t('Close')}
				onclick={() => (show = false)}
			>
				<XMark className="size-4" />
			</button>
		</div>

		<hr class="border-gray-100 dark:border-gray-850" />

		{#if embeddingMismatch}
			<div
				class="mx-5 mt-3 rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/20 px-3 py-2"
			>
				<div class="text-xs text-amber-800 dark:text-amber-300">
					{$i18n.t(
						'Embedding model changed: documents were indexed with "{{stored}}" but the active model is "{{active}}". Search results will be wrong until you reprocess.',
						{ stored: storedEmbeddingModel, active: activeEmbeddingModel }
					)}
				</div>
				<button
					class="mt-1.5 px-2.5 py-1 text-xs font-medium rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition {reprocessing
						? 'opacity-50 cursor-not-allowed'
						: ''}"
					onclick={reprocessHandler}
					disabled={reprocessing}
				>
					{reprocessing ? $i18n.t('Reprocessing...') : $i18n.t('Reprocess now')}
				</button>
			</div>
		{/if}

		<!-- Collection Info -->
		<div
			class="px-5 py-3 bg-gray-50 dark:bg-gray-850/50 border-y border-gray-100 dark:border-gray-800"
		>
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
						{$i18n.t('Collection')}
					</div>
					{#if collectionLoading}
						<Spinner className="size-3" />
					{:else if collectionInfo}
						<div class="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
							<span>{collectionInfo.points_count ?? 0} {$i18n.t('vectors')}</span>
							<span class="text-gray-300 dark:text-gray-600">·</span>
							<span>{collectionInfo.dimension ?? '—'}d</span>
							<span class="text-gray-300 dark:text-gray-600">·</span>
							<span>{docCount} {$i18n.t('docs')}</span>
							{#if collectionInfo.distance}
								<span class="text-gray-300 dark:text-gray-600">·</span>
								<span>{collectionInfo.distance}</span>
							{/if}
							<Badge type="success" content={$i18n.t('Linked')} />
						</div>
					{:else}
						<span class="text-xs text-gray-400 dark:text-gray-500"
							>{$i18n.t('No collection yet — will be created when files are added')}</span
						>
					{/if}
				</div>
				<div class="flex items-center gap-1.5">
					{#if (knowledge?.files?.length ?? 0) > 0}
						<button
							class="px-2 py-1 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition {reprocessing
								? 'opacity-50 cursor-not-allowed'
								: ''}"
							title={$i18n.t('Re-embed all files with the current embedding and chunking settings')}
							onclick={reprocessHandler}
							disabled={reprocessing}
						>
							{reprocessing ? $i18n.t('Reprocessing...') : $i18n.t('Reprocess all')}
						</button>
						<button
							class="px-2 py-1 text-xs font-medium rounded-lg text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 transition"
							onclick={() => (showClearConfirm = true)}
						>
							{$i18n.t('Clear all')}
						</button>
					{/if}
					{#if collectionInfo}
						<button
							class="px-2 py-1 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition"
							onclick={viewCollectionDetail}
						>
							{$i18n.t('View in Collections')}
						</button>
					{/if}
				</div>
			</div>
		</div>

		<!-- Toolbar -->
		<div class="flex items-center gap-2 px-5 py-3">
			<div
				class="flex items-center flex-1 px-2.5 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-100 dark:border-gray-800"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-4 h-4 text-gray-400"
				>
					<path
						fill-rule="evenodd"
						d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
						clip-rule="evenodd"
					/>
				</svg>
				<input
					class="w-full text-sm py-1.5 px-2 bg-transparent outline-hidden"
					bind:value={query}
					placeholder={$i18n.t('Search Collection')}
				/>
			</div>

			<button
				class="px-3 py-1.5 text-xs font-medium rounded-lg bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition shrink-0"
				onclick={() => document.getElementById('kbd-files-input')?.click()}
			>
				+ {$i18n.t('Upload files')}
			</button>
			<button
				class="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition shrink-0"
				onclick={() => (showAddTextContentModal = true)}
			>
				{$i18n.t('Add text content')}
			</button>
		</div>

		<!-- File list / drop zone -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="relative flex-1 overflow-y-auto px-3 pb-4 min-h-[16rem]"
			ondragover={onDragOver}
			ondragleave={onDragLeave}
			ondrop={onDrop}
		>
			{#if dragged}
				<div
					class="absolute inset-2 z-10 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600 bg-gray-50/80 dark:bg-gray-900/80 flex items-center justify-center pointer-events-none"
				>
					<div class="text-sm text-gray-500 dark:text-gray-300">
						{$i18n.t('Drop any files here to add to my documents')}
					</div>
				</div>
			{/if}

			{#if loading}
				<div class="flex justify-center py-12">
					<Spinner />
				</div>
			{:else if filteredItems.length > 0}
				<div class="text-xs text-gray-500 dark:text-gray-400 px-2 pt-1 pb-2">
					{$i18n.t('{{count}} files', { count: (knowledge?.files ?? []).length })}
				</div>
				<Files
					small
					files={filteredItems as unknown as FilesProp}
					{selectedFileId}
					onClick={(...args: unknown[]) => {
						const fileId = args[0] as string;
						selectedFileId = selectedFileId === fileId ? null : fileId;
					}}
					onDelete={(...args: unknown[]) => {
						const fileId = args[0] as string;
						selectedFileId = null;
						deleteFileHandler(fileId);
					}}
				/>
			{:else}
				<EmptyState
					title={$i18n.t('No content found')}
					description={$i18n.t(
						'Drag and drop files here or use the buttons above to add documents.'
					)}
				/>
			{/if}
		</div>
	</div>
</Modal>

<input
	id="kbd-files-input"
	bind:files={inputFiles}
	type="file"
	multiple
	hidden
	onchange={onInputFilesChange}
/>

<AddTextContentModal
	bind:show={showAddTextContentModal}
	onSubmit={(...args: unknown[]) => {
		const e = args[0] as { name: string; content: string };
		uploadFileHandler(createFileFromText(e.name, e.content));
	}}
/>

<ConfirmDialog
	bind:show={showClearConfirm}
	title={$i18n.t('Clear all documents')}
	message={$i18n.t(
		'This removes all {{count}} files from "{{name}}" and deletes its vector DB collection. The knowledge base itself is kept. This cannot be undone. Type the knowledge base name to confirm.',
		{ count: knowledge?.files?.length ?? 0, name: knowledge?.name ?? '' }
	)}
	input={true}
	inputPlaceholder={knowledge?.name ?? ''}
	confirmLabel={$i18n.t('Clear all')}
	onconfirm={clearHandler}
/>
