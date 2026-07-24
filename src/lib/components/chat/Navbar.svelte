<script lang="ts">
	import { get } from 'svelte/store';
	import { getContext } from 'svelte';

	import {
		APP_NAME_STORE,
		chatId,
		showArchivedChats,
		showControls,
		showSidebar,
		temporaryChatEnabled,
		user
	} from '$lib/stores';

	import ShareChatModal from '../chat/ShareChatModal.svelte';
	import ModelSelector from '../chat/ModelSelector.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Menu from '$lib/components/layout/Navbar/Menu.svelte';
	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';
	import MenuLines from '../icons/MenuLines.svelte';
	import AdjustmentsHorizontal from '../icons/AdjustmentsHorizontal.svelte';

	import PencilSquare from '../icons/PencilSquare.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/** Chat data structure passed from the parent Chat component */
	interface ChatData {
		id?: string;
		chat: {
			history: { currentId: string | null; [key: string]: unknown };
			title: string;
			[key: string]: unknown;
		};
		[key: string]: unknown;
	}

	interface Props {
		/** Callback to initialize a new chat session */
		initNewChat: () => void;
		/** Chat title displayed in the browser tab */
		title?: string;
		/** Whether sharing features are available */
		shareEnabled?: boolean;
		/** Current chat data */
		chat: ChatData;
		/** Currently selected model IDs */
		selectedModels: string[];
		/** Whether to show the model selector dropdown */
		showModelSelector?: boolean;
	}

	let {
		initNewChat,
		title: _title = get(APP_NAME_STORE),
		shareEnabled = false,
		chat,
		selectedModels = $bindable(),
		showModelSelector = true
	}: Props = $props();

	let showShareChatModal = $state(false);

	/** Toggle the sidebar open/closed state */
	const toggleSidebar = (): void => {
		showSidebar.set(!$showSidebar);
	};

	/** Toggle the chat controls panel */
	const toggleControls = async (): Promise<void> => {
		await showControls.set(!$showControls);
	};
</script>

<ShareChatModal bind:show={showShareChatModal} chatId={$chatId} />

<nav class="sticky top-0 z-30 w-full px-1.5 py-1.5 -mb-8 flex items-center drag-region">
	<div
		class=" bg-linear-to-b via-50% from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 dark:to-transparent pointer-events-none absolute inset-0 -bottom-7 z-[-1]"
	></div>

	<div class=" flex max-w-full w-full mx-auto px-1 pt-0.5 bg-transparent">
		<div class="flex items-center w-full max-w-full">
			<div
				class="{$showSidebar
					? 'md:hidden'
					: ''} mr-1 self-start flex flex-none items-center text-gray-600 dark:text-gray-400"
			>
				<button
					id="sidebar-toggle-button"
					class="cursor-pointer px-2 py-2 flex rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
					onclick={toggleSidebar}
					aria-label={$i18n.t('Toggle Sidebar')}
				>
					<div class=" m-auto self-center">
						<MenuLines />
					</div>
				</button>
			</div>

			<div
				class="flex-1 overflow-hidden max-w-full py-0.5
			{$showSidebar ? 'ml-1' : ''}
			"
			>
				{#if showModelSelector}
					<ModelSelector bind:selectedModels showSetDefault={!shareEnabled} />
				{/if}
			</div>

			<div class="self-start flex flex-none items-center text-gray-600 dark:text-gray-400">
				{#if shareEnabled && chat && (chat.id || $temporaryChatEnabled)}
					<Menu
						{chat}
						{shareEnabled}
						shareHandler={() => {
							showShareChatModal = !showShareChatModal;
						}}
						downloadHandler={() => {
							// Download modal intentionally not shown (same as original)
						}}
					>
						<button
							class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							id="chat-context-menu-button"
							aria-label={$i18n.t('More')}
						>
							<div class=" m-auto self-center">
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="1.5"
									stroke="currentColor"
									class="size-5"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										d="M6.75 12a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM12.75 12a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM18.75 12a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z"
									/>
								</svg>
							</div>
						</button>
					</Menu>
				{/if}

				<Tooltip content={$i18n.t('Controls')}>
					<button
						class=" flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
						onclick={toggleControls}
						aria-label={$i18n.t('Controls')}
					>
						<div class=" m-auto self-center">
							<AdjustmentsHorizontal className=" size-5" strokeWidth="0.5" />
						</div>
					</button>
				</Tooltip>

				<Tooltip content={$i18n.t('New Chat')}>
					<button
						id="new-chat-button"
						class=" flex {$showSidebar
							? 'md:hidden'
							: ''} cursor-pointer px-2 py-2 rounded-xl text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-850 transition"
						onclick={initNewChat}
						aria-label={$i18n.t('New Chat')}
					>
						<div class=" m-auto self-center">
							<PencilSquare className=" size-5" strokeWidth="2" />
						</div>
					</button>
				</Tooltip>

				{#if $user !== undefined}
					<UserMenu
						className="max-w-[200px]"
						role={$user.role}
						onshow={(e: CustomEvent) => {
							if (e.detail === 'archived-chat') {
								showArchivedChats.set(true);
							}
						}}
					>
						<button
							class="select-none flex rounded-xl p-1.5 w-full hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							aria-label={$i18n.t('User Menu')}
						>
							<div class=" self-center">
								<img
									src={$user.profile_image_url}
									class="size-6 object-cover rounded-full"
									alt={$i18n.t('User profile')}
									draggable="false"
								/>
							</div>
						</button>
					</UserMenu>
				{/if}
			</div>
		</div>
	</div>
</nav>
