<!-- BCGPT WebUI - Admin Layout: Admin-only shell with section tabs -->
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import { APP_NAME_STORE, showSidebar, user } from '$lib/stores';
	import MenuLines from '$lib/components/icons/MenuLines.svelte';
	import { page } from '$app/state';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let loaded = $state(false);

	onMount(async () => {
		if (get(user)?.role !== 'admin') {
			await goto(resolve('/'));
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Admin Panel')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

{#if loaded}
	<div
		class=" flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-260px)]'
			: ''} max-w-full"
	>
		<nav class="px-4 pt-2 backdrop-blur-xl drag-region">
			<div class=" flex items-center gap-1">
				<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-end">
					<button
						id="sidebar-toggle-button"
						class="cursor-pointer p-2 flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition"
						onclick={() => {
							showSidebar.set(!$showSidebar);
						}}
						aria-label={$i18n.t('Toggle sidebar')}
					>
						<div class=" m-auto self-center">
							<MenuLines />
						</div>
					</button>
				</div>

				<div class=" flex w-full">
					<div
						role="tablist"
						aria-label={$i18n.t('Admin sections')}
						class="flex gap-1.5 scrollbar-none overflow-x-auto w-fit text-center text-sm font-medium rounded-full bg-transparent pt-1.5 pb-1"
					>
						<a
							role="tab"
							aria-selected={page.url.pathname === '/admin'}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/admin'
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin')}>{$i18n.t('Overview')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/users')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes('/admin/users')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/users')}>{$i18n.t('Users')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/evaluations')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes(
								'/admin/evaluations'
							)
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/evaluations')}>{$i18n.t('Evaluations')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/functions')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes(
								'/admin/functions'
							)
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/functions')}>{$i18n.t('Functions')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/skill')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes('/admin/skill')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/skill')}>{$i18n.t('Skills')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/mcp')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes('/admin/mcp')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/mcp')}>{$i18n.t('MCP')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/audit')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes('/admin/audit')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/audit')}>{$i18n.t('Audit')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/rag')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes('/admin/rag')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/rag')}>{$i18n.t('RAG')}</a
						>

						<a
							role="tab"
							aria-selected={page.url.pathname.includes('/admin/settings')}
							class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname.includes(
								'/admin/settings'
							)
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							href={resolve('/admin/settings')}>{$i18n.t('Settings')}</a
						>
					</div>
				</div>
			</div>
		</nav>

		<div class="pb-2 px-5 flex-1 max-h-full overflow-y-auto">
			{@render children?.()}
		</div>
	</div>
{/if}
