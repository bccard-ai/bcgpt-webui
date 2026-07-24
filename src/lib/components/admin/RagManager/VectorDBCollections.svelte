<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { CollectionInfo, VectorDBStatus } from '$lib/apis/retrieval';
	import type { KnowledgeBase } from '$lib/apis/knowledge';
	import { deleteVectorDBCollection, createVectorDBCollection } from '$lib/apis/retrieval';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import VectorDBCollectionDetail from './VectorDBCollectionDetail.svelte';

	interface Props {
		collections: CollectionInfo[];
		knowledgeBases: KnowledgeBase[];
		status?: VectorDBStatus | null;
		onRefresh: () => void;
	}
	let { collections, knowledgeBases, status = null, onRefresh }: Props = $props();
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let searchQuery = $state('');
	let showDeleteConfirm = $state(false);
	let deleteTarget = $state<CollectionInfo | null>(null);

	let showCreateModal = $state(false);
	let createName = $state('');
	let creating = $state(false);

	// Orphaned-collection cleanup
	let showCleanupConfirm = $state(false);

	// Deep-linkable collection detail view (?tab=collections&name=...)
	let selectedName = $state<string | null>(null);

	// The embedding model must be loaded to create a collection (the probe needs it).
	// Treat an undefined flag (older/non-admin responses) as ready so we never block wrongly.
	let embeddingReady = $derived(status?.embedding_loaded !== false);

	function openCollection(name: string) {
		selectedName = name;
		const url = new URL(page.url);
		url.searchParams.set('name', name);
		goto(resolve((url.pathname + url.search) as unknown as '/'), {
			replaceState: true,
			keepFocus: true,
			noScroll: true
		});
	}
	function closeCollection() {
		selectedName = null;
		const url = new URL(page.url);
		url.searchParams.delete('name');
		goto(resolve((url.pathname + url.search) as unknown as '/'), {
			replaceState: true,
			keepFocus: true,
			noScroll: true
		});
	}

	onMount(() => {
		const name = page.url.searchParams.get('name');
		if (name) selectedName = name;
	});

	let filteredCollections = $derived(
		searchQuery
			? collections.filter((c) => c.name.toLowerCase().includes(searchQuery.toLowerCase()))
			: collections
	);

	let totalDocs = $derived(collections.reduce((sum, c) => sum + c.document_count, 0));

	let kbMap = $derived(new Map((knowledgeBases ?? []).map((kb) => [kb.id, kb.name])));

	function getLinkedKB(collectionName: string): string | null {
		return kbMap.get(collectionName) ?? null;
	}

	// Orphans = collections not backing any knowledge base and not produced by a
	// live source (chat file uploads "file-", web search "web-search-"). These were
	// created ad-hoc here and are never queried — safe to clean up.
	let orphanCollections = $derived(
		(collections ?? []).filter(
			(c) => !kbMap.has(c.name) && !c.name.startsWith('file-') && !c.name.startsWith('web-search-')
		)
	);

	const handleDelete = async () => {
		if (!deleteTarget) return;
		try {
			await deleteVectorDBCollection('', deleteTarget.name);
			toast.success($i18n.t('Collection deleted'));
			onRefresh();
		} catch (e) {
			toast.error(`${e}`);
		}
		showDeleteConfirm = false;
		deleteTarget = null;
	};

	const handleCleanupOrphans = async (typed: string) => {
		if ((typed ?? '').trim().toUpperCase() !== 'DELETE') {
			toast.error($i18n.t('Type DELETE to confirm.'));
			return;
		}
		let deleted = 0;
		for (const c of orphanCollections) {
			try {
				await deleteVectorDBCollection('', c.name);
				deleted++;
			} catch (e) {
				toast.error(`${c.name}: ${e}`);
			}
		}
		showCleanupConfirm = false;
		if (deleted > 0) {
			toast.success($i18n.t('Deleted {{count}} orphaned collections', { count: deleted }));
			onRefresh();
		}
	};

	const handleCreate = async () => {
		if (!createName.trim()) {
			toast.error($i18n.t('Please enter a collection name.'));
			return;
		}
		if (!embeddingReady) {
			toast.error(
				$i18n.t(
					'The embedding model is not loaded. Collections cannot be created until it is fixed.'
				)
			);
			return;
		}
		creating = true;
		try {
			await createVectorDBCollection('', createName.trim());
			toast.success($i18n.t('Collection created successfully.'));
			showCreateModal = false;
			createName = '';
			onRefresh();
		} catch (e) {
			toast.error(`${e}`);
		}
		creating = false;
	};
</script>

{#if selectedName}
	<VectorDBCollectionDetail
		collectionName={selectedName}
		{knowledgeBases}
		onBack={closeCollection}
		{onRefresh}
	/>
{:else}
	<div class="space-y-4">
		<div class="flex items-center justify-between">
			<div class="text-base font-medium">{$i18n.t('Collections')}</div>
			<div class="flex gap-2">
				<button
					class="px-3 py-1.5 text-xs font-medium rounded-lg bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition"
					onclick={() => (showCreateModal = true)}
				>
					+ {$i18n.t('Create')}
				</button>
				<button
					class="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					onclick={onRefresh}
				>
					{$i18n.t('Refresh')}
				</button>
			</div>
		</div>
		<hr class="border-gray-100 dark:border-gray-850 my-2" />

		<InfoCallout
			>{$i18n.t(
				'Collections are the vector DB\'s storage units that hold your documents\' embeddings. You can create an empty collection here or one is generated automatically when you create a knowledge base or upload a file in a chat. Collections starting with "file-" come from individual chat uploads; the rest are linked to a knowledge base. Use the trash icon to delete one.'
			)}</InfoCallout
		>

		<div class="mb-3">
			<input
				class="w-full rounded-lg text-sm dark:bg-gray-850 p-2 border-1 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500"
				type="text"
				placeholder={$i18n.t('Search collections...')}
				bind:value={searchQuery}
			/>
		</div>

		<div class="text-xs text-gray-500 dark:text-gray-400">
			{$i18n.t('{{count}} collections, {{docs}} documents', {
				count: collections.length,
				docs: totalDocs.toLocaleString()
			})}
		</div>

		{#if orphanCollections.length > 0}
			<div
				class="flex items-center justify-between gap-3 rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/20 px-3 py-2"
			>
				<div class="text-xs text-amber-800 dark:text-amber-300">
					{$i18n.t(
						'{{count}} orphaned collections are not linked to any knowledge base and were not created by chat uploads. They are never searched and only consume storage.',
						{ count: orphanCollections.length }
					)}
				</div>
				<button
					class="shrink-0 px-2.5 py-1 text-xs font-medium rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition"
					onclick={() => (showCleanupConfirm = true)}
				>
					{$i18n.t('Clean up')}
				</button>
			</div>
		{/if}

		{#if filteredCollections.length > 0}
			<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-850">
						<tr>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
								{$i18n.t('Collection Name')}
							</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
								{$i18n.t('Knowledge Base')}
							</th>
							<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
								{$i18n.t('Documents')}
							</th>
							<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
								{$i18n.t('Actions')}
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
						{#each filteredCollections as collection (collection.name)}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-850/50 transition">
								<td class="px-4 py-2.5">
									<button
										class="font-medium text-left hover:text-blue-600 dark:hover:text-blue-400 hover:underline transition"
										onclick={() => openCollection(collection.name)}
									>
										{collection.name}
									</button>
								</td>
								<td class="px-4 py-2.5 text-gray-500 dark:text-gray-400">
									{#if getLinkedKB(collection.name)}
										<span class="text-blue-500 dark:text-blue-400"
											>{getLinkedKB(collection.name)}</span
										>
									{:else if collection.name.startsWith('file-')}
										<span class="text-gray-400 dark:text-gray-500"
											>{$i18n.t('Standalone file')}</span
										>
									{:else}
										<span class="text-gray-400 dark:text-gray-500">—</span>
									{/if}
								</td>
								<td class="px-4 py-2.5 text-right text-gray-500 dark:text-gray-400">
									{collection.document_count.toLocaleString()}
								</td>
								<td class="px-4 py-2.5 text-right whitespace-nowrap">
									<button
										class="p-1 rounded text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
										title={$i18n.t('View')}
										onclick={() => openCollection(collection.name)}
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
										onclick={() => {
											deleteTarget = collection;
											showDeleteConfirm = true;
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
		{:else}
			<EmptyState
				title={$i18n.t('No Collections')}
				description={$i18n.t(
					'No vector DB collections found. Create a knowledge base to get started.'
				)}
			/>
		{/if}
	</div>
{/if}

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete Collection')}
	message={$i18n.t(
		'Are you sure you want to delete collection "{{name}}"? This cannot be undone.',
		{
			name: deleteTarget?.name ?? ''
		}
	)}
	onconfirm={handleDelete}
	onCancel={() => {
		deleteTarget = null;
	}}
/>

<ConfirmDialog
	bind:show={showCleanupConfirm}
	title={$i18n.t('Clean up orphaned collections')}
	message={$i18n.t(
		'This permanently deletes {{count}} orphaned collections: {{names}}. This cannot be undone. Type DELETE to confirm.',
		{
			count: orphanCollections.length,
			names: orphanCollections.map((c) => c.name).join(', ')
		}
	)}
	input={true}
	inputPlaceholder={$i18n.t('Type DELETE to confirm')}
	confirmLabel={$i18n.t('Delete')}
	onconfirm={handleCleanupOrphans}
/>

{#if showCreateModal}
	<Modal bind:show={showCreateModal} size="sm">
		<div class="p-5 space-y-4">
			<div class="text-lg font-medium">{$i18n.t('Create Collection')}</div>

			<div>
				<div class="text-xs font-medium mb-1">{$i18n.t('Collection Name')}</div>
				<input
					class="w-full rounded-lg text-sm dark:bg-gray-850 p-2 border-1 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500"
					type="text"
					placeholder={$i18n.t('Enter collection name')}
					bind:value={createName}
				/>
			</div>

			<InfoCallout variant="warning">
				{$i18n.t(
					'An empty collection created here is not used by chat. A collection is only searched when a knowledge base exists with the exact same name. To make documents searchable, create a Knowledge Base instead — it manages its own collection automatically.'
				)}
			</InfoCallout>

			{#if !embeddingReady}
				<div
					class="rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-xs text-red-700 dark:text-red-300"
				>
					{$i18n.t(
						'The embedding model is not loaded, so a collection cannot be created. Fix the embedding model under Admin Settings > Documents first.'
					)}
				</div>
			{/if}

			<div class="flex justify-end gap-2 pt-2">
				<button
					class="px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					onclick={() => (showCreateModal = false)}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					class="px-3 py-1.5 text-sm font-medium rounded-lg bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition {creating ||
					!embeddingReady
						? 'opacity-50 cursor-not-allowed'
						: ''}"
					onclick={handleCreate}
					disabled={creating || !embeddingReady}
				>
					{$i18n.t('Create')}
				</button>
			</div>
		</div>
	</Modal>
{/if}
