<!-- BCGPT WebUI - App Layout: Authenticated shell with sidebar, changelog, keyboard shortcuts -->
<script lang="ts">
	import { onMount, tick, getContext, onDestroy } from 'svelte';
	import { openDB, deleteDB } from 'idb';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { fade } from 'svelte/transition';

	import { getModels, getToolServersData, getVersionUpdates } from '$lib/apis';
	import { getTools } from '$lib/apis/tools';
	import { getBanners } from '$lib/apis/configs';
	import { getUserSettings } from '$lib/apis/users';

	import { APP_VERSION } from '$lib/constants';
	import { compareVersion } from '$lib/utils';

	import {
		config,
		user,
		settings,
		models,
		tools,
		banners,
		showChangelog,
		temporaryChatEnabled,
		toolServers
	} from '$lib/stores';

	import Sidebar from '$lib/components/layout/Sidebar.svelte';
	import ChangelogModal from '$lib/components/ChangelogModal.svelte';
	import AccountPending from '$lib/components/layout/Overlay/AccountPending.svelte';
	import UpdateInfoToast from '$lib/components/layout/UpdateInfoToast.svelte';
	import { get } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let loaded = $state(false);
	let DB = $state(null);
	let localDBChats = $state([]);

	let version = $state();

	async function handleGlobalKeydown(event: KeyboardEvent) {
		const isCtrlPressed = event.ctrlKey || event.metaKey; // metaKey is for Cmd key on Mac
		// Check if the Shift key is pressed
		const isShiftPressed = event.shiftKey;

		// Check if Ctrl + Shift + O is pressed
		if (isCtrlPressed && isShiftPressed && event.key.toLowerCase() === 'o') {
			event.preventDefault();
			document.getElementById('sidebar-new-chat-button')?.click();
		}

		// Check if Shift + Esc is pressed
		if (isShiftPressed && event.key === 'Escape') {
			event.preventDefault();
			document.getElementById('chat-input')?.focus();
		}

		// Check if Ctrl + Shift + ; is pressed
		if (isCtrlPressed && isShiftPressed && event.key === ';') {
			event.preventDefault();
			const button = [...document.getElementsByClassName('copy-code-button')]?.at(-1);
			button?.click();
		}

		// Check if Ctrl + Shift + C is pressed
		if (isCtrlPressed && isShiftPressed && event.key.toLowerCase() === 'c') {
			event.preventDefault();
			const button = [...document.getElementsByClassName('copy-response-button')]?.at(-1);
			button?.click();
		}

		// Check if Ctrl + Shift + S is pressed
		if (isCtrlPressed && isShiftPressed && event.key.toLowerCase() === 's') {
			event.preventDefault();
			document.getElementById('sidebar-toggle-button')?.click();
		}

		// Check if Ctrl + Shift + Backspace is pressed
		if (isCtrlPressed && isShiftPressed && (event.key === 'Backspace' || event.key === 'Delete')) {
			event.preventDefault();
			document.getElementById('delete-chat-button')?.click();
		}

		// Check if Ctrl + . is pressed
		if (isCtrlPressed && event.key === '.') {
			event.preventDefault();
			goto(resolve('/settings'));
		}

		// Check if Ctrl + / is pressed
		if (isCtrlPressed && event.key === '/') {
			event.preventDefault();
			document.getElementById('show-shortcuts-button')?.click();
		}

		// Check if Ctrl + Shift + ' is pressed
		if (
			isCtrlPressed &&
			isShiftPressed &&
			(event.key.toLowerCase() === `'` || event.key.toLowerCase() === `"`)
		) {
			event.preventDefault();
			temporaryChatEnabled.set(!get(temporaryChatEnabled));
			await goto(resolve('/'));
			const newChatButton = document.getElementById('new-chat-button');
			setTimeout(() => {
				newChatButton?.click();
			}, 0);
		}
	}

	onMount(async () => {
		if (get(user) === undefined) {
			await goto(resolve('/auth'));
		} else if (['user', 'admin'].includes(get(user).role)) {
			try {
				// Check if IndexedDB exists
				DB = await openDB('Chats', 1);

				if (DB) {
					const chats = await DB.getAllFromIndex('chats', 'timestamp');
					localDBChats = chats.map((item, idx) => chats[chats.length - 1 - idx]);

					if (localDBChats.length === 0) {
						await deleteDB('Chats');
					}
				}
			} catch {
				// IndexedDB Not Found
			}

			const userSettings = await getUserSettings('').catch(() => {
				return null;
			});

			if (userSettings) {
				settings.set(userSettings.ui);
			} else {
				let localStorageSettings = {} as Parameters<(typeof settings)['set']>[0];

				try {
					localStorageSettings = JSON.parse(localStorage.getItem('settings') ?? '{}');
				} catch {
					// ignore
				}

				settings.set(localStorageSettings);
			}

			models.set(
				await getModels(
					'',
					get(config)?.features?.enable_direct_connections &&
						(get(settings)?.directConnections ?? null)
				)
			);

			banners.set(await getBanners(''));
			tools.set(await getTools(''));
			toolServers.set(await getToolServersData($i18n, get(settings)?.toolServers ?? []));

			document.addEventListener('keydown', handleGlobalKeydown);

			if (get(user).role === 'admin' && (get(settings)?.showChangelog ?? true)) {
				showChangelog.set(get(settings)?.version !== get(config).version);
			}

			if (page.url.searchParams.get('temporary-chat') === 'true') {
				temporaryChatEnabled.set(true);
			}

			if (get(user)?.permissions?.chat?.temporary_enforced) {
				temporaryChatEnabled.set(true);
			}

			// Check for version updates
			if (get(user).role === 'admin') {
				// Check if the user has dismissed the update toast in the last 24 hours
				if (localStorage.dismissedUpdateToast) {
					const dismissedUpdateToast = new Date(Number(localStorage.dismissedUpdateToast));
					const now = new Date();

					if (now - dismissedUpdateToast > 24 * 60 * 60 * 1000) {
						checkForVersionUpdates();
					}
				} else {
					checkForVersionUpdates();
				}
			}
			await tick();
		}

		loaded = true;
	});

	onDestroy(() => {
		document.removeEventListener('keydown', handleGlobalKeydown);
	});

	const checkForVersionUpdates = async () => {
		version = await getVersionUpdates('').catch(() => {
			return {
				current: APP_VERSION,
				latest: APP_VERSION
			};
		});
	};
</script>

<ChangelogModal bind:show={$showChangelog} />

{#if version && compareVersion(version.latest, version.current) && ($settings?.showUpdateToast ?? true)}
	<div class=" absolute bottom-8 right-8 z-50" in:fade={{ duration: 100 }}>
		<UpdateInfoToast
			{version}
			onClose={() => {
				localStorage.setItem('dismissedUpdateToast', Date.now().toString());
				version = null;
			}}
		/>
	</div>
{/if}

<div class="app relative">
	<div
		class=" text-gray-700 dark:text-gray-100 bg-white dark:bg-gray-900 h-screen max-h-[100dvh] overflow-auto flex flex-row justify-end"
	>
		{#if loaded}
			{#if !['user', 'admin'].includes($user.role)}
				<AccountPending />
			{:else if localDBChats.length > 0}
				<div class="fixed w-full h-full flex z-50">
					<div
						class="absolute w-full h-full backdrop-blur-md bg-white/20 dark:bg-gray-900/50 flex justify-center"
					>
						<div class="m-auto pb-44 flex flex-col justify-center">
							<div class="max-w-md">
								<div class="text-center dark:text-white text-2xl font-medium z-50">
									{$i18n.t('Important Update')}<br />
									{$i18n.t('Action Required for Chat Log Storage')}
								</div>

								<div class=" mt-4 text-center text-sm dark:text-gray-200 w-full">
									{$i18n.t(
										"Saving chat logs directly to your browser's storage is no longer supported. Please take a moment to download and delete your chat logs by clicking the button below. Don't worry, you can easily re-import your chat logs to the backend through"
									)}
									<span class="font-semibold dark:text-white"
										>{$i18n.t('Settings')} > {$i18n.t('Chats')} > {$i18n.t('Import Chats')}</span
									>. {$i18n.t(
										'This ensures that your valuable conversations are securely saved to your backend database. Thank you!'
									)}
								</div>

								<div class=" mt-6 mx-auto relative group w-fit">
									<button
										class="relative z-20 flex px-5 py-2 rounded-full bg-white border border-gray-100 dark:border-none hover:bg-gray-100 transition font-medium text-sm"
										onclick={async () => {
											let blob = new Blob([JSON.stringify(localDBChats)], {
												type: 'application/json'
											});
											saveAs(blob, `chat-export-${Date.now()}.json`);

											const tx = DB.transaction('chats', 'readwrite');
											await Promise.all([tx.store.clear(), tx.done]);
											await deleteDB('Chats');

											localDBChats = [];
										}}
									>
										{$i18n.t('Download & Delete')}
									</button>

									<button
										class="text-xs text-center w-full mt-2 text-gray-400 underline"
										onclick={async () => {
											localDBChats = [];
										}}>{$i18n.t('Close')}</button
									>
								</div>
							</div>
						</div>
					</div>
				</div>
			{/if}

			<Sidebar />
			{@render children?.()}
		{/if}
	</div>
</div>

<style>
	:global(.loading) {
		display: inline-block;
		clip-path: inset(0 1ch 0 0);
		animation: l 1s steps(3) infinite;
		letter-spacing: -0.5px;
	}

	@keyframes l {
		to {
			clip-path: inset(0 -1ch 0 0);
		}
	}

	:global(pre[class*='language-']) {
		position: relative;
		overflow: auto;

		/* make space  */
		margin: 5px 0;
		padding: 1.75rem 0 1.75rem 1rem;
		border-radius: 10px;
	}

	:global(pre[class*='language-'] button) {
		position: absolute;
		top: 5px;
		right: 5px;

		font-size: 0.9rem;
		padding: 0.15rem;
		background-color: #828282;

		border: ridge 1px #7b7b7c;
		border-radius: 5px;
		text-shadow: #c4c4c4 0 0 2px;
	}

	:global(pre[class*='language-'] button:hover) {
		cursor: pointer;
		background-color: #bcbabb;
	}
</style>
