<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { get } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { user } from '$lib/stores';

	import Overview from './Audit/Overview.svelte';
	import Logs from './Audit/Logs.svelte';
	import PersonalData from './Audit/PersonalData.svelte';
	import Anomalies from './Audit/Anomalies.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const TABS = ['overview', 'logs', 'personal', 'anomalies'] as const;
	type Tab = (typeof TABS)[number];

	// Accept the legacy sub-route slugs as deep-link aliases (?tab=personal-data).
	function resolveTab(value: string | null): Tab {
		if (value === 'personal-data') return 'personal';
		return (TABS as readonly string[]).includes(value ?? '') ? (value as Tab) : 'overview';
	}

	let selectedTab: Tab = $derived(resolveTab(page.url.searchParams.get('tab')));
	let loaded = $state(false);

	onMount(async () => {
		if (get(user)?.role !== 'admin') {
			await goto(resolve('/'));
			return;
		}
		loaded = true;

		const containerElement = document.getElementById('audit-tabs-container');
		if (containerElement) {
			const wheelHandler = (event: WheelEvent) => {
				if (event.deltaY !== 0) containerElement.scrollLeft += event.deltaY;
			};
			containerElement.addEventListener('wheel', wheelHandler);
			return () => containerElement.removeEventListener('wheel', wheelHandler);
		}
	});

	function switchTab(tab: Tab) {
		goto(resolve(`/admin/audit?tab=${tab}`));
	}
</script>

{#if loaded}
	<div class="flex flex-col lg:flex-row w-full h-full pb-2 lg:space-x-6">
		<div
			id="audit-tabs-container"
			role="tablist"
			aria-label={$i18n.t('Audit sections')}
			class="flex flex-row overflow-x-auto gap-2.5 max-w-full lg:gap-1.5 lg:flex-col lg:flex-none lg:w-48 dark:text-gray-200 text-sm font-medium text-left scrollbar-none"
		>
			<button
				role="tab"
				aria-selected={selectedTab === 'overview'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'overview'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('overview')}
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
				<div class="self-center">{$i18n.t('Overview')}</div>
			</button>

			<button
				role="tab"
				aria-selected={selectedTab === 'logs'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'logs'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('logs')}
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
							d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
						/>
					</svg>
				</div>
				<div class="self-center">{$i18n.t('Logs')}</div>
			</button>

			<button
				role="tab"
				aria-selected={selectedTab === 'personal'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'personal'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('personal')}
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
							d="M15 9h3.75M15 12h3.75M15 15h3.75M4.5 19.5h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Zm6-10.125a1.875 1.875 0 1 1-3.75 0 1.875 1.875 0 0 1 3.75 0Zm1.294 6.336a6.721 6.721 0 0 1-3.17.789 6.721 6.721 0 0 1-3.168-.789 3.376 3.376 0 0 1 6.338 0Z"
						/>
					</svg>
				</div>
				<div class="self-center">{$i18n.t('Personal Data')}</div>
			</button>

			<button
				role="tab"
				aria-selected={selectedTab === 'anomalies'}
				class="px-2 py-2 min-w-fit rounded-lg lg:flex-none flex text-right transition {selectedTab ===
				'anomalies'
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => switchTab('anomalies')}
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
							d="M12 9v3.75m0-10.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Zm0 13.036h.008v.008H12v-.008Z"
						/>
					</svg>
				</div>
				<div class="self-center">{$i18n.t('Anomalies')}</div>
			</button>
		</div>

		<div class="flex-1 mt-1 lg:mt-0 overflow-y-scroll" role="tabpanel">
			{#if selectedTab === 'overview'}
				<Overview />
			{:else if selectedTab === 'logs'}
				<Logs />
			{:else if selectedTab === 'personal'}
				<PersonalData />
			{:else if selectedTab === 'anomalies'}
				<Anomalies />
			{/if}
		</div>
	</div>
{/if}
