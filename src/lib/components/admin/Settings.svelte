<script lang="ts">
	/**
	 * Admin Settings Container
	 *
	 * Main settings page with tabbed navigation for all admin configuration sections.
	 * Uses URL query parameter `tab` to track the active tab for deep-linking.
	 * Supports horizontal scrolling on mobile and vertical sidebar on desktop.
	 */
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext, tick, onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { toast } from 'svelte-sonner';

	import { config } from '$lib/stores';
	import { getBackendConfig } from '$lib/apis';

	import General from './Settings/General.svelte';
	import Pipelines from './Settings/Pipelines.svelte';
	import Audio from './Settings/Audio.svelte';
	import Images from './Settings/Images.svelte';
	import Interface from './Settings/Interface.svelte';
	import Models from './Settings/Models.svelte';
	import Connections from './Settings/Connections.svelte';
	import Documents from './Settings/Documents.svelte';
	import WebSearch from './Settings/WebSearch.svelte';
	import Rag from './Settings/Rag.svelte';
	import AdvancedRag from './Settings/AdvancedRag.svelte';
	import Agent from './Settings/Agent.svelte';
	import Database from './Settings/Database.svelte';
	import Security from './Settings/Security.svelte';
	import Audit from './Settings/Audit.svelte';
	import DocumentChartBar from '../icons/DocumentChartBar.svelte';
	import Evaluations from './Settings/Evaluations.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/** Currently selected tab, derived from URL search params */
	let selectedTab = $derived(page.url.searchParams.get('tab') || 'general');

	/**
	 * Common save handler that shows a success toast and refreshes the backend config.
	 * Used by tabs that need to reload config after saving.
	 */
	const saveAndRefreshConfig = async () => {
		toast.success($i18n.t('Settings saved successfully!'));
		await tick();
		await config.set(await getBackendConfig());
	};

	/**
	 * Simple save handler that only shows a success toast.
	 * Used by tabs that don't need config refresh.
	 */
	const saveWithToast = () => {
		toast.success($i18n.t('Settings saved successfully!'));
	};

	/** Tab navigation configuration */
	interface TabConfig {
		/** Unique tab identifier matching URL param */
		id: string;
		/** Section label (used as group header when defined) */
		section?: string;
		/** Display name for the tab button */
		label: string;
		/** SVG icon snippet for the tab */
		icon:
			| 'general'
			| 'security'
			| 'audit'
			| 'connections'
			| 'models'
			| 'evaluations'
			| 'agent'
			| 'documents'
			| 'rag'
			| 'advanced-rag'
			| 'web'
			| 'interface'
			| 'audio'
			| 'images'
			| 'pipelines'
			| 'db';
	}

	/**
	 * Tab definitions in sidebar order.
	 *
	 * Tabs are organized into six named groups. The first tab of each group carries
	 * a `section` label, which renders as a group header in the sidebar. Because every
	 * tab now belongs to a named group, no manual divider hack is needed — the next
	 * section header acts as the visual separator.
	 */
	const tabs: TabConfig[] = [
		// General — instance configuration & end-user UI
		{ id: 'general', section: 'General', label: 'General', icon: 'general' },
		{ id: 'interface', label: 'Interface', icon: 'interface' },
		// Security & Audit — governance / compliance
		{ id: 'security', section: 'Security & Audit', label: 'Security', icon: 'security' },
		{ id: 'audit', label: 'Audit', icon: 'audit' },
		// AI & Models — providers & model behavior
		{ id: 'connections', section: 'AI & Models', label: 'Connections', icon: 'connections' },
		{ id: 'models', label: 'Models', icon: 'models' },
		{ id: 'agent', label: 'Agent', icon: 'agent' },
		{ id: 'evaluations', label: 'Evaluations', icon: 'evaluations' },
		// Knowledge & Retrieval — the retrieval pipeline end-to-end
		{ id: 'documents', section: 'Knowledge & Retrieval', label: 'Documents', icon: 'documents' },
		{ id: 'rag', label: 'RAG', icon: 'rag' },
		{ id: 'advanced-rag', label: 'Advanced RAG', icon: 'advanced-rag' },
		{ id: 'web', label: 'Web Search', icon: 'web' },
		// Media — non-text modality integrations
		{ id: 'audio', section: 'Media', label: 'Audio', icon: 'audio' },
		{ id: 'images', label: 'Images', icon: 'images' },
		// Infrastructure — operational / platform settings
		{ id: 'pipelines', section: 'Infrastructure', label: 'Pipelines', icon: 'pipelines' },
		{ id: 'db', label: 'Database', icon: 'db' }
	];

	/** Navigate to a specific settings tab */
	const navigateToTab = (tabId: string) => {
		goto(resolve(`/admin/settings?tab=${tabId}`));
	};

	/** Set up horizontal scroll conversion on the tab container */
	onMount(() => {
		const container = document.getElementById('admin-settings-tabs-container');
		if (container) {
			const wheelHandler = (event: WheelEvent) => {
				if (event.deltaY !== 0) {
					container.scrollLeft += event.deltaY;
				}
			};
			container.addEventListener('wheel', wheelHandler);
			return () => container.removeEventListener('wheel', wheelHandler);
		}
	});
</script>

<div class="flex flex-col lg:flex-row w-full h-full pb-2 lg:space-x-6">
	<div
		id="admin-settings-tabs-container"
		role="tablist"
		aria-label={$i18n.t('Admin settings sections')}
		class="tabs flex flex-row overflow-x-auto gap-2.5 max-w-full lg:gap-1.5 lg:flex-col lg:flex-none lg:w-48 dark:text-gray-200 text-sm font-medium text-left scrollbar-none"
	>
		{#each tabs as tab (tab.id)}
			{#if tab.section}
				<div
					class="hidden lg:block text-[0.65rem] font-semibold text-gray-400 dark:text-gray-600 uppercase tracking-wider px-0.5 pt-4 pb-0.5 {tab.id ===
					'general'
						? '!pt-3'
						: ''}"
				>
					{$i18n.t(tab.section)}
				</div>
			{/if}

			<button
				role="tab"
				aria-selected={selectedTab === tab.id}
				class="px-2 py-2 min-w-fit rounded-lg flex-1 lg:flex-none flex text-left transition {selectedTab ===
				tab.id
					? ''
					: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				onclick={() => navigateToTab(tab.id)}
			>
				<div class="self-center mr-2">
					{#if tab.icon === 'general'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M6.955 1.45A.5.5 0 0 1 7.452 1h1.096a.5.5 0 0 1 .497.45l.17 1.699c.484.12.94.312 1.356.562l1.321-1.081a.5.5 0 0 1 .67.033l.774.775a.5.5 0 0 1 .034.67l-1.08 1.32c.25.417.44.873.561 1.357l1.699.17a.5.5 0 0 1 .45.497v1.096a.5.5 0 0 1-.45.497l-1.699.17c-.12.484-.312.94-.562 1.356l1.082 1.322a.5.5 0 0 1-.034.67l-.774.774a.5.5 0 0 1-.67.033l-1.322-1.08c-.416.25-.872.44-1.356.561l-.17 1.699a.5.5 0 0 1-.497.45H7.452a.5.5 0 0 1-.497-.45l-.17-1.699a4.973 4.973 0 0 1-1.356-.562L4.108 13.37a.5.5 0 0 1-.67-.033l-.774-.775a.5.5 0 0 1-.034-.67l1.08-1.32a4.971 4.971 0 0 1-.561-1.357l-1.699-.17A.5.5 0 0 1 1 8.548V7.452a.5.5 0 0 1 .45-.497l1.699-.17c.12-.484.312-.94.562-1.356L2.629 4.107a.5.5 0 0 1 .034-.67l.774-.774a.5.5 0 0 1 .67-.033L5.43 3.71a4.97 4.97 0 0 1 1.356-.561l.17-1.699ZM6 8c0 .538.212 1.026.558 1.385l.057.057a2 2 0 0 0 2.828-2.828l-.058-.056A2 2 0 0 0 6 8Z"
								clip-rule="evenodd"
							/>
						</svg>
					{:else if tab.icon === 'security'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M8 1a3.5 3.5 0 0 0-3.5 3.5V7A1.5 1.5 0 0 0 3 8.5v5A1.5 1.5 0 0 0 4.5 15h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 7V4.5A3.5 3.5 0 0 0 8 1Zm2 6V4.5a2 2 0 1 0-4 0V7h4Z"
								clip-rule="evenodd"
							/>
						</svg>
					{:else if tab.icon === 'audit'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M3 2.75A.75.75 0 0 1 3.75 2h3.401a1.5 1.5 0 0 1 1.085.462l2.15 2.238A1.5 1.5 0 0 1 11 5.738V13.25a.75.75 0 0 1-.75.75h-6.5a.75.75 0 0 1-.75-.75V2.75Z"
								clip-rule="evenodd"
							/>
							<path
								fill-rule="evenodd"
								d="M8.5 2v3.5A1.5 1.5 0 0 0 10 7h3.5v6.25a.75.75 0 0 1-.75.75h-6.5a.75.75 0 0 1-.75-.75V2.75A.75.75 0 0 1 6.25 2H8.5Z"
								clip-rule="evenodd"
							/>
						</svg>
					{:else if tab.icon === 'connections'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M1 9.5A3.5 3.5 0 0 0 4.5 13H12a3 3 0 0 0 .917-5.857 2.503 2.503 0 0 0-3.198-3.019 3.5 3.5 0 0 0-6.628 2.171A3.5 3.5 0 0 0 1 9.5Z"
							/>
						</svg>
					{:else if tab.icon === 'models'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M10 1c3.866 0 7 1.79 7 4s-3.134 4-7 4-7-1.79-7-4 3.134-4 7-4zm5.694 8.13c.464-.264.91-.583 1.306-.952V10c0 2.21-3.134 4-7 4s-7-1.79-7-4V8.178c.396.37.842.688 1.306.953C5.838 10.006 7.854 10.5 10 10.5s4.162-.494 5.694-1.37zM3 13.179V15c0 2.21 3.134 4 7 4s7-1.79 7-4v-1.822c-.396.37-.842.688-1.306.953-1.532.875-3.548 1.369-5.694 1.369s-4.162-.494-5.694-1.37A7.009 7.009 0 013 13.179z"
								clip-rule="evenodd"
							/>
						</svg>
					{:else if tab.icon === 'evaluations'}
						<DocumentChartBar />
					{:else if tab.icon === 'agent'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M12 .75a8.25 8.25 0 0 0-4.135 15.39c.431.826.138 1.9-.586 2.525-.953.822-1.529 2.008-1.529 3.335h12c0-1.327-.576-2.513-1.53-3.335-.723-.625-1.016-1.7-.585-2.525A8.25 8.25 0 0 0 12 .75ZM8.073 19.1a4.5 4.5 0 0 1 7.854 0H8.073Z"
							/>
						</svg>
					{:else if tab.icon === 'documents'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path d="M11.625 16.5a1.875 1.875 0 1 0 0-3.75 1.875 1.875 0 0 0 0 3.75Z" />
							<path
								fill-rule="evenodd"
								d="M5.625 1.5H9a3.75 3.75 0 0 1 3.75 3.75v1.875c0 1.036.84 1.875 1.875 1.875H16.5a3.75 3.75 0 0 1 3.75 3.75v7.875c0 1.035-.84 1.875-1.875 1.875H5.625a1.875 1.875 0 0 1-1.875-1.875V3.375c0-1.036.84-1.875 1.875-1.875Zm6 16.5c.66 0 1.277-.19 1.797-.518l1.048 1.048a.75.75 0 0 0 1.06-1.06l-1.047-1.048A3.375 3.375 0 1 0 11.625 18Z"
								clip-rule="evenodd"
							/>
							<path
								d="M14.25 5.25a5.23 5.23 0 0 0-1.279-3.434 9.768 9.768 0 0 1 6.963 6.963A5.23 5.23 0 0 0 16.5 7.5h-1.875a.375.375 0 0 1-.375-.375V5.25Z"
							/>
						</svg>
					{:else if tab.icon === 'rag'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M5.625 3.75a2.625 2.625 0 1 0 0 5.25h12.75a2.625 2.625 0 0 0 0-5.25H5.625ZM3.75 11.25a.75.75 0 0 0 0 1.5h16.5a.75.75 0 0 0 0-1.5H3.75ZM3 15.75a.75.75 0 0 1 .75-.75h16.5a.75.75 0 0 1 0 1.5H3.75a.75.75 0 0 1-.75-.75ZM3.75 18.75a.75.75 0 0 0 0 1.5h16.5a.75.75 0 0 0 0-1.5H3.75Z"
							/>
						</svg>
					{:else if tab.icon === 'advanced-rag'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M3.75 13.5l.98-5.15A2.25 2.25 0 0 1 6.94 6.5h10.12a2.25 2.25 0 0 1 2.21 1.85l.98 5.15M3.75 13.5h16.5m-16.5 0a2.25 2.25 0 1 0 0 4.5h16.5a2.25 2.25 0 0 0 0-4.5m-9.75-3h.008v.008H10.5V10.5Zm3.75 0h.008v.008h-.008V10.5Zm-1.5 3h.008v.008H12V13.5Zm3.75 0h.008v.008h-.008V13.5ZM10.5 16.5h.008v.008H10.5V16.5Zm3.75 0h.008v.008h-.008V16.5Z"
							/>
						</svg>
					{:else if tab.icon === 'web'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M21.721 12.752a9.711 9.711 0 0 0-.945-5.003 12.754 12.754 0 0 1-4.339 2.708 18.991 18.991 0 0 1-.214 4.772 17.165 17.165 0 0 0 5.498-2.477ZM14.634 15.55a17.324 17.324 0 0 0 .332-4.647c-.952.227-1.945.347-2.966.347-1.021 0-2.014-.12-2.966-.347a17.515 17.515 0 0 0 .332 4.647 17.385 17.385 0 0 0 5.268 0ZM9.772 17.119a18.963 18.963 0 0 0 4.456 0A17.182 17.182 0 0 1 12 21.724a17.18 17.18 0 0 1-2.228-4.605ZM7.777 15.23a18.87 18.87 0 0 1-.214-4.774 12.753 12.753 0 0 1-4.34-2.708 9.711 9.711 0 0 0-.944 5.004 17.165 17.165 0 0 0 5.498 2.477ZM21.356 14.752a9.765 9.765 0 0 1-7.478 6.817 18.64 18.64 0 0 0 1.988-4.718 18.627 18.627 0 0 0 5.49-2.098ZM2.644 14.752c1.682.971 3.53 1.688 5.49 2.099a18.64 18.64 0 0 0 1.988 4.718 9.765 9.765 0 0 1-7.478-6.816ZM13.878 2.43a9.755 9.755 0 0 1 6.116 3.986 11.267 11.267 0 0 1-3.746 2.504 18.63 18.63 0 0 0-2.37-6.49ZM12 2.276a17.152 17.152 0 0 1 2.805 7.121c-.897.23-1.837.353-2.805.353-.968 0-1.908-.122-2.805-.353A17.151 17.151 0 0 1 12 2.276ZM10.122 2.43a18.629 18.629 0 0 0-2.37 6.49 11.266 11.266 0 0 1-3.746-2.504 9.754 9.754 0 0 1 6.116-3.985Z"
							/>
						</svg>
					{:else if tab.icon === 'interface'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M2 4.25A2.25 2.25 0 0 1 4.25 2h7.5A2.25 2.25 0 0 1 14 4.25v5.5A2.25 2.25 0 0 1 11.75 12h-1.312c.1.128.21.248.328.36a.75.75 0 0 1 .234.545v.345a.75.75 0 0 1-.75.75h-4.5a.75.75 0 0 1-.75-.75v-.345a.75.75 0 0 1 .234-.545c.118-.111.228-.232.328-.36H4.25A2.25 2.25 0 0 1 2 9.75v-5.5Zm2.25-.75a.75.75 0 0 0-.75.75v4.5c0 .414.336.75.75.75h7.5a.75.75 0 0 0 .75-.75v-4.5a.75.75 0 0 0-.75-.75h-7.5Z"
								clip-rule="evenodd"
							/>
						</svg>
					{:else if tab.icon === 'audio'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M7.557 2.066A.75.75 0 0 1 8 2.75v10.5a.75.75 0 0 1-1.248.56L3.59 11H2a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h1.59l3.162-2.81a.75.75 0 0 1 .805-.124ZM12.95 3.05a.75.75 0 1 0-1.06 1.06 5.5 5.5 0 0 1 0 7.78.75.75 0 1 0 1.06 1.06 7 7 0 0 0 0-9.9Z"
							/>
							<path
								d="M10.828 5.172a.75.75 0 1 0-1.06 1.06 2.5 2.5 0 0 1 0 3.536.75.75 0 1 0 1.06 1.06 4 4 0 0 0 0-5.656Z"
							/>
						</svg>
					{:else if tab.icon === 'images'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M2 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4Zm10.5 5.707a.5.5 0 0 0-.146-.353l-1-1a.5.5 0 0 0-.708 0L9.354 9.646a.5.5 0 0 1-.708 0L6.354 7.354a.5.5 0 0 0-.708 0l-2 2a.5.5 0 0 0-.146.353V12a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5V9.707ZM12 5a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"
								clip-rule="evenodd"
							/>
						</svg>
					{:else if tab.icon === 'pipelines'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="currentColor"
							class="size-4"
						>
							<path
								d="M11.644 1.59a.75.75 0 0 1 .712 0l9.75 5.25a.75.75 0 0 1 0 1.32l-9.75 5.25a.75.75 0 0 1-.712 0l-9.75-5.25a.75.75 0 0 1 0-1.32l9.75-5.25Z"
							/>
							<path
								d="m3.265 10.602 7.668 4.129a2.25 2.25 0 0 0 2.134 0l7.668-4.13 1.37.739a.75.75 0 0 1 0 1.32l-9.75 5.25a.75.75 0 0 1-.71 0l-9.75-5.25a.75.75 0 0 1 0-1.32l1.37-.738Z"
							/>
							<path
								d="m10.933 19.231-7.668-4.13-1.37.739a.75.75 0 0 0 0 1.32l9.75 5.25c.221.12.489.12.71 0l9.75-5.25a.75.75 0 0 0 0-1.32l-1.37-.738-7.668 4.13a2.25 2.25 0 0 1-2.134-.001Z"
							/>
						</svg>
					{:else if tab.icon === 'db'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path d="M8 7c3.314 0 6-1.343 6-3s-2.686-3-6-3-6 1.343-6 3 2.686 3 6 3Z" />
							<path
								d="M8 8.5c1.84 0 3.579-.37 4.914-1.037A6.33 6.33 0 0 0 14 6.78V8c0 1.657-2.686 3-6 3S2 9.657 2 8V6.78c.346.273.72.5 1.087.683C4.42 8.131 6.16 8.5 8 8.5Z"
							/>
							<path
								d="M8 12.5c1.84 0 3.579-.37 4.914-1.037.366-.183.74-.41 1.086-.684V12c0 1.657-2.686 3-6 3s-6-1.343-6-3v-1.22c.346.273.72.5 1.087.683C4.42 12.131 6.16 12.5 8 12.5Z"
							/>
						</svg>
					{/if}
				</div>
				<div class="self-center">{$i18n.t(tab.label)}</div>
			</button>
		{/each}
	</div>

	<div
		class="admin-settings-panel flex-1 mt-3 lg:mt-0 overflow-y-scroll pr-1 scrollbar-hidden"
		role="tabpanel"
	>
		{#if selectedTab === 'general'}
			<General saveHandler={saveAndRefreshConfig} />
		{:else if selectedTab === 'connections'}
			<Connections onSave={saveWithToast} />
		{:else if selectedTab === 'models'}
			<Models />
		{:else if selectedTab === 'evaluations'}
			<Evaluations onSave={saveWithToast} />
		{:else if selectedTab === 'agent'}
			<Agent onSave={saveAndRefreshConfig} />
		{:else if selectedTab === 'documents'}
			<Documents onSave={saveAndRefreshConfig} />
		{:else if selectedTab === 'rag'}
			<Rag onSave={saveAndRefreshConfig} />
		{:else if selectedTab === 'advanced-rag'}
			<AdvancedRag onSave={saveAndRefreshConfig} />
		{:else if selectedTab === 'web'}
			<WebSearch saveHandler={saveAndRefreshConfig} />
		{:else if selectedTab === 'interface'}
			<Interface onSave={saveWithToast} />
		{:else if selectedTab === 'audio'}
			<Audio saveHandler={saveWithToast} />
		{:else if selectedTab === 'images'}
			<Images onSave={saveWithToast} />
		{:else if selectedTab === 'db'}
			<Database saveHandler={saveWithToast} />
		{:else if selectedTab === 'pipelines'}
			<Pipelines saveHandler={saveWithToast} />
		{:else if selectedTab === 'security'}
			<Security saveHandler={saveAndRefreshConfig} />
		{:else if selectedTab === 'audit'}
			<Audit saveHandler={saveAndRefreshConfig} />
		{/if}
	</div>
</div>
