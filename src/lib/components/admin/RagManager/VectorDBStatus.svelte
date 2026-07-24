<script lang="ts">
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	import type { VectorDBStatus } from '$lib/apis/retrieval';
	import { resolve } from '$app/paths';
	import Badge from '$lib/components/common/Badge.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';

	interface Props {
		status: VectorDBStatus | null;
	}
	let { status }: Props = $props();
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let totalDocs = $derived(status?.collections?.reduce((sum, c) => sum + c.document_count, 0) ?? 0);
	let totalVectors = $derived(
		status?.total_vectors ??
			status?.collections?.reduce((sum, c) => sum + (c.vector_count ?? 0), 0) ??
			0
	);

	function engineLabel(engine?: string): string {
		if (!engine) return 'Local (Sentence-Transformers)';
		if (engine === 'openai') return 'OpenAI';
		if (engine === 'ollama') return 'Ollama';
		return engine;
	}

	function engineBadgeType(engine?: string): 'success' | 'warning' | 'info' {
		if (!engine) return 'warning';
		return 'success';
	}

	function clusterBadgeType(status?: string | null): 'success' | 'warning' | 'error' {
		if (!status) return 'warning';
		const s = status.toLowerCase();
		if (s === 'green' || s === 'ok' || s === 'enabled') return 'success';
		if (s === 'yellow') return 'warning';
		return 'error';
	}
</script>

<div class="space-y-5">
	<div class="text-base font-medium">{$i18n.t('Vector DB Status')}</div>
	<hr class="border-gray-100 dark:border-gray-850 my-2" />

	<InfoCallout
		>{$i18n.t(
			'Overview of the vector database that powers retrieval-augmented generation (RAG): the configured backend, its connection state, embedding model, and how much data is stored.'
		)}</InfoCallout
	>

	{#if status}
		{#if status.embedding_loaded === false}
			<!-- Embedding-not-loaded warning -->
			<div
				class="rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-800 dark:text-red-200"
			>
				<div class="font-medium">
					{$i18n.t(
						'The embedding model is not loaded. Creating collections, indexing files, and search will fail until it is fixed.'
					)}
				</div>
				<div class="mt-1.5 text-red-700 dark:text-red-300">
					{$i18n.t('Check the embedding model under')}
					<a
						href={resolve('/admin/settings?tab=documents')}
						class="font-medium underline underline-offset-2 hover:text-red-900 dark:hover:text-red-100"
					>
						{$i18n.t('Document & Embedding Settings')}
					</a>.
				</div>
			</div>
		{/if}

		<!-- Embedding Model Section -->
		<div>
			<div class="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
				{$i18n.t('Embedding Model')}
			</div>
			<div
				class="p-4 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700"
			>
				<div class="flex items-center gap-3 mb-2">
					<Badge
						type={engineBadgeType(status.embedding_engine)}
						content={engineLabel(status.embedding_engine)}
					/>
					{#if status.embedding_model}
						<span class="text-sm font-medium">{status.embedding_model}</span>
					{:else}
						<span class="text-sm text-gray-400 dark:text-gray-500">{$i18n.t('Not configured')}</span
						>
					{/if}
				</div>
			</div>
		</div>

		<!-- Status Grid -->
		<div>
			<div class="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
				{$i18n.t('Vector Database')}
			</div>
			<div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
				<div
					class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">{$i18n.t('Backend')}</div>
					<div class="text-lg font-semibold">{status.backend}</div>
				</div>
				<div
					class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">{$i18n.t('Connection')}</div>
					<div class="mt-1">
						<Badge
							type={status.connected ? 'success' : 'error'}
							content={status.connected ? $i18n.t('Connected') : $i18n.t('Disconnected')}
						/>
					</div>
				</div>
				<div
					class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">
						{$i18n.t('Cluster Status')}
					</div>
					<div class="mt-1">
						{#if status.cluster_status}
							<Badge
								type={clusterBadgeType(status.cluster_status)}
								content={status.cluster_status}
							/>
						{:else}
							<span class="text-sm text-gray-400">—</span>
						{/if}
					</div>
				</div>
				<div
					class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">
						{$i18n.t('Collections')}
					</div>
					<div class="text-lg font-semibold">{status.collections?.length ?? 0}</div>
				</div>
				<div
					class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">
						{$i18n.t('Total Documents')}
					</div>
					<div class="text-lg font-semibold">{totalDocs.toLocaleString()}</div>
				</div>
				<div
					class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">
						{$i18n.t('Total Vectors')}
					</div>
					<div class="text-lg font-semibold">{totalVectors.toLocaleString()}</div>
				</div>
			</div>
		</div>

		<!-- Collections Mini-Table -->
		{#if status.collections && status.collections.length > 0}
			<div>
				<div class="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
					{$i18n.t('Collections Overview')}
				</div>
				<div
					class="max-h-64 overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-700"
				>
					<table class="w-full text-sm">
						<thead class="bg-gray-50 dark:bg-gray-850 sticky top-0">
							<tr>
								<th
									class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400"
								>
									{$i18n.t('Name')}
								</th>
								<th
									class="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400"
								>
									{$i18n.t('Documents')}
								</th>
								<th
									class="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400"
								>
									{$i18n.t('Vectors')}
								</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
							{#each status.collections as c (c.name)}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-850/50">
									<td class="px-3 py-2 text-gray-700 dark:text-gray-200 truncate max-w-[16rem]">
										{c.name}
									</td>
									<td class="px-3 py-2 text-right text-gray-500 dark:text-gray-400 tabular-nums">
										{c.document_count.toLocaleString()}
									</td>
									<td class="px-3 py-2 text-right text-gray-500 dark:text-gray-400 tabular-nums">
										{(c.vector_count ?? 0).toLocaleString()}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{:else}
		<div class="text-gray-400 dark:text-gray-500">
			{$i18n.t('Unable to fetch vector DB status')}
		</div>
	{/if}

	<!-- Configuration cross-links -->
	<div>
		<div class="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">
			{$i18n.t('Configuration')}
		</div>
		<InfoCallout
			>{$i18n.t(
				'These settings govern how RAG behaves and are configured under Admin Settings.'
			)}</InfoCallout
		>
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
			<a
				href={resolve('/admin/settings?tab=documents')}
				class="block p-4 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
			>
				<div class="text-sm font-medium">{$i18n.t('Document & Embedding Settings')}</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
					{$i18n.t(
						'Embedding model, chunking, retrieval (top K, hybrid search), content extraction.'
					)}
				</div>
			</a>
			<a
				href={resolve('/admin/settings?tab=rag')}
				class="block p-4 rounded-lg bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
			>
				<div class="text-sm font-medium">{$i18n.t('Vector & Engine Settings')}</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
					{$i18n.t('Vector database engine and embedding model connection.')}
				</div>
			</a>
		</div>
	</div>
</div>
