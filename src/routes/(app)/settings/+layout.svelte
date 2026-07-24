<!-- BCGPT WebUI - Settings Layout: Tabbed settings navigation with sidebar -->
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { APP_NAME_STORE, showSidebar, user, config } from '$lib/stores';
	import MenuLines from '$lib/components/icons/MenuLines.svelte';
	import { page } from '$app/state';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	import Search from '$lib/components/icons/Search.svelte';
	import User from '$lib/components/icons/User.svelte';

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let search = $state('');
	let loaded = $state(false);

	onMount(() => {
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Settings')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

{#if loaded}
	<div
		class="flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-260px)]'
			: ''} max-w-full"
	>
		<nav class="px-4 pt-2 backdrop-blur-xl drag-region">
			<div class="flex items-center gap-1">
				<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-end">
					<button
						id="sidebar-toggle-button"
						class="cursor-pointer p-2 flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition"
						onclick={() => {
							showSidebar.set(!$showSidebar);
						}}
						aria-label={$i18n.t('Toggle sidebar')}
					>
						<div class="m-auto self-center">
							<MenuLines />
						</div>
					</button>
				</div>

				<div class="flex items-center gap-2">
					<button
						class="cursor-pointer p-1.5 flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition"
						onclick={() => {
							goto(resolve('/'));
						}}
						aria-label={$i18n.t('Back')}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="1.5"
							stroke="currentColor"
							class="w-5 h-5"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"
							/>
						</svg>
					</button>
					<div class="text-lg font-medium self-center">{$i18n.t('Settings')}</div>
				</div>
			</div>
		</nav>

		<div class="flex flex-row flex-1 overflow-hidden px-4 pt-1 pb-4">
			<!-- Sidebar tabs -->
			<div
				class="hidden md:flex flex-col w-48 flex-none mr-4 text-sm font-medium text-left space-y-0.5"
			>
				<!-- Search -->
				<div class="w-full rounded-xl mb-2 px-0.5 gap-2 flex items-center">
					<div class="self-center rounded-l-xl bg-transparent">
						<Search className="size-3.5" />
					</div>
					<input
						class="w-full py-1.5 text-sm bg-transparent dark:text-gray-300 outline-hidden"
						bind:value={search}
						placeholder={$i18n.t('Search')}
					/>
				</div>

				<!-- General -->
				<a
					href={resolve('/settings/general')}
					class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
						.pathname === '/settings/general'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path
							fill-rule="evenodd"
							d="M8.34 1.804A1 1 0 019.32 1h1.36a1 1 0 01.98.804l.295 1.473c.497.144.971.342 1.416.587l1.25-.834a1 1 0 011.262.125l.962.962a1 1 0 01.125 1.262l-.834 1.25c.245.445.443.919.587 1.416l1.473.294a1 1 0 01.804.98v1.361a1 1 0 01-.804.98l-1.473.295a6.95 6.95 0 01-.587 1.416l.834 1.25a1 1 0 01-.125 1.262l-.962.962a1 1 0 01-1.262.125l-1.25-.834a6.953 6.953 0 01-1.416.587l-.294 1.473a1 1 0 01-.98.804H9.32a1 1 0 01-.98-.804l-.295-1.473a6.957 6.957 0 01-1.416-.587l-1.25.834a1 1 0 01-1.262-.125l-.962-.962a1 1 0 01-.125-1.262l.834-1.25a6.957 6.957 0 01-.587-1.416l-1.473-.294A1 1 0 011 10.68V9.32a1 1 0 01.804-.98l1.473-.295c.144-.497.342-.971.587-1.416l-.834-1.25a1 1 0 01.125-1.262l.962-.962A1 1 0 015.38 3.03l1.25.834a6.957 6.957 0 011.416-.587l.294-1.73zM13 10a3 3 0 11-6 0 3 3 0 016 0z"
							clip-rule="evenodd"
						/>
					</svg>
					<span class="self-center">{$i18n.t('General')}</span>
				</a>

				<!-- Interface -->
				<a
					href={resolve('/settings/interface')}
					class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
						.pathname === '/settings/interface'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				>
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
					<span class="self-center">{$i18n.t('Interface')}</span>
				</a>

				<!-- Connections (conditional) -->
				{#if $user.role === 'admin' || ($user.role === 'user' && $config?.features?.enable_direct_connections)}
					<a
						href={resolve('/settings/connections')}
						class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
							.pathname === '/settings/connections'
							? ''
							: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
					>
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
						<span class="self-center">{$i18n.t('Connections')}</span>
					</a>
				{/if}

				<!-- Tools (conditional) -->
				{#if $user.role === 'admin' || ($user.role === 'user' && $config?.features?.enable_direct_tools)}
					<a
						href={resolve('/settings/tools')}
						class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
							.pathname === '/settings/tools'
							? ''
							: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="currentColor"
							class="size-4"
						>
							<path
								fill-rule="evenodd"
								d="M12 6.75a5.25 5.25 0 0 1 6.775-5.025.75.75 0 0 1 .313 1.248l-3.32 3.319c.063.475.276.934.641 1.299.365.365.824.578 1.3.64l3.318-3.319a.75.75 0 0 1 1.248.313 5.25 5.25 0 0 1-5.472 6.756c-1.018-.086-1.87.1-2.309.634L7.344 21.3A3.298 3.298 0 1 1 2.7 16.657l8.684-7.151c.533-.44.72-1.291.634-2.309A5.342 5.342 0 0 1 12 6.75ZM4.117 19.125a.75.75 0 0 1 .75-.75h.008a.75.75 0 0 1 .75.75v.008a.75.75 0 0 1-.75.75h-.008a.75.75 0 0 1-.75-.75v-.008Z"
								clip-rule="evenodd"
							/>
						</svg>
						<span class="self-center">{$i18n.t('Tools')}</span>
					</a>
				{/if}

				<!-- Personalization -->
				<a
					href={resolve('/settings/personalization')}
					class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
						.pathname === '/settings/personalization'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				>
					<User className="w-4 h-4" />
					<span class="self-center">{$i18n.t('Personalization')}</span>
				</a>

				<!-- Audio -->
				<a
					href={resolve('/settings/audio')}
					class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
						.pathname === '/settings/audio'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				>
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
					<span class="self-center">{$i18n.t('Audio')}</span>
				</a>

				<!-- Chats -->
				<a
					href={resolve('/settings/chats')}
					class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
						.pathname === '/settings/chats'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path
							fill-rule="evenodd"
							d="M8 2C4.262 2 1 4.57 1 8c0 1.86.98 3.486 2.455 4.566a3.472 3.472 0 0 1-.469 1.26.75.75 0 0 0 .713 1.14 6.961 6.961 0 0 0 3.06-1.06c.403.062.818.094 1.241.094 3.738 0 7-2.57 7-6s-3.262-6-7-6ZM5 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm7-1a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM8 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
							clip-rule="evenodd"
						/>
					</svg>
					<span class="self-center">{$i18n.t('Chats')}</span>
				</a>

				<!-- Account -->
				<a
					href={resolve('/settings/account')}
					class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
						.pathname === '/settings/account'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path
							fill-rule="evenodd"
							d="M15 8A7 7 0 1 1 1 8a7 7 0 0 1 14 0Zm-5-2a2 2 0 1 1-4 0 2 2 0 0 1 4 0ZM8 9c-1.825 0-3.422.977-4.295 2.437A5.49 5.49 0 0 0 8 13.5a5.49 5.49 0 0 0 4.294-2.063A4.997 4.997 0 0 0 8 9Z"
							clip-rule="evenodd"
						/>
					</svg>
					<span class="self-center">{$i18n.t('Account')}</span>
				</a>

				<!-- About -->
				<a
					href={resolve('/settings/about')}
					class="px-2 py-1.5 min-w-fit rounded-lg flex items-center gap-2 transition {page.url
						.pathname === '/settings/about'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path
							fill-rule="evenodd"
							d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
							clip-rule="evenodd"
						/>
					</svg>
					<span class="self-center">{$i18n.t('About')}</span>
				</a>
			</div>

			<!-- Mobile horizontal tabs -->
			<div
				class="flex md:hidden overflow-x-auto gap-1.5 text-sm font-medium text-center mb-2 w-full"
			>
				<a
					href={resolve('/settings/general')}
					class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/general'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
					>{$i18n.t('General')}</a
				>
				<a
					href={resolve('/settings/interface')}
					class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/interface'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
					>{$i18n.t('Interface')}</a
				>
				{#if $user.role === 'admin' || ($user.role === 'user' && $config?.features?.enable_direct_connections)}
					<a
						href={resolve('/settings/connections')}
						class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/connections'
							? ''
							: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
						>{$i18n.t('Connections')}</a
					>
				{/if}
				{#if $user.role === 'admin' || ($user.role === 'user' && $config?.features?.enable_direct_tools)}
					<a
						href={resolve('/settings/tools')}
						class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/tools'
							? ''
							: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
						>{$i18n.t('Tools')}</a
					>
				{/if}
				<a
					href={resolve('/settings/personalization')}
					class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname ===
					'/settings/personalization'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
					>{$i18n.t('Personalization')}</a
				>
				<a
					href={resolve('/settings/audio')}
					class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/audio'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
					>{$i18n.t('Audio')}</a
				>
				<a
					href={resolve('/settings/chats')}
					class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/chats'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
					>{$i18n.t('Chats')}</a
				>
				<a
					href={resolve('/settings/account')}
					class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/account'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
					>{$i18n.t('Account')}</a
				>
				<a
					href={resolve('/settings/about')}
					class="min-w-fit rounded-full px-3 py-1.5 {page.url.pathname === '/settings/about'
						? ''
						: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
					>{$i18n.t('About')}</a
				>
			</div>

			<!-- Content area -->
			<div class="flex-1 min-h-0 overflow-y-auto">
				{@render children?.()}
			</div>
		</div>
	</div>
{/if}
