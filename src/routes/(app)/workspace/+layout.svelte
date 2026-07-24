<!-- BCGPT WebUI - Workspace Layout: Workspace navigation with permission-gated tabs -->
<script lang="ts">
	import { get } from 'svelte/store';
	import { onMount, getContext } from 'svelte';
	import { APP_NAME_STORE, showSidebar, user } from '$lib/stores';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import MenuLines from '$lib/components/icons/MenuLines.svelte';
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
			if (page.url.pathname.includes('/models') && !get(user)?.permissions?.workspace?.models) {
				goto(resolve('/'));
			} else if (
				page.url.pathname.includes('/knowledge') &&
				!get(user)?.permissions?.workspace?.knowledge
			) {
				goto(resolve('/'));
			} else if (
				page.url.pathname.includes('/prompts') &&
				!get(user)?.permissions?.workspace?.prompts
			) {
				goto(resolve('/'));
			} else if (
				page.url.pathname.includes('/tools') &&
				!get(user)?.permissions?.workspace?.tools
			) {
				goto(resolve('/'));
			}
		}

		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Workspace')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

{#if loaded}
	<div
		class=" relative flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-260px)]'
			: ''} max-w-full"
	>
		<nav class="   px-2.5 pt-1 backdrop-blur-xl drag-region">
			<div class=" flex items-center gap-1">
				<div class="{$showSidebar ? 'md:hidden' : ''} self-center flex flex-none items-center">
					<button
						id="sidebar-toggle-button"
						class="cursor-pointer p-1.5 flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition"
						onclick={() => {
							showSidebar.set(!$showSidebar);
						}}
						aria-label={$i18n.t('Toggle Sidebar')}
					>
						<div class=" m-auto self-center">
							<MenuLines />
						</div>
					</button>
				</div>

				<div class="">
					<div
						class="flex gap-1 scrollbar-none overflow-x-auto w-fit text-center text-sm font-medium rounded-full bg-transparent py-1 touch-auto pointer-events-auto"
					>
						{#if $user?.role === 'admin' || $user?.permissions?.workspace?.models}
							<a
								class="min-w-fit rounded-full p-1.5 {page.url.pathname.includes('/workspace/agents')
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								href={resolve('/workspace/agents')}>{$i18n.t('Agents')}</a
							>
						{/if}

						{#if $user?.role === 'admin' || $user?.permissions?.workspace?.knowledge}
							<a
								class="min-w-fit rounded-full p-1.5 {page.url.pathname.includes(
									'/workspace/knowledge'
								)
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								href={resolve('/workspace/knowledge')}
							>
								{$i18n.t('Knowledge')}
							</a>
						{/if}

						{#if $user?.role === 'admin' || $user?.permissions?.workspace?.prompts}
							<a
								class="min-w-fit rounded-full p-1.5 {page.url.pathname.includes(
									'/workspace/prompts'
								)
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								href={resolve('/workspace/prompts')}>{$i18n.t('Prompts')}</a
							>
						{/if}

						{#if $user?.role === 'admin' || $user?.permissions?.workspace?.tools}
							<a
								class="min-w-fit rounded-full p-1.5 {page.url.pathname.includes('/workspace/tools')
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								href={resolve('/workspace/tools')}
							>
								{$i18n.t('Tools')}
							</a>
						{/if}
					</div>
				</div>

				<!-- <div class="flex items-center text-xl font-semibold">{$i18n.t('Workspace')}</div> -->
			</div>
		</nav>

		<div class="  pb-1 px-[18px] flex-1 max-h-full overflow-y-auto" id="workspace-container">
			{@render children?.()}
		</div>
	</div>
{/if}
