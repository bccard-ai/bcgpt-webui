<!-- BCGPT WebUI - Home Layout: Navigation bar with sidebar toggle -->
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { APP_NAME_STORE, showSidebar } from '$lib/stores';
	import MenuLines from '$lib/components/icons/MenuLines.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	onMount(async () => {});
</script>

<svelte:head>
	<title>
		{$i18n.t('Home')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

<div
	class=" flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-260px)]'
		: ''} max-w-full"
>
	<nav class="   px-2.5 pt-1 backdrop-blur-xl w-full drag-region">
		<div class=" flex items-center">
			<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-end">
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

			<div class=" flex w-full"></div>
		</div>
	</nav>

	<div class=" flex-1 max-h-full overflow-y-auto">
		{@render children?.()}
	</div>
</div>
