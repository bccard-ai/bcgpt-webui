<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	import type { CollectionInfo } from '$lib/apis/retrieval';
	import type { KnowledgeBase, AccessControlValue } from '$lib/apis/knowledge';
	import { createNewKnowledge, deleteKnowledgeById } from '$lib/apis/knowledge';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import AccessControl from '$lib/components/workspace/common/AccessControl.svelte';
	import KnowledgeBaseDetail from './KnowledgeBaseDetail.svelte';

	interface Props {
		knowledgeBases: KnowledgeBase[];
		collections: CollectionInfo[];
		onRefresh: () => void;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		models?: any[];
	}
	let { knowledgeBases, collections, onRefresh, models = [] }: Props = $props();
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let searchQuery = $state('');
	let showDeleteConfirm = $state(false);
	let deleteTarget: KnowledgeBase | null = $state(null);

	let detailTarget: KnowledgeBase | null = $state(null);

	let showCreateModal = $state(false);
	let createName = $state('');
	let createDescription = $state('');
	let createAccessControl = $state<AccessControlValue>(null);
	let creating = $state(false);

	let collectionMap = $derived(new Map((collections ?? []).map((c) => [c.name, c])));

	let filteredKBs = $derived(
		searchQuery
			? knowledgeBases.filter((kb) => kb.name.toLowerCase().includes(searchQuery.toLowerCase()))
			: knowledgeBases
	);

	let sortedKBs = $derived(
		[...filteredKBs].sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0))
	);

	function relativeTime(timestamp: number | undefined): string {
		if (!timestamp) return '—';
		const diff = Date.now() / 1000 - timestamp;
		if (diff < 60) return $i18n.t('just now');
		if (diff < 3600) return $i18n.t('{{count}}m ago', { count: Math.floor(diff / 60) });
		if (diff < 86400) return $i18n.t('{{count}}h ago', { count: Math.floor(diff / 3600) });
		return $i18n.t('{{count}}d ago', { count: Math.floor(diff / 86400) });
	}

	function getDocCount(kbId: string): number {
		return collectionMap.get(kbId)?.document_count ?? 0;
	}

	function hasCollection(kbId: string): boolean {
		return collectionMap.has(kbId);
	}

	function fileCount(kb: KnowledgeBase): number {
		return kb.data?.file_ids?.length ?? 0;
	}

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	function attachedModels(kb: KnowledgeBase | null): any[] {
		if (!kb) return [];
		return (models ?? []).filter((m) =>
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			(m?.info?.meta?.knowledge ?? m?.meta?.knowledge ?? []).some((k: any) => k?.id === kb.id)
		);
	}

	const handleDelete = async (typed: string) => {
		if (!deleteTarget) return;
		if ((typed ?? '').trim() !== (deleteTarget?.name ?? '')) {
			toast.error($i18n.t('The name you typed does not match. Deletion cancelled.'));
			showDeleteConfirm = false;
			deleteTarget = null;
			return;
		}
		try {
			await deleteKnowledgeById('', deleteTarget.id);
			toast.success($i18n.t('Knowledge base deleted'));
			onRefresh();
		} catch (e) {
			toast.error(`${e}`);
		}
		showDeleteConfirm = false;
		deleteTarget = null;
	};

	const handleCreate = async () => {
		if (!createName.trim() || !createDescription.trim()) {
			toast.error($i18n.t('Please fill in all fields.'));
			return;
		}
		creating = true;
		try {
			await createNewKnowledge(
				'',
				createName,
				createDescription,
				createAccessControl
			);
			toast.success($i18n.t('Knowledge base created successfully.'));
			showCreateModal = false;
			createName = '';
			createDescription = '';
			createAccessControl = null;
			onRefresh();
		} catch (e) {
			toast.error(`${e}`);
		}
		creating = false;
	};
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<div class="text-base font-medium">{$i18n.t('Knowledge Bases')}</div>
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
			'Knowledge bases are groups of documents you can attach to models or reference in a chat with #. Each one is automatically stored as a vector DB collection so its contents can be searched (RAG). Click Manage on a row to add or remove its documents.'
		)}</InfoCallout
	>

	<div class="mb-3">
		<input
			class="w-full rounded-lg text-sm dark:bg-gray-850 p-2 border-1 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500"
			type="text"
			placeholder={$i18n.t('Search knowledge bases...')}
			bind:value={searchQuery}
		/>
	</div>

	<div class="text-xs text-gray-500 dark:text-gray-400">
		{#if searchQuery}
			{$i18n.t('{{filtered}} of {{total}} knowledge bases', {
				filtered: filteredKBs.length,
				total: knowledgeBases.length
			})}
		{:else}
			{$i18n.t('{{count}} knowledge bases', { count: knowledgeBases.length })}
		{/if}
	</div>

	{#if sortedKBs.length > 0}
		<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
			<table class="w-full text-sm">
				<thead class="bg-gray-50 dark:bg-gray-850">
					<tr>
						<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Name')}
						</th>
						<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Collection')}
						</th>
						<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Files')}
						</th>
						<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Access')}
						</th>
						<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Last Updated')}
						</th>
						<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Actions')}
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
					{#each sortedKBs as kb (kb.id)}
						<tr class="hover:bg-gray-50 dark:hover:bg-gray-850/50 transition">
							<td class="px-4 py-2.5">
								<button
									class="font-medium truncate max-w-[200px] text-left hover:underline"
									title={$i18n.t('Manage')}
									onclick={() => (detailTarget = kb)}>{kb.name}</button
								>
								{#if kb.description}
									<div
										class="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px] mt-0.5"
									>
										{kb.description}
									</div>
								{/if}
							</td>
							<td class="px-4 py-2.5">
								{#if hasCollection(kb.id)}
									{#if getDocCount(kb.id) === 0 && fileCount(kb) > 0}
										<Badge type="warning" content={$i18n.t('Needs indexing')} />
									{:else}
										<span class="text-xs">
											<Badge type="success" content={$i18n.t('Synced')} />
											<span class="text-gray-400 dark:text-gray-500 ml-1"
												>· {getDocCount(kb.id)} {$i18n.t('docs')}</span
											>
										</span>
									{/if}
								{:else}
									<Badge type="warning" content={$i18n.t('No collection')} />
								{/if}
							</td>
							<td class="px-4 py-2.5 text-gray-500 dark:text-gray-400">
								{kb.data?.file_ids?.length ?? 0}
							</td>
							<td class="px-4 py-2.5">
								{#if kb.access_control === null}
									<Badge type="success" content={$i18n.t('Public')} />
								{:else if typeof kb.access_control === 'object' && Object.keys(kb.access_control).length === 0}
									<Badge type="muted" content={$i18n.t('Private')} />
								{:else}
									<Badge type="info" content={$i18n.t('Restricted')} />
								{/if}
							</td>
							<td class="px-4 py-2.5 text-gray-500 dark:text-gray-400 text-xs">
								{relativeTime(kb.updated_at)}
							</td>
							<td class="px-4 py-2.5 text-right">
								<div class="flex items-center justify-end gap-1">
									<button
										class="px-2 py-1 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition"
										onclick={() => (detailTarget = kb)}
									>
										{$i18n.t('Manage')}
									</button>
									<button
										class="p-1 rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition"
										title={$i18n.t('Delete')}
										onclick={() => {
											deleteTarget = kb;
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
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<EmptyState
			title={$i18n.t('No Knowledge Bases')}
			description={$i18n.t('Create a knowledge base to register documents in the vector DB.')}
		/>
	{/if}
</div>

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete Knowledge Base')}
	input={true}
	inputPlaceholder={deleteTarget?.name ?? ''}
	confirmLabel={$i18n.t('Delete')}
	message={`${$i18n.t(
		'Are you sure you want to delete "{{name}}"? This will also remove its vector DB collection.',
		{ name: deleteTarget?.name ?? '' }
	)}${
		attachedModels(deleteTarget).length > 0
			? ' ' +
				$i18n.t(
					'This knowledge base is attached to {{count}} model(s): {{names}}. They will lose access.',
					{
						count: attachedModels(deleteTarget).length,
						names: attachedModels(deleteTarget)
							.map((m) => m?.name)
							.join(', ')
					}
				)
			: ''
	} ${$i18n.t('Type the knowledge base name to confirm.')}`}
	onconfirm={handleDelete}
	onCancel={() => {
		deleteTarget = null;
	}}
/>

{#if detailTarget}
	<KnowledgeBaseDetail
		kb={detailTarget}
		{collections}
		{onRefresh}
		onClose={() => {
			detailTarget = null;
		}}
	/>
{/if}

{#if showCreateModal}
	<Modal bind:show={showCreateModal} size="sm">
		<div class="p-5 space-y-4">
			<div class="text-lg font-medium">{$i18n.t('Create Knowledge Base')}</div>

			<div>
				<div class="text-xs font-medium mb-1">{$i18n.t('Name')}</div>
				<input
					class="w-full rounded-lg text-sm dark:bg-gray-850 p-2 border-1 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500"
					type="text"
					placeholder={$i18n.t('Name your knowledge base')}
					bind:value={createName}
				/>
			</div>

			<div>
				<div class="text-xs font-medium mb-1">{$i18n.t('Description')}</div>
				<textarea
					class="w-full resize-none rounded-lg text-sm dark:bg-gray-850 p-2 border-1 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500"
					rows="3"
					placeholder={$i18n.t('Describe your knowledge base')}
					bind:value={createDescription}
				></textarea>
			</div>

			<div class="px-3 py-2 bg-gray-50 dark:bg-gray-950 rounded-lg">
				<AccessControl
					bind:accessControl={createAccessControl}
					accessRoles={['read', 'write']}
					allowPublic={true}
				/>
			</div>

			<InfoCallout>
				{$i18n.t(
					"A vector DB collection is created automatically the first time you add a file. A knowledge base manages its own collection — you don't choose or link an existing one."
				)}
			</InfoCallout>

			<div class="flex justify-end gap-2 pt-2">
				<button
					class="px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-850 hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					onclick={() => (showCreateModal = false)}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					class="px-3 py-1.5 text-sm font-medium rounded-lg bg-black dark:bg-white text-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 transition {creating
						? 'opacity-50 cursor-not-allowed'
						: ''}"
					onclick={handleCreate}
					disabled={creating}
				>
					{$i18n.t('Create')}
				</button>
			</div>
		</div>
	</Modal>
{/if}
