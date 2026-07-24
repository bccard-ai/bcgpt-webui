<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { config } from '$lib/stores';
	import { blobToFile, copyToClipboard } from '$lib/utils';
	import { uploadFile } from '$lib/apis/files';
	import {
		getKnowledgeById,
		addFileToKnowledgeById,
		removeFileFromKnowledgeById,
		type KnowledgeBase,
		type KnowledgeBaseFile
	} from '$lib/apis/knowledge';

	import {
		getVectorDBCollectionInfo,
		getVectorDBCollectionPoints,
		searchVectorDBCollection,
		deleteVectorDBCollectionPoint,
		getEmbeddingConfig,
		processFile,
		deleteVectorDBCollection,
		type CollectionDetail,
		type CollectionPoint
	} from '$lib/apis/retrieval';

	import Modal from '$lib/components/common/Modal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Files from '$lib/components/workspace/Knowledge/KnowledgeBase/Files.svelte';
	import AddTextContentModal from '$lib/components/workspace/Knowledge/KnowledgeBase/AddTextContentModal.svelte';

	interface Props {
		collectionName: string;
		knowledgeBases: KnowledgeBase[];
		onBack: () => void;
		onRefresh: () => void;
	}
	let { collectionName, knowledgeBases, onBack, onRefresh }: Props = $props();
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const PER_PAGE = 25;

	let loaded = $state(false);
	let loading = $state(false);
	let info = $state<CollectionDetail | null>(null);

	// Browse (cursor pagination)
	let points = $state<CollectionPoint[]>([]);
	let pageOffsets = $state<(string | null)[]>([null]);
	let pageIndex = $state(0);
	let nextOffset = $state<string | null>(null);

	// Search
	let mode = $state<'browse' | 'search'>('browse');
	let searchQuery = $state('');
	let searching = $state(false);
	let searchResults = $state<CollectionPoint[]>([]);

	// Point detail modal
	let selectedPoint = $state<CollectionPoint | null>(null);
	let showPointModal = $state(false);

	// Delete
	let deleteTarget = $state<CollectionPoint | null>(null);
	let showDeleteConfirm = $state(false);

	// File upload state (only used when linkedKB is set)
	let knowledge = $state<KnowledgeBase | null>(null);
	let inputFiles = $state<FileList | null>(null);
	let dragged = $state(false);
	let showAddTextContentModal = $state(false);
	let selectedFileId = $state<string | null>(null);

	// Embedding model provenance (read-only mismatch detection)
	let activeEmbeddingModel = $state<string | null>(null);
	let storedEmbeddingModel = $state<string | null>(null);
	let embeddingMismatch = $derived(
		!!activeEmbeddingModel &&
			!!storedEmbeddingModel &&
			activeEmbeddingModel !== storedEmbeddingModel
	);

	let kbMap = $derived(new Map((knowledgeBases ?? []).map((kb) => [kb.id, kb.name])));
	let linkedKB = $derived(kbMap.get(collectionName) ?? null);
	let displayPoints = $derived(mode === 'search' ? searchResults : points);
	let rangeFrom = $derived(pageIndex * PER_PAGE + 1);
	let rangeTo = $derived(pageIndex * PER_PAGE + points.length);

	function metaSource(p: CollectionPoint): string {
		const m = (p.metadata ?? {}) as Record<string, unknown>;
		return (m.name as string) || (m.source as string) || (m.file_id as string) || '—';
	}
	function metaPage(p: CollectionPoint): string | null {
		const m = (p.metadata ?? {}) as Record<string, unknown>;
		const page = m.page ?? m.page_number ?? null;
		return page === null || page === undefined ? null : `${page}`;
	}
	function preview(text: string, n = 160): string {
		if (!text) return '';
		return text.length > n ? `${text.slice(0, n)}…` : text;
	}
	function fmtScore(score?: number | null): string {
		return score === null || score === undefined ? '' : score.toFixed(3);
	}

	async function copy(text: string) {
		const ok = await copyToClipboard(text);
		if (ok) toast.success($i18n.t('Copied to clipboard'));
	}

	async function loadInfo() {
		try {
			info = await getVectorDBCollectionInfo('', collectionName);
		} catch (e) {
			toast.error(`${$i18n.t('Failed to load collection data')}: ${e}`);
		}
	}

	async function loadPage(idx: number) {
		loading = true;
		try {
			const offset = pageOffsets[idx] ?? null;
			const page = await getVectorDBCollectionPoints('', collectionName, PER_PAGE, offset);
			points = page?.points ?? [];
			nextOffset = page?.next_offset ?? null;
			pageIndex = idx;
			if (nextOffset && pageOffsets[idx + 1] === undefined) {
				pageOffsets[idx + 1] = nextOffset;
			}
		} catch (e) {
			toast.error(`${$i18n.t('Failed to load collection data')}: ${e}`);
		} finally {
			loading = false;
		}
	}

	function nextPage() {
		if (nextOffset && !loading) loadPage(pageIndex + 1);
	}
	function prevPage() {
		if (pageIndex > 0 && !loading) loadPage(pageIndex - 1);
	}

	async function runSearch() {
		const q = searchQuery.trim();
		if (!q) {
			clearSearch();
			return;
		}
		searching = true;
		try {
			const res = await searchVectorDBCollection('', collectionName, q, 30);
			searchResults = res?.points ?? [];
			mode = 'search';
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			searching = false;
		}
	}
	function clearSearch() {
		mode = 'browse';
		searchQuery = '';
		searchResults = [];
	}

	function openPoint(p: CollectionPoint) {
		selectedPoint = p;
		showPointModal = true;
	}
	function askDelete(p: CollectionPoint) {
		deleteTarget = p;
		showDeleteConfirm = true;
	}

	async function handleDeletePoint() {
		if (!deleteTarget) return;

		try {
			await deleteVectorDBCollectionPoint('', collectionName, deleteTarget.id);
			toast.success($i18n.t('Point deleted'));
			showPointModal = false;
			selectedPoint = null;
			await loadInfo();
			if (mode === 'search') {
				await runSearch();
			} else {
				// reset pagination — counts/cursors may have shifted
				pageOffsets = [null];
				await loadPage(0);
			}
			onRefresh?.();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			showDeleteConfirm = false;
			deleteTarget = null;
		}
	}

	function readStoredEmbeddingModel(): string | null {
		const raw = (points[0]?.metadata as Record<string, unknown> | undefined)?.embedding_config;
		if (typeof raw !== 'string' || raw.length === 0) return null;
		try {
			const parsed = JSON.parse(raw) as { engine?: string; model?: string };
			return typeof parsed?.model === 'string' && parsed.model.length > 0 ? parsed.model : null;
		} catch {
			return null;
		}
	}

	// --- File upload handlers (same pattern as KnowledgeBaseDetail.svelte) ---

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

	const addFileHandler = async (fileId: string, tempItemId: string) => {
		const updatedKnowledge = await addFileToKnowledgeById('', collectionName, fileId).catch((e) => {
			toast.error(`${e}`);
			return null;
		});

		if (updatedKnowledge) {
			knowledge = updatedKnowledge;
			toast.success($i18n.t('File added successfully.'));
			// Refresh collection stats + points
			await loadInfo();
			pageOffsets = [null];
			await loadPage(0);
			onRefresh?.();
		} else {
			removeOptimisticItem(tempItemId);
			toast.error($i18n.t('Failed to add file.'));
		}
	};

	const uploadFileHandler = async (file: File) => {
		if (file.size === 0) {
			toast.error($i18n.t('You cannot upload an empty file.'));
			return;
		}

		const maxSize = $config?.file?.max_size ?? null;
		if (maxSize !== null && file.size > maxSize * 1024 * 1024) {
			toast.error($i18n.t('File size should not exceed {{maxSize}} MB.', { maxSize }));
			return;
		}

		// Optimistic UI for linked KBs (has file list)
		let tempItemId: string | null = null;
		if (linkedKB && knowledge) {
			tempItemId = uuidv4();
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
		}

		try {
			const uploadedFile = await uploadFile('', file).catch((e) => {
				toast.error(`${e}`);
				return null;
			});

			if (!uploadedFile) {
				if (tempItemId) removeOptimisticItem(tempItemId);
				toast.error($i18n.t('Failed to upload file.'));
				return;
			}

			if (linkedKB) {
				// KB flow: use addFileToKnowledgeById (existing behavior)
				if (knowledge) {
					knowledge.files = (knowledge.files ?? []).map((item) =>
						item.itemId === tempItemId ? { ...item, id: uploadedFile.id } : item
					);
				}
				await addFileHandler(uploadedFile.id, tempItemId ?? '');
			} else {
				// Direct flow: use processFile to embed directly into collection
				const result = await processFile('', uploadedFile.id, collectionName).catch((e) => {
					toast.error(`${e}`);
					return null;
				});

				if (result) {
					// Clean up the auto-created file-{id} collection
					await deleteVectorDBCollection('', `file-${uploadedFile.id}`).catch(() => {});

					toast.success($i18n.t('File added successfully.'));
					// Refresh collection stats + points
					await loadInfo();
					pageOffsets = [null];
					await loadPage(0);
					onRefresh?.();
				} else {
					toast.error($i18n.t('Failed to process file.'));
				}
			}
		} catch (e) {
			if (tempItemId) removeOptimisticItem(tempItemId);
			toast.error(`${e}`);
		}
	};

	const deleteFileHandler = async (fileId: string) => {
		if (!linkedKB) return; // Only for KB-linked collections

		const updatedKnowledge = await removeFileFromKnowledgeById('', collectionName, fileId).catch(
			(e) => {
				toast.error(`${e}`);
				return null;
			}
		);

		if (updatedKnowledge) {
			knowledge = updatedKnowledge;
			toast.success($i18n.t('File removed successfully.'));
			// Refresh collection stats + points
			await loadInfo();
			pageOffsets = [null];
			await loadPage(0);
			onRefresh?.();
		}
	};

	const onInputFilesChange = async () => {
		if (inputFiles && inputFiles.length > 0) {
			for (const file of Array.from(inputFiles)) {
				await uploadFileHandler(file);
			}
			inputFiles = null;
			const el = document.getElementById('vecdb-files-input') as HTMLInputElement | null;
			if (el) el.value = '';
		} else {
			toast.error($i18n.t('File not found.'));
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

	onMount(async () => {
		await Promise.all([loadInfo(), loadPage(0)]);
		try {
			const cfg = await getEmbeddingConfig('');
			activeEmbeddingModel = cfg?.embedding_model ?? null;
		} catch {
			activeEmbeddingModel = null;
		}
		storedEmbeddingModel = readStoredEmbeddingModel();
		loaded = true;

		// Load linked knowledge base files for upload management
		if (linkedKB) {
			const kbData = await getKnowledgeById('', collectionName).catch(() => null);
			knowledge = kbData ?? null;
		}
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="relative space-y-4" ondragover={onDragOver} ondragleave={onDragLeave} ondrop={onDrop}>
	{#if dragged}
		<div
			class="absolute inset-2 z-10 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600 bg-gray-50/80 dark:bg-gray-900/80 flex items-center justify-center pointer-events-none"
		>
			<div class="text-sm text-gray-500 dark:text-gray-300">
				{$i18n.t('Drop any files here to add to this collection')}
			</div>
		</div>
	{/if}

	<!-- Header -->
	<div class="flex items-center justify-between gap-2">
		<div class="flex items-center gap-2 min-w-0">
			<button
				class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition shrink-0"
				title={$i18n.t('Back to Collections')}
				onclick={onBack}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="size-5"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					stroke-width="2"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
				</svg>
			</button>
			<div class="min-w-0">
				<div class="flex items-center gap-1.5">
					<span class="text-base font-medium truncate" title={collectionName}>{collectionName}</span
					>
					<button
						class="p-1 rounded text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition shrink-0"
						title={$i18n.t('Copy')}
						onclick={() => copy(collectionName)}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="size-3.5"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
							stroke-width="2"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
							/>
						</svg>
					</button>
				</div>
				{#if linkedKB}
					<div class="text-xs text-blue-500 dark:text-blue-400">{linkedKB}</div>
				{:else if collectionName.startsWith('file-')}
					<div class="text-xs text-gray-400 dark:text-gray-500">{$i18n.t('Standalone file')}</div>
				{/if}
			</div>
		</div>
	</div>
	<hr class="border-gray-100 dark:border-gray-850" />

	<!-- Embedding model mismatch warning -->
	{#if embeddingMismatch}
		<div
			class="rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300"
		>
			{$i18n.t(
				'Embedding model mismatch: these points were embedded with "{{stored}}", but the active model is "{{active}}". Reindex the linked knowledge base to fix retrieval.',
				{ stored: storedEmbeddingModel, active: activeEmbeddingModel }
			)}
			{#if linkedKB}
				{$i18n.t('Reindexing is available from the linked knowledge base detail page.')}
			{/if}
		</div>
	{/if}

	<!-- Stats -->
	<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
		<div class="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
			<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Points')}</div>
			<div class="text-lg font-medium">
				{info?.points_count?.toLocaleString() ?? '—'}
			</div>
		</div>
		<div class="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
			<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Dimension')}</div>
			<div class="text-lg font-medium">{info?.dimension ?? '—'}</div>
		</div>
		<div class="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
			<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Distance')}</div>
			<div class="text-lg font-medium">{info?.distance ?? '—'}</div>
		</div>
		<div class="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
			<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Status')}</div>
			<div class="text-lg font-medium capitalize">{info?.status ?? '—'}</div>
		</div>
	</div>

	<!-- Search toolbar -->
	<div class="flex gap-2">
		<input
			class="w-full rounded-lg text-sm dark:bg-gray-850 p-2 border-1 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500"
			type="text"
			placeholder={$i18n.t('Semantic search within this collection...')}
			bind:value={searchQuery}
			onkeydown={(e) => e.key === 'Enter' && runSearch()}
		/>
		<button
			class="px-3 py-1.5 text-xs font-medium rounded-lg bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition whitespace-nowrap {searching
				? 'opacity-50 cursor-not-allowed'
				: ''}"
			onclick={runSearch}
			disabled={searching}
		>
			{$i18n.t('Search')}
		</button>
		{#if mode === 'search'}
			<button
				class="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition whitespace-nowrap"
				onclick={clearSearch}
			>
				{$i18n.t('Clear')}
			</button>
		{/if}
	</div>

	<!-- File upload section -->
	{#if !collectionName.startsWith('file-')}
		<div class="flex gap-2">
			<button
				class="px-3 py-1.5 text-xs font-medium rounded-lg bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition shrink-0"
				onclick={() => document.getElementById('vecdb-files-input')?.click()}
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
	{/if}

	{#if mode === 'search'}
		<div class="text-xs text-gray-500 dark:text-gray-400">
			{$i18n.t('{{count}} results for "{{query}}"', {
				count: searchResults.length,
				query: searchQuery
			})}
		</div>
	{/if}

	<!-- Content -->
	{#if !loaded || (loading && mode === 'browse')}
		<div class="py-12"><Spinner className="size-6" /></div>
	{:else if displayPoints.length > 0}
		<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
			<table class="w-full text-sm">
				<thead class="bg-gray-50 dark:bg-gray-850">
					<tr>
						<th
							class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 w-10"
							>#</th
						>
						<th class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Source')}
						</th>
						<th
							class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 w-14"
						>
							{$i18n.t('Page')}
						</th>
						<th class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Content')}
						</th>
						{#if mode === 'search'}
							<th
								class="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 w-16"
							>
								{$i18n.t('Score')}
							</th>
						{/if}
						<th
							class="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 w-20"
						>
							{$i18n.t('Actions')}
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
					{#each displayPoints as point, idx (point.id)}
						<tr
							class="hover:bg-gray-50 dark:hover:bg-gray-850/50 transition cursor-pointer"
							onclick={() => openPoint(point)}
						>
							<td class="px-3 py-2.5 text-gray-400 dark:text-gray-500 tabular-nums">
								{mode === 'search' ? idx + 1 : rangeFrom + idx}
							</td>
							<td class="px-3 py-2.5 text-gray-600 dark:text-gray-300 truncate max-w-[10rem]">
								{metaSource(point)}
							</td>
							<td class="px-3 py-2.5 text-gray-500 dark:text-gray-400 tabular-nums">
								{metaPage(point) ?? '—'}
							</td>
							<td class="px-3 py-2.5 text-gray-700 dark:text-gray-200">
								<span class="line-clamp-2">{preview(point.text)}</span>
							</td>
							{#if mode === 'search'}
								<td class="px-3 py-2.5 text-right text-gray-500 dark:text-gray-400 tabular-nums">
									{fmtScore(point.score)}
								</td>
							{/if}
							<td class="px-3 py-2.5 text-right whitespace-nowrap">
								<button
									class="p-1 rounded text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
									title={$i18n.t('View')}
									onclick={(e) => {
										e.stopPropagation();
										openPoint(point);
									}}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-4"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
										/>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
										/>
									</svg>
								</button>
								<button
									class="p-1 rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition"
									title={$i18n.t('Delete')}
									onclick={(e) => {
										e.stopPropagation();
										askDelete(point);
									}}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-4"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
										/>
									</svg>
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else if mode === 'search'}
		<EmptyState
			title={$i18n.t('No results')}
			description={$i18n.t('No points matched your search.')}
		/>
	{:else if pageIndex === 0}
		<EmptyState
			title={$i18n.t('No data')}
			description={$i18n.t(
				'This collection has no points yet. Upload a file or add it to a knowledge base.'
			)}
		/>
	{:else}
		<div class="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('No more points.')}
		</div>
	{/if}

	<!-- Pagination (browse mode) -->
	{#if loaded && mode === 'browse' && !loading && (points.length > 0 || pageIndex > 0)}
		<div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
			<div>
				{$i18n.t('Showing {{from}}–{{to}} of {{total}}', {
					from: points.length ? rangeFrom : 0,
					to: rangeTo,
					total: info?.points_count?.toLocaleString() ?? '?'
				})}
			</div>
			<div class="flex gap-2">
				<button
					class="px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition {pageIndex ===
						0 || loading
						? 'opacity-40 cursor-not-allowed'
						: ''}"
					onclick={prevPage}
					disabled={pageIndex === 0 || loading}
				>
					{$i18n.t('Previous')}
				</button>
				<button
					class="px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition {!nextOffset ||
					loading
						? 'opacity-40 cursor-not-allowed'
						: ''}"
					onclick={nextPage}
					disabled={!nextOffset || loading}
				>
					{$i18n.t('Next')}
				</button>
			</div>
		</div>
	{/if}

	<!-- File list (linked KB only) -->
	{#if linkedKB && knowledge}
		<hr class="border-gray-100 dark:border-gray-850" />
		<div class="flex items-center justify-between">
			<div class="text-sm font-medium">{$i18n.t('Files')}</div>
			<div class="text-xs text-gray-500 dark:text-gray-400">
				{$i18n.t('{{count}} files', { count: (knowledge?.files ?? []).length })}
			</div>
		</div>
		{#if (knowledge?.files ?? []).length > 0}
			<Files
				small
				files={(knowledge?.files ?? []) as unknown as {
					id?: string;
					name?: string;
					size?: number | string;
					status?: string;
					meta?: { name?: string; size?: number | string };
					file?: { data?: { content?: string } };
					[key: string]: unknown;
				}[]}
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
				title={$i18n.t('No files')}
				description={$i18n.t('Upload files to add documents to this collection.')}
			/>
		{/if}
	{/if}
</div>
{#if showPointModal && selectedPoint}
	<Modal bind:show={showPointModal} size="lg">
		<div class="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
			<div class="flex items-center justify-between">
				<div class="text-lg font-medium">{$i18n.t('Point Detail')}</div>
				<button
					class="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
					onclick={() => (showPointModal = false)}
					aria-label={$i18n.t('Close')}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="size-5"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<div>
				<div class="flex items-center justify-between mb-1">
					<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
						{$i18n.t('Point ID')}
					</div>
					<button
						class="text-xs text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
						onclick={() => copy(selectedPoint?.id ?? '')}>{$i18n.t('Copy')}</button
					>
				</div>
				<div class="text-xs font-mono break-all text-gray-600 dark:text-gray-300">
					{selectedPoint.id}
				</div>
			</div>

			<div>
				<div class="flex items-center justify-between mb-1">
					<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
						{$i18n.t('Content')}
					</div>
					<button
						class="text-xs text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
						onclick={() => copy(selectedPoint?.text ?? '')}>{$i18n.t('Copy')}</button
					>
				</div>
				<div
					class="text-sm whitespace-pre-wrap rounded-lg bg-gray-50 dark:bg-gray-850 p-3 max-h-64 overflow-y-auto"
				>
					{selectedPoint.text}
				</div>
			</div>

			<div>
				<div class="flex items-center justify-between mb-1">
					<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
						{$i18n.t('Metadata')}
					</div>
					<button
						class="text-xs text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
						onclick={() => copy(JSON.stringify(selectedPoint?.metadata ?? {}, null, 2))}
						>{$i18n.t('Copy')}</button
					>
				</div>
				<pre
					class="text-xs font-mono rounded-lg bg-gray-50 dark:bg-gray-850 p-3 max-h-64 overflow-auto">{JSON.stringify(
						selectedPoint.metadata ?? {},
						null,
						2
					)}</pre>
			</div>

			<div class="flex justify-end gap-2 pt-2">
				<button
					class="px-3 py-1.5 text-sm font-medium rounded-lg text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 transition"
					onclick={() => selectedPoint && askDelete(selectedPoint)}
				>
					{$i18n.t('Delete')}
				</button>
				<button
					class="px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					onclick={() => (showPointModal = false)}
				>
					{$i18n.t('Close')}
				</button>
			</div>
		</div>
	</Modal>
{/if}

<input
	id="vecdb-files-input"
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
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete Point')}
	message={$i18n.t('Are you sure you want to delete this point? This cannot be undone.')}
	onconfirm={handleDeletePoint}
	onCancel={() => {
		deleteTarget = null;
	}}
/>
