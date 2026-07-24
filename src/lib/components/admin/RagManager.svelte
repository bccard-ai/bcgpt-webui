<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		getVectorDBStatus,
		getVectorDBCollections,
		type VectorDBStatus as VectorDBStatusType,
		type CollectionInfo
	} from '$lib/apis/retrieval';
	import { getKnowledgeBases } from '$lib/apis/knowledge';
	import type { KnowledgeBase } from '$lib/apis/knowledge';
	import { getModels } from '$lib/apis';

	import VectorDBStatusTab from './RagManager/VectorDBStatus.svelte';
	import VectorDBCollectionsTab from './RagManager/VectorDBCollections.svelte';
	import KnowledgeBasesTab from './RagManager/KnowledgeBases.svelte';
	import DangerZoneTab from './RagManager/DangerZone.svelte';

	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const TABS = ['status', 'collections', 'knowledge', 'danger'] as const;
	type Tab = (typeof TABS)[number];

	function resolveTab(value: string | null): Tab {
		return (TABS as readonly string[]).includes(value ?? '') ? (value as Tab) : 'status';
	}

	let selectedTab = $state<Tab>('status');
	let loaded = $state(false);

	let dbStatus = $state<VectorDBStatusType | null>(null);
	let collections = $state<CollectionInfo[]>([]);
	let knowledgeBasesList = $state<KnowledgeBase[]>([]);
	// Used to show the blast radius ("attached to N models") before deleting a knowledge base.
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let models = $state<any[]>([]);

	function switchTab(tab: Tab) {
		if (tab === selectedTab) return;
		selectedTab = tab;
		const url = new URL(page.url);
		url.searchParams.set('tab', tab);
		goto(resolve((url.pathname + url.search) as unknown as '/'), { replaceState: true });
	}

	const refreshData = async () => {
		try {
			const [status, colls, kbs] = await Promise.all([
				getVectorDBStatus(''),
				getVectorDBCollections(''),
				getKnowledgeBases('')
			]);
			dbStatus = status;
			collections = colls ?? [];
			knowledgeBasesList = kbs ?? [];
		} catch (e) {
			console.error('Failed to load RAG data:', e);
			toast.error(`${$i18n.t('Failed to load RAG data')}: ${e}`);
		}

		// Non-critical: used only to surface how many models reference each knowledge base.
		// A failure here must not block the core RAG views.
		try {
			models = (await getModels('')) ?? [];
		} catch (e) {
			console.error('Failed to load models for knowledge-base usage count:', e);
			models = [];
		}
	};

	onMount(async () => {
		selectedTab = resolveTab(page.url.searchParams.get('tab'));
		await refreshData();
		loaded = true;

		const containerElement = document.getElementById('rag-tabs-container');
		if (containerElement) {
			const wheelHandler = (event: WheelEvent) => {
				if (event.deltaY !== 0) containerElement.scrollLeft += event.deltaY;
			};
			containerElement.addEventListener('wheel', wheelHandler);
			return () => containerElement.removeEventListener('wheel', wheelHandler);
		}
	});
</script>

{#if loaded}
	<div class="flex flex-col lg:flex-row w-full h-full pb-2 lg:space-x-6">
		<div
			id="rag-tabs-container"
			role="tablist"
			aria-label={$i18n.t('RAG sections')}
			class="flex flex-row overflow-x-auto gap-2.5 max-w-full lg:gap-1.5 lg:flex-col lg:flex-none lg:w-48 dark:text-gray-200 text-sm font-medium text-left scrollbar-none"
		>
			<button
				role="tab"
				aria-selected={selectedTab === 'status'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'status'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('status')}
			>
				<div class="self-center mr-2">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="size-4"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"
						/>
					</svg>
				</div>
				<div class="self-center">{$i18n.t('Status')}</div>
			</button>

			<button
				role="tab"
				aria-selected={selectedTab === 'collections'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'collections'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('collections')}
			>
				<div class="self-center mr-2">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="size-4"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125"
						/>
					</svg>
				</div>
				<div class="self-center">{$i18n.t('Collections')}</div>
			</button>

			<button
				role="tab"
				aria-selected={selectedTab === 'knowledge'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'knowledge'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('knowledge')}
			>
				<div class="self-center mr-2">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="size-4"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
						/>
					</svg>
				</div>
				<div class="self-center">{$i18n.t('Knowledge Bases')}</div>
			</button>

			<button
				role="tab"
				aria-selected={selectedTab === 'danger'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'danger'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('danger')}
			>
				<div class="self-center mr-2">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="size-4"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
						/>
					</svg>
				</div>
				<div class="self-center">{$i18n.t('Danger Zone')}</div>
			</button>
		</div>

		<div class="flex-1 mt-1 lg:mt-0 overflow-y-scroll" role="tabpanel">
			{#if selectedTab === 'status'}
				<VectorDBStatusTab status={dbStatus} />
			{:else if selectedTab === 'collections'}
				<VectorDBCollectionsTab
					{collections}
					knowledgeBases={knowledgeBasesList}
					status={dbStatus}
					onRefresh={refreshData}
				/>
			{:else if selectedTab === 'knowledge'}
				<KnowledgeBasesTab
					knowledgeBases={knowledgeBasesList}
					{collections}
					{models}
					onRefresh={refreshData}
				/>
			{:else if selectedTab === 'danger'}
				<DangerZoneTab
					collectionsCount={collections.length}
					kbCount={knowledgeBasesList.length}
					onRefresh={refreshData}
				/>
			{/if}
		</div>
	</div>
{/if}
